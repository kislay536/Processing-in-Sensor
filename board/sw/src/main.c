/* EventCam board firmware, Step 2c: three sensor streams -> PL detectors -> trigger -> event window to the GPU laptop.
 * Bare-metal lwIP raw API on the Zedboard PS (Cortex-A9). UART1 for logs.
 *
 * TCP :5000 (laptop relay in, diagnostics out), parsed by 4-byte magic:
 *   FRM1 (32 B header + payload)  header fmt: 1 = colour YUYV 640x480 (614400 B), 2 = IR GREY 480x480 (230400 B), 3 = PCM16 x512 (1024 B).
 *                                 Each stream has its own DDR ring; the payload goes straight into slot (count % nslot), CRC32 is checked,
 *                                 the D-cache is flushed (DDR is what the PL reads), then the matching PL detector is run:
 *                                   colour -> image_change IP (0x40000000, the image-change-detector in fabric)  -> trigger decision
 *                                   IR     -> change_ir IP    (0x40010000)  score only
 *                                   audio  -> audio_bands IP  (0x40020000)  8 band powers only
 *   REQ1 (12 B)                   slot 0..59: RSP1 + that colour slot (CRC recomputed from DDR); 0xFFFFFFFF: STS1; 0xFFFFFFFE: DET1 (detector state).
 *   CFG1 (4 + 96 B)               24 x u32 parameters (see params[] below), applied immediately.
 * TCP :5001 (board listens, the laptop GPU stage connects): motion-gated streaming. While the scene is static NOTHING is sent. On the onset of
 * image_change `fired` (it already includes persistence + global/exposure suppression) the board sends `pre` colour frames from the ring, then every
 * colour frame as it arrives (same fps as the relay delivers) while motion lasts, plus `hang` frames after it stops, each as EVF1 (header with the
 * frame's timestamp + payload). A chunk is closed with EVE1 when motion ended or when it reaches `max_chunk_s` seconds (by frame timestamps);
 * sustained motion therefore arrives as consecutive chunks of at most max_chunk_s seconds.
 * Layout mirrors common/proto.py. IR and audio are measured and reported but NOT yet part of the trigger (untuned: see CONTEXT.md). */
#include <stdio.h>
#include <string.h>
#include "xparameters.h"
#include "netif/xadapter.h"
#include "platform.h"
#include "platform_config.h"
#include "xil_printf.h"
#include "xil_cache.h"
#include "xil_io.h"
#include "xtime_l.h"
#include "lwip/init.h"
#include "lwip/tcp.h"
#include "lwip/err.h"

#define REQ_STATS    0xFFFFFFFFUL
#define REQ_DET      0xFFFFFFFEUL
#define MAXSLOT      600
#define NPARAM       32

/* PL detector register bases (board/vivado/bd.tcl) */
#define IMG_BASE 0x40000000UL
#define IR_BASE  0x40010000UL
#define AUD_BASE 0x40020000UL
#define CROP_OFFSET 143488UL          /* row 112, column 64 of a 640x480 YUYV frame: first pixel of the 512x256 crop */

void tcp_fasttmr(void);
void tcp_slowtmr(void);
extern volatile int TcpFastTmrFlag;
extern volatile int TcpSlowTmrFlag;
struct netif server_netif;

static void enable_mdio_pins(void)
{
	Xil_Out32(0xF8000008, 0xDF0D);          /* SLCR unlock */
	Xil_Out32(0xF80007D0, 0x00001280);      /* MIO52 = MDC  */
	Xil_Out32(0xF80007D4, 0x00001280);      /* MIO53 = MDIO */
	Xil_Out32(0xF8000004, 0x767B);          /* SLCR lock */
}

/* ---- CRC32 (zlib polynomial, matches Python zlib.crc32) ---- */
static u32 crc_tab[256];
static void crc_init(void)
{
	for (u32 i = 0; i < 256; i++) {
		u32 c = i;
		for (int k = 0; k < 8; k++) c = (c & 1) ? (0xEDB88320U ^ (c >> 1)) : (c >> 1);
		crc_tab[i] = c;
	}
}
static u32 crc_update(u32 c, const u8 *p, u32 n)
{
	while (n--) c = crc_tab[(c ^ *p++) & 0xFF] ^ (c >> 8);
	return c;
}

/* ---- streams: 0 colour, 1 IR, 2 audio ---- */
enum { S_COL = 0, S_IR = 1, S_AUD = 2, NSTREAM = 3 };
typedef struct {
	UINTPTR base; u32 fbytes, nslot, count;
	u32 fid[MAXSLOT], len[MAXSLOT], crc[MAXSLOT];
	u64 ts[MAXSLOT];
} stream_t;
static stream_t st[NSTREAM] = {
	{ 0x10000000UL, 614400UL, 60 },
	{ 0x18000000UL, 230400UL, 60 },
	{ 0x1C000000UL, 1024UL,  600 },
};
static u32 crc_err, bad_len, fid_gaps, last_fid;
static u64 bytes_rx;
static int have_last = 0;

static inline u8 *slot_ptr(int s, u32 slot) { return (u8 *)(st[s].base + (UINTPTR)slot * st[s].fbytes); }

/* ---- tunable parameters (CFG1) ---- */
enum { P_PIX_MIN, P_VAR_INIT, P_VAR_MIN, P_VAR_MAX, P_VAR_SHIFT, P_MIN_CELLS, P_PERSIST, P_FREEZE, P_ILLUM_EN, P_ILLUM_MIN,
       P_CELL_REQ, P_GLOBAL_LIMIT, P_RESID_LIMIT, P_PRE, P_HANG, P_MAXCHUNK, P_IR_THR, P_IR_SHIFT, P_RESET, P_CTX_PERIOD, P_CTX_FRAMES, P_TRIG_MODE, P_AUD_RATIO, P_AUD_PERSIST, P_AUD_FLOOR };
static u32 params[NPARAM] = { 20, 4, 1, 127, 1, 2, 2, 3, 1, 10, 16, 2457, 204, 4, 6, 30, 24, 3, 0, 60, 10, 0, 40, 3, 150 };

static void apply_params(const u32 *p)
{
	u32 n[NPARAM]; memcpy(n, p, sizeof n);
	/* clamp to what the IPs / the window logic accept */
	if (n[P_PIX_MIN] > 255) n[P_PIX_MIN] = 255;
	if (n[P_VAR_MIN] < 1) n[P_VAR_MIN] = 1;
	if (n[P_VAR_INIT] < n[P_VAR_MIN]) n[P_VAR_INIT] = n[P_VAR_MIN];
	if (n[P_VAR_MAX] < n[P_VAR_INIT]) n[P_VAR_MAX] = n[P_VAR_INIT];
	if (n[P_VAR_MAX] > 255) n[P_VAR_MAX] = 255;
	if (n[P_VAR_SHIFT] > 7) n[P_VAR_SHIFT] = 7;
	if (n[P_MIN_CELLS] < 1) n[P_MIN_CELLS] = 1;
	if (n[P_MIN_CELLS] > 64) n[P_MIN_CELLS] = 64;
	if (n[P_PERSIST] < 1) n[P_PERSIST] = 1;
	if (n[P_PERSIST] > 65535) n[P_PERSIST] = 65535;
	if (n[P_FREEZE] < 1) n[P_FREEZE] = 1;
	if (n[P_FREEZE] > 65535) n[P_FREEZE] = 65535;
	n[P_ILLUM_EN] = n[P_ILLUM_EN] != 0;
	if (n[P_ILLUM_MIN] < 1) n[P_ILLUM_MIN] = 1;
	if (n[P_ILLUM_MIN] > 255) n[P_ILLUM_MIN] = 255;
	if (n[P_CELL_REQ] < 1) n[P_CELL_REQ] = 1;
	if (n[P_CELL_REQ] > 64) n[P_CELL_REQ] = 64;
	if (n[P_GLOBAL_LIMIT] > 4095) n[P_GLOBAL_LIMIT] = 4095;
	if (n[P_RESID_LIMIT] > 4095) n[P_RESID_LIMIT] = 4095;
	if (n[P_PRE] > 50) n[P_PRE] = 50;                 /* pre-roll comes from the 60-slot ring */
	if (n[P_HANG] > 1000) n[P_HANG] = 1000;
	if (n[P_MAXCHUNK] < 1) n[P_MAXCHUNK] = 1;
	if (n[P_MAXCHUNK] > 3600) n[P_MAXCHUNK] = 3600;
	if (n[P_CTX_PERIOD] > 86400) n[P_CTX_PERIOD] = 86400;      /* 0 = no scene-context bursts */
	if (n[P_CTX_FRAMES] < 1) n[P_CTX_FRAMES] = 1;
	if (n[P_CTX_FRAMES] > 50) n[P_CTX_FRAMES] = 50;
	if (n[P_TRIG_MODE] > 1) n[P_TRIG_MODE] = 1;                /* 0 = video trigger only, 1 = video OR audio */
	if (n[P_AUD_RATIO] < 11) n[P_AUD_RATIO] = 11;               /* x10: 40 = block energy 4.0x the slow baseline */
	if (n[P_AUD_RATIO] > 10000) n[P_AUD_RATIO] = 10000;
	if (n[P_AUD_PERSIST] < 1) n[P_AUD_PERSIST] = 1;
	if (n[P_AUD_PERSIST] > 200) n[P_AUD_PERSIST] = 200;
	if (n[P_AUD_FLOOR] > 32767) n[P_AUD_FLOOR] = 32767;         /* RMS (int16 units) the block must exceed */
	if (n[P_IR_THR] > 255) n[P_IR_THR] = 255;
	if (n[P_IR_SHIFT] < 1) n[P_IR_SHIFT] = 1;
	if (n[P_IR_SHIFT] > 8) n[P_IR_SHIFT] = 8;
	memcpy(params, n, sizeof params);
}

/* ---- PL detector drivers (plain AXI-Lite register access; offsets from the HLS-generated *_hw.h) ---- */
static u32 img_reset_pending = 1, ir_reset_pending = 1;
static struct { u32 fired, reason, score, region, active, changed, persist, ipframes, us; u8 cells[64]; } img;
static struct { u32 changed, score, ipframes; } ir;
static struct { u64 band[8]; u64 sumsq; u32 blocks; } aud;
static u32 onsets, fired_frames, ir_rx, aud_rx;
/* audio change detector (PS decision on the PL band-power result): block energy vs a slow baseline */
static struct { u64 base; u32 run, hold, rms, base_rms, onsets, blocks, fired, prev_fired; } ad;
static u32 isqrt64(u64 x) { u64 r = 0, b = 1ULL << 62; while (b > x) b >>= 2; while (b) { if (x >= r + b) { x -= r + b; r = (r >> 1) + b; } else r >>= 1; b >>= 2; } return (u32)r; }
static void audio_detect(void)
{
	u64 e = aud.sumsq;                                         /* sum of squares of the 512 samples of this block */
	u64 floor_e = (u64)params[P_AUD_FLOOR] * params[P_AUD_FLOOR] * 512ULL;
	int active = ad.blocks > 40 && e > floor_e && e * 10ULL > (u64)params[P_AUD_RATIO] * ad.base;
	if (ad.blocks == 0) ad.base = e;
	if (!active) ad.base += ((s64)e - (s64)ad.base) >> (ad.blocks < 40 ? 3 : 6);   /* adapt only while quiet: speech does not raise the baseline */
	ad.blocks++;
	ad.run = active ? ad.run + 1 : 0;
	if (ad.run >= params[P_AUD_PERSIST]) ad.hold = 31;           /* hold ~1 s so short pauses do not end the event */
	else if (ad.hold) ad.hold--;
	ad.fired = ad.run >= params[P_AUD_PERSIST] || ad.hold > 0;
	if (ad.fired && !ad.prev_fired) ad.onsets++;
	ad.prev_fired = ad.fired;
	ad.rms = isqrt64(e / 512ULL); ad.base_rms = isqrt64(ad.base / 512ULL);
}
static u64 us_of(XTime t) { return t * 1000000ULL / COUNTS_PER_SECOND; }

static int ip_run(UINTPTR base)
{
	XTime t0, t;
	Xil_Out32(base, 1);
	XTime_GetTime(&t0);
	do {
		if (Xil_In32(base) & 2) return 1;
		XTime_GetTime(&t);
	} while (us_of(t - t0) < 100000);
	return 0;
}

static void run_image(u32 idx)
{
	XTime t0, t1;
	static const u8 poff[13] = { 0x1c, 0x24, 0x2c, 0x34, 0x3c, 0x44, 0x4c, 0x54, 0x5c, 0x64, 0x6c, 0x74, 0x7c };
	XTime_GetTime(&t0);
	Xil_Out32(IMG_BASE + 0x10, (u32)(UINTPTR)(slot_ptr(S_COL, idx % st[S_COL].nslot) + CROP_OFFSET));
	Xil_Out32(IMG_BASE + 0x14, 0);
	for (int k = 0; k < 13; k++) Xil_Out32(IMG_BASE + poff[k], params[k]);
	Xil_Out32(IMG_BASE + 0x84, img_reset_pending); img_reset_pending = 0;
	if (!ip_run(IMG_BASE)) { xil_printf("image IP timeout\r\n"); return; }
	img.fired = Xil_In32(IMG_BASE + 0x8c) & 1;
	img.reason = Xil_In32(IMG_BASE + 0x9c) & 0xFF;
	img.score = Xil_In32(IMG_BASE + 0xac) & 0xFF;
	img.region = Xil_In32(IMG_BASE + 0xbc) & 1;
	img.active = Xil_In32(IMG_BASE + 0xcc) & 0xFF;
	img.changed = Xil_In32(IMG_BASE + 0xdc) & 0xFFFF;
	img.persist = Xil_In32(IMG_BASE + 0xec) & 0xFFFF;
	img.ipframes = Xil_In32(IMG_BASE + 0x140);
	for (int k = 0; k < 16; k++) { u32 w = Xil_In32(IMG_BASE + 0x100 + 4 * k); memcpy(img.cells + 4 * k, &w, 4); }
	XTime_GetTime(&t1);
	img.us = (u32)us_of(t1 - t0);
}

static void run_ir(u32 idx)
{
	Xil_Out32(IR_BASE + 0x10, (u32)(UINTPTR)slot_ptr(S_IR, idx % st[S_IR].nslot));
	Xil_Out32(IR_BASE + 0x1c, params[P_IR_THR]); Xil_Out32(IR_BASE + 0x24, params[P_IR_SHIFT]);
	Xil_Out32(IR_BASE + 0x2c, ir_reset_pending); ir_reset_pending = 0;
	if (!ip_run(IR_BASE)) { xil_printf("IR IP timeout\r\n"); return; }
	ir.changed = Xil_In32(IR_BASE + 0x34); ir.score = Xil_In32(IR_BASE + 0x54); ir.ipframes = Xil_In32(IR_BASE + 0x64);
}

static void run_audio(u32 idx)
{
	Xil_Out32(AUD_BASE + 0x10, (u32)(UINTPTR)slot_ptr(S_AUD, idx % st[S_AUD].nslot));
	if (!ip_run(AUD_BASE)) { xil_printf("audio IP timeout\r\n"); return; }
	for (int k = 0; k < 8; k++)
		aud.band[k] = ((u64)Xil_In32(AUD_BASE + 0x44 + 8 * k) << 32) | Xil_In32(AUD_BASE + 0x40 + 8 * k);
	aud.sumsq = ((u64)Xil_In32(AUD_BASE + 0x20) << 32) | Xil_In32(AUD_BASE + 0x1c);
	aud.blocks = Xil_In32(AUD_BASE + 0x80);
}

/* ---- motion-gated frame streaming (TCP :5001, board is the server) ----
 * EVF1 header (48 B) = "EVF1", seg, episode, chunk, seq, flags, fid (u32 each), ts_us u64, w u16, h u16, fmt u8, pad, changed u16, len u32; then the payload.
 *   flags: bit0 first frame of the chunk, bit1 pre-roll frame (before the detector fired), bit2 scene-context frame,
 *          bit3 video detector firing on this frame, bit4 audio detector firing at this frame.
 * EVA1 header (48 B) = "EVA1", seg, episode, chunk, first_seq, n_blocks, flags (u32 each), first_ts_us u64, len u32, pad; then n_blocks x 1024 B PCM16 (16 kHz mono, 512 samples/block).
 * EVE1 header (44 B) = "EVE1", seg, episode, chunk, n_frames, reason (u32 each; 0 motion ended, 1 max chunk length, 2 interrupted, 3 scene context), first_ts u64, last_ts u64, n_audio_blocks u32 (44 B). */
static struct tcp_pcb *evt_pcb;
enum { QI_FRAME = 0, QI_END = 1, QI_AUDIO = 2 };
typedef struct { u8 type, flags; u16 changed; u32 idx, seg, episode, chunk, seq, n; u64 t0, t1; } qitem_t;
#define QCAP 128
static qitem_t evq[QCAP];
static u32 q_head, q_tail;
static struct {
	int active, kind;                   /* kind 0 = motion episode, 1 = scene-context burst */
	u32 episode, seg, chunk, seq, hang_left;
	u64 chunk_t0, last_ts;
	u32 chunks_sent, frames_sent, frames_lost, episodes_dropped;
	int aud_on; u32 aud_next, aud_seq, aud_sent, aud_lost, cause;   /* audio of the episode: next ring block to queue, blocks in this chunk */
} ev;
static struct { int stage; u32 off, hlen, plen; u8 hdr[48]; const u8 *pay; } etx;
/* scene context: at least P_CTX_FRAMES frames per P_CTX_PERIOD seconds reach the GPU even when nothing moves */
static u64 ctx_win_t0;
static u32 ctx_sent, ctx_left;
static int ctx_first = 1;

static void ev_flush_audio(int force);
static int q_push(const qitem_t *it)
{
	if (q_tail - q_head >= QCAP) return 0;
	evq[q_tail % QCAP] = *it; q_tail++;
	return 1;
}

static void ev_close_chunk(u32 reason)
{
	qitem_t it = {0};
	ev_flush_audio(1);                                      /* the chunk's audio ends with the chunk */
	it.type = QI_END; it.flags = (u8)reason; it.seg = ev.seg; it.episode = ev.episode; it.chunk = ev.chunk; it.n = ev.seq; it.idx = ev.aud_seq;
	it.t0 = ev.chunk_t0; it.t1 = ev.last_ts;
	if (!q_push(&it)) ev.frames_lost++;
	xil_printf("chunk %u (episode %u/%u) closed: %u frames, %u audio blocks, reason %u\r\n", ev.seg, ev.episode, ev.chunk, ev.seq, ev.aud_seq, reason);
}

/* start collecting audio for a new episode at the first block not older than from_ts (the first video frame of the chunk) */
static void ev_audio_start(u64 from_ts)
{
	stream_t *z = &st[S_AUD];
	u32 cnt = z->count, depth = cnt < z->nslot - 8 ? cnt : z->nslot - 8, first = cnt;
	for (u32 k = 0; k < depth; k++) { u32 i = cnt - 1 - k; if (z->ts[i % z->nslot] >= from_ts) first = i; else break; }
	ev.aud_on = 1; ev.aud_next = first; ev.aud_seq = 0;
}

static void ev_flush_audio(int force)
{
	stream_t *z = &st[S_AUD];
	if (!ev.aud_on) return;
	while (ev.aud_next < z->count) {
		u32 avail = z->count - ev.aud_next, slot, n;
		if (avail > z->nslot - 8) { u32 lost = avail - (z->nslot - 8); ev.aud_lost += lost; ev.aud_next += lost; avail -= lost; }   /* overwritten in the ring */
		if (!force && avail < 16) return;
		slot = ev.aud_next % z->nslot; n = avail > 16 ? 16 : avail;
		if (slot + n > z->nslot) n = z->nslot - slot;       /* an item never wraps around the ring */
		qitem_t it = {0};
		it.type = QI_AUDIO; it.idx = ev.aud_next; it.n = n; it.seg = ev.seg; it.episode = ev.episode; it.chunk = ev.chunk; it.seq = ev.aud_seq;
		if (!q_push(&it)) { ev.aud_lost += n; }
		else ev.aud_seq += n;
		ev.aud_next += n;
	}
}

static void ev_queue_frame(u32 idx, u8 flags)
{
	u32 s = idx % st[S_COL].nslot;
	u64 ts = st[S_COL].ts[s];
	qitem_t it = {0};
	if (ev.seq > 0 && ts - ev.chunk_t0 >= (u64)params[P_MAXCHUNK] * 1000000ULL) {   /* 30 s (by frame timestamps) -> next batch */
		ev_close_chunk(1);
		ev.seg++; ev.chunk++; ev.seq = 0; ev.aud_seq = 0;
	}
	if (ev.seq == 0) { ev.chunk_t0 = ts; flags |= 1; }
	if (!(flags & 2)) { if (img.fired) flags |= 8; if (params[P_TRIG_MODE] && ad.fired) flags |= 16; }
	it.type = QI_FRAME; it.flags = flags; it.changed = (u16)img.changed; it.idx = idx; it.seg = ev.seg; it.episode = ev.episode;
	it.chunk = ev.chunk; it.seq = ev.seq;
	if (!q_push(&it)) { ev.frames_lost++; return; }
	ev.seq++; ev.last_ts = ts; if (!(flags & 4)) ctx_sent++;   /* context frames do not count towards the next window */
}

static void ev_reset_stream(void)
{
	q_head = q_tail = 0; etx.stage = 0; etx.off = 0; ev.active = 0; ev.aud_on = 0;
}

static void ev_pump(void)
{
	if (!evt_pcb) return;
	while (q_head != q_tail) {
		qitem_t *it = &evq[q_head % QCAP];
		if (etx.stage == 0) {
			if (it->type == QI_FRAME) {
				u32 s = it->idx % st[S_COL].nslot, fid = st[S_COL].fid[s], len = st[S_COL].len[s], magic = 0x31465645U /* "EVF1" */;
				u64 ts = st[S_COL].ts[s];
				u16 w = 640, h = 480, ch = it->changed; u8 fmt = 1, pad = 0;
				if (st[S_COL].count - it->idx > 58) { ev.frames_lost++; q_head++; continue; }   /* slot already overwritten by newer frames */
				memcpy(etx.hdr, &magic, 4); memcpy(etx.hdr + 4, &it->seg, 4); memcpy(etx.hdr + 8, &it->episode, 4);
				memcpy(etx.hdr + 12, &it->chunk, 4); memcpy(etx.hdr + 16, &it->seq, 4); { u32 fl = it->flags; memcpy(etx.hdr + 20, &fl, 4); }
				memcpy(etx.hdr + 24, &fid, 4); memcpy(etx.hdr + 28, &ts, 8); memcpy(etx.hdr + 36, &w, 2); memcpy(etx.hdr + 38, &h, 2);
				etx.hdr[40] = fmt; etx.hdr[41] = pad; memcpy(etx.hdr + 42, &ch, 2); memcpy(etx.hdr + 44, &len, 4);
				etx.hlen = 48; etx.pay = slot_ptr(S_COL, s); etx.plen = len;
			} else if (it->type == QI_AUDIO) {
				u32 magic = 0x31415645U /* "EVA1" */, fl = 0, slot = it->idx % st[S_AUD].nslot, len = it->n * 1024;
				u64 ts = st[S_AUD].ts[slot];
				if (st[S_AUD].count - it->idx > st[S_AUD].nslot - 4) { ev.aud_lost += it->n; q_head++; continue; }   /* overwritten by newer blocks */
				memset(etx.hdr, 0, 48);
				memcpy(etx.hdr, &magic, 4); memcpy(etx.hdr + 4, &it->seg, 4); memcpy(etx.hdr + 8, &it->episode, 4);
				memcpy(etx.hdr + 12, &it->chunk, 4); memcpy(etx.hdr + 16, &it->seq, 4); memcpy(etx.hdr + 20, &it->n, 4);
				memcpy(etx.hdr + 24, &fl, 4); memcpy(etx.hdr + 28, &ts, 8); memcpy(etx.hdr + 36, &len, 4);
				etx.hlen = 48; etx.pay = slot_ptr(S_AUD, slot); etx.plen = len;
			} else {
				u32 magic = 0x31455645U /* "EVE1" */, rs = it->flags, na = it->idx;
				memcpy(etx.hdr, &magic, 4); memcpy(etx.hdr + 4, &it->seg, 4); memcpy(etx.hdr + 8, &it->episode, 4);
				memcpy(etx.hdr + 12, &it->chunk, 4); memcpy(etx.hdr + 16, &it->n, 4); memcpy(etx.hdr + 20, &rs, 4);
				memcpy(etx.hdr + 24, &it->t0, 8); memcpy(etx.hdr + 32, &it->t1, 8); memcpy(etx.hdr + 40, &na, 4);
				etx.hlen = 44; etx.pay = NULL; etx.plen = 0;
			}
			if (tcp_sndbuf(evt_pcb) < etx.hlen) break;
			if (tcp_write(evt_pcb, etx.hdr, etx.hlen, TCP_WRITE_FLAG_COPY | (etx.plen ? TCP_WRITE_FLAG_MORE : 0)) != ERR_OK) break;
			etx.stage = 1; etx.off = 0;
		}
		if (etx.stage == 1) {
			while (etx.off < etx.plen) {
				u32 room = tcp_sndbuf(evt_pcb), n = etx.plen - etx.off;
				if (!room) break;
				if (n > room) n = room;
				if (n > 16 * 1460) n = 16 * 1460;
				if (tcp_write(evt_pcb, etx.pay + etx.off, n, 0) != ERR_OK) break;
				etx.off += n;
			}
			if (etx.off < etx.plen) break;                 /* wait for acks */
			if (it->type == QI_FRAME) ev.frames_sent++; else if (it->type == QI_AUDIO) ev.aud_sent += it->n; else ev.chunks_sent++;
			etx.stage = 0; q_head++;
		}
	}
	tcp_output(evt_pcb);
}

/* called after every colour frame has been through the PL */
static void event_step(u32 idx, u32 fid)
{
	static u32 prev_fired = 0;
	int afire = params[P_TRIG_MODE] && ad.fired;               /* union trigger: video OR audio */
	int trig = img.fired || afire;
	u32 onset = trig && !prev_fired;
	prev_fired = trig;
	if (img.fired) fired_frames++;
	if (onset) onsets++;
	if (!evt_pcb && ev.active) { ev_reset_stream(); }
	/* context window bookkeeping (by frame timestamps): true when a context burst is due */
	int ctx_due = 0;
	{
		u32 period = params[P_CTX_PERIOD];
		u64 ts = st[S_COL].ts[idx % st[S_COL].nslot];
		if (!period || !evt_pcb) { ctx_first = 1; }
		else if (ctx_first) { ctx_first = 0; ctx_win_t0 = ts; ctx_sent = 0; ctx_due = 1; }      /* baseline right after a GPU client connects */
		else if (ts - ctx_win_t0 >= (u64)period * 1000000ULL) { ctx_due = ctx_sent < params[P_CTX_FRAMES]; ctx_win_t0 = ts; ctx_sent = 0; }
	}
	if (!ev.active) {
		if (!onset) {
			if (!ctx_due) return;
			ev.active = 1; ev.kind = 1; ev.episode++; ev.seg++; ev.chunk = 0; ev.seq = 0; ctx_left = params[P_CTX_FRAMES];
			xil_printf("CONTEXT fid %u: sending %u frames of scene context (episode %u)\r\n", fid, ctx_left, ev.episode);
			ev_audio_start(st[S_COL].ts[idx % st[S_COL].nslot]);
			ev_queue_frame(idx, 4); ctx_left--;
			if (ctx_left == 0) { ev_close_chunk(3); ev.active = 0; }
			ev_pump();
			return;
		}
		if (!evt_pcb) { ev.episodes_dropped++; xil_printf("motion at fid %u: no GPU client on :5001, nothing sent\r\n", fid); return; }
		u32 pre = params[P_PRE], first = idx >= pre ? idx - pre : 0;
		ev.active = 1; ev.kind = 0; ev.episode++; ev.seg++; ev.chunk = 0; ev.seq = 0; ev.hang_left = params[P_HANG];
		xil_printf("TRIGGER (%s%s) fid %u: score %u changed %u active %u aud_rms %u -> streaming (episode %u, %u pre-roll frames)\r\n",
		           img.fired ? "video" : "", afire ? (img.fired ? "+audio" : "audio") : "", fid, img.score, img.changed, img.active, ad.rms, ev.episode, idx - first);
		ev_audio_start(st[S_COL].ts[first % st[S_COL].nslot]);
		for (u32 i = first; i < idx; i++) ev_queue_frame(i, 2);
		ev_queue_frame(idx, 0);
	} else if (ev.kind == 1) {
		if (trig) {                                        /* motion/sound during a context burst: continue as a motion episode */
			ev.kind = 0; ev.hang_left = params[P_HANG];
			xil_printf("MOTION fid %u during context burst -> continuing as motion\r\n", fid);
			ev_queue_frame(idx, 0);
		} else {
			ev_queue_frame(idx, 4);
			if (--ctx_left == 0) { ev_close_chunk(3); ev.active = 0; }
		}
	} else if (trig) {
		ev.hang_left = params[P_HANG];
		ev_queue_frame(idx, 0);
	} else if (ev.hang_left == 0) {
		ev_close_chunk(0); ev.active = 0;
	} else {
		ev_queue_frame(idx, 0);
		if (--ev.hang_left == 0) { ev_close_chunk(0); ev.active = 0; }
	}
	ev_pump();
}

/* ---- receive parser (state persists across pbufs) ---- */
enum { PH_MAGIC, PH_HDR, PH_PAYLOAD, PH_SKIP };
enum { K_FRM, K_REQ, K_CFG };
static struct {
	int phase;
	u8 hbuf[136] __attribute__((aligned(8)));
	u32 hgot, hneed, kind;
	u32 stream, slot, plen, pgot, crc, fid, hdr_crc; u64 ts;
} ps;

static void parser_reset(void) { memset(&ps, 0, sizeof ps); ps.phase = PH_MAGIC; ps.hneed = 4; }

/* ---- reply sender (port 5000) ---- */
static struct {
	u8 hdr[512]; u32 hlen, hsent;
	const u8 *pay; u32 plen, psent;
	int active;
} tx;

static void tx_pump(struct tcp_pcb *tpcb)
{
	while (tx.active) {
		u32 room = tcp_sndbuf(tpcb);
		if (!room) break;
		if (tx.hsent < tx.hlen) {
			u32 n = tx.hlen - tx.hsent;
			if (n > room) n = room;
			if (tcp_write(tpcb, tx.hdr + tx.hsent, n, TCP_WRITE_FLAG_COPY | (tx.plen ? TCP_WRITE_FLAG_MORE : 0)) != ERR_OK) break;
			tx.hsent += n; room -= n;
			if (tx.hsent < tx.hlen) break;
		}
		if (tx.psent < tx.plen && room) {
			u32 n = tx.plen - tx.psent;
			if (n > room) n = room;
			if (n > 16 * 1460) n = 16 * 1460;
			if (tcp_write(tpcb, tx.pay + tx.psent, n, 0) != ERR_OK) break;   /* no-copy: ring data is stable while the laptop reads */
			tx.psent += n;
		}
		if (tx.hsent >= tx.hlen && tx.psent >= tx.plen) { tx.active = 0; }
	}
	tcp_output(tpcb);
}

static void send_stats(struct tcp_pcb *tpcb)
{
	u32 v[6] = {0x31535453U /* "STS1" */, st[S_COL].count, crc_err, bad_len, fid_gaps, last_fid};
	memcpy(tx.hdr, v, 24);
	memcpy(tx.hdr + 24, &bytes_rx, 8);
	tx.hlen = 32; tx.hsent = 0; tx.pay = NULL; tx.plen = tx.psent = 0; tx.active = 1;
	tx_pump(tpcb);
}

/* DET1 = "DET1" + 40 x u32 + 64 x u8 (8x8 cell counts) + 8 x u64 (audio bands) + 32 x u32 (params)  = 420 B */
static void send_det(struct tcp_pcb *tpcb)
{
	u32 f[40] = {0};
	f[0] = st[S_COL].count; f[1] = crc_err; f[2] = last_fid;
	f[3] = img.fired; f[4] = img.reason; f[5] = img.score; f[6] = img.region; f[7] = img.active; f[8] = img.changed;
	f[9] = img.persist; f[10] = img.ipframes; f[11] = ev.chunks_sent; f[12] = ev.episodes_dropped; f[13] = ev.active ? (ev.kind == 1 ? 2 : 1) : 0; f[14] = ev.seg; f[15] = onsets;
	f[16] = ir_rx; f[17] = ir.changed; f[18] = ir.score; f[19] = ir.ipframes; f[20] = aud_rx; f[21] = aud.blocks;
	f[22] = (u32)aud.sumsq; f[23] = (u32)(aud.sumsq >> 32); f[24] = evt_pcb != NULL; f[25] = img.us; f[26] = fired_frames;
	f[27] = ev.frames_sent; f[28] = ev.frames_lost; f[29] = ev.episode; f[30] = q_tail - q_head;
	f[31] = ad.fired; f[32] = ad.rms; f[33] = ad.base_rms; f[34] = ad.onsets; f[35] = ev.aud_sent; f[36] = ev.aud_lost; f[37] = (img.fired ? 1 : 0) | ((params[P_TRIG_MODE] && ad.fired) ? 2 : 0);
	memcpy(tx.hdr, "DET1", 4);
	memcpy(tx.hdr + 4, f, 160);
	memcpy(tx.hdr + 164, img.cells, 64);
	memcpy(tx.hdr + 228, aud.band, 64);
	memcpy(tx.hdr + 292, params, 128);
	tx.hlen = 420; tx.hsent = 0; tx.pay = NULL; tx.plen = tx.psent = 0; tx.active = 1;
	tx_pump(tpcb);
}

static void send_slot(struct tcp_pcb *tpcb, u32 s)
{
	u32 v[6];
	u32 len = st[S_COL].len[s];
	/* force a real DDR read: flush(clean+invalidate) so the CRC below is not served from the data cache */
	Xil_DCacheFlushRange((UINTPTR)slot_ptr(S_COL, s), st[S_COL].fbytes);
	u32 crc = crc_update(0xFFFFFFFFU, slot_ptr(S_COL, s), len) ^ 0xFFFFFFFFU;
	v[0] = 0x31505352U /* "RSP1" */; v[1] = s; v[2] = st[S_COL].fid[s]; v[3] = len; v[4] = crc; v[5] = st[S_COL].crc[s];
	memcpy(tx.hdr, v, 24);
	tx.hlen = 24; tx.hsent = 0; tx.pay = slot_ptr(S_COL, s); tx.plen = len; tx.psent = 0; tx.active = 1;
	tx_pump(tpcb);
}

static void frame_done(void)
{
	int si = ps.stream;
	stream_t *z = &st[si];
	u32 s = ps.slot, idx = z->count;
	u32 crc = ps.crc ^ 0xFFFFFFFFU;
	Xil_DCacheFlushRange((UINTPTR)slot_ptr(si, s), z->fbytes);   /* DDR now holds the frame (and the PL will read it from DDR) */
	if (crc != ps.hdr_crc) crc_err++;
	if (si == S_COL) {
		if (have_last && ps.fid != 0 && ps.fid != last_fid + 1) fid_gaps++;   /* fid 0 = a new relay session starts, not a loss */
		have_last = 1; last_fid = ps.fid;
		if (ps.fid == 0) img_reset_pending = 1;
	}
	if (si == S_IR && ps.fid == 0) ir_reset_pending = 1;
	z->fid[s] = ps.fid; z->crc[s] = ps.hdr_crc; z->len[s] = ps.plen; z->ts[s] = ps.ts;
	z->count++;
	if (si == S_COL) { run_image(idx); event_step(idx, ps.fid); }
	else if (si == S_IR) { ir_rx++; run_ir(idx); }
	else {
		aud_rx++; run_audio(idx); audio_detect();
		if (ev.active && ev.aud_on) { ev_flush_audio(0); ev_pump(); }
	}
}

static void feed(struct tcp_pcb *tpcb, const u8 *p, u32 n)
{
	while (n) {
		switch (ps.phase) {
		case PH_MAGIC:
		case PH_HDR: {
			u32 take = ps.hneed - ps.hgot;
			if (take > n) take = n;
			memcpy(ps.hbuf + ps.hgot, p, take);
			ps.hgot += take; p += take; n -= take;
			if (ps.hgot < ps.hneed) break;
			if (ps.phase == PH_MAGIC) {
				if (!memcmp(ps.hbuf, "FRM1", 4)) { ps.kind = K_FRM; ps.hneed = 32; ps.phase = PH_HDR; }
				else if (!memcmp(ps.hbuf, "REQ1", 4)) { ps.kind = K_REQ; ps.hneed = 12; ps.phase = PH_HDR; }
				else if (!memcmp(ps.hbuf, "CFG1", 4)) { ps.kind = K_CFG; ps.hneed = 4 + 4 * NPARAM; ps.phase = PH_HDR; }
				else { xil_printf("bad magic %02x%02x%02x%02x, dropping connection\r\n", ps.hbuf[0], ps.hbuf[1], ps.hbuf[2], ps.hbuf[3]);
				       parser_reset(); tcp_abort(tpcb); return; }
				break;
			}
			if (ps.kind == K_FRM) {
				u32 fid, len, crc; u64 ts; u8 fmt = ps.hbuf[20];
				memcpy(&fid, ps.hbuf + 4, 4); memcpy(&ts, ps.hbuf + 8, 8); memcpy(&len, ps.hbuf + 24, 4); memcpy(&crc, ps.hbuf + 28, 4);
				ps.fid = fid; ps.ts = ts; ps.plen = len; ps.hdr_crc = crc; ps.pgot = 0; ps.crc = 0xFFFFFFFFU;
				ps.stream = (fmt >= 1 && fmt <= NSTREAM) ? fmt - 1 : 0;
				ps.slot = st[ps.stream].count % st[ps.stream].nslot;
				if (fmt < 1 || fmt > NSTREAM || len != st[ps.stream].fbytes) { bad_len++; ps.phase = len ? PH_SKIP : PH_MAGIC; }
				else ps.phase = PH_PAYLOAD;
			} else if (ps.kind == K_REQ) {
				u32 slot; memcpy(&slot, ps.hbuf + 4, 4);
				if (slot == REQ_STATS) send_stats(tpcb);
				else if (slot == REQ_DET) send_det(tpcb);
				else if (slot < st[S_COL].nslot && st[S_COL].len[slot]) send_slot(tpcb, slot);
				ps.phase = PH_MAGIC;
			} else {
				u32 np[NPARAM]; memcpy(np, ps.hbuf + 4, 4 * NPARAM);
				u32 rst = np[P_RESET]; np[P_RESET] = 0;
				apply_params(np);
				if (rst) { img_reset_pending = 1; ir_reset_pending = 1; if (ev.active) { ev_close_chunk(2); ev_pump(); } ev.active = 0; memset(&ad, 0, sizeof ad); }
				xil_printf("CFG applied (reset=%u)\r\n", rst);
				ps.phase = PH_MAGIC;
			}
			ps.hgot = 0; if (ps.phase == PH_MAGIC) ps.hneed = 4;
			break;
		}
		case PH_PAYLOAD: {
			u32 take = ps.plen - ps.pgot;
			if (take > n) take = n;
			u8 *dst = slot_ptr(ps.stream, ps.slot) + ps.pgot;
			memcpy(dst, p, take);
			ps.crc = crc_update(ps.crc, p, take);
			ps.pgot += take; p += take; n -= take; bytes_rx += take;
			if (ps.pgot == ps.plen) { frame_done(); ps.phase = PH_MAGIC; ps.hgot = 0; ps.hneed = 4; }
			break;
		}
		case PH_SKIP: {
			u32 take = ps.plen - ps.pgot;
			if (take > n) take = n;
			ps.pgot += take; p += take; n -= take;
			if (ps.pgot == ps.plen) { ps.phase = PH_MAGIC; ps.hgot = 0; ps.hneed = 4; }
			break;
		}
		}
	}
}

static err_t sent_cb(void *arg, struct tcp_pcb *tpcb, u16_t len)
{
	if (tx.active) tx_pump(tpcb);
	return ERR_OK;
}

static err_t recv_cb(void *arg, struct tcp_pcb *tpcb, struct pbuf *p, err_t err)
{
	if (!p) {
		xil_printf("client closed: colour frames=%u crc_err=%u\r\n", st[S_COL].count, crc_err);
		parser_reset(); tx.active = 0;
		tcp_close(tpcb);
		return ERR_OK;
	}
	tcp_recved(tpcb, p->tot_len);
	for (struct pbuf *q = p; q; q = q->next) feed(tpcb, (const u8 *)q->payload, q->len);
	pbuf_free(p);
	return ERR_OK;
}

static void err_cb(void *arg, err_t err) { parser_reset(); tx.active = 0; }

static err_t accept_cb(void *arg, struct tcp_pcb *newpcb, err_t err)
{
	xil_printf("relay connected\r\n");
	parser_reset(); tx.active = 0;
	img_reset_pending = 1; ir_reset_pending = 1;
	if (ev.active) { ev_close_chunk(2); ev_pump(); ev.active = 0; }
	tcp_nagle_disable(newpcb);
	tcp_recv(newpcb, recv_cb);
	tcp_sent(newpcb, sent_cb);
	tcp_err(newpcb, err_cb);
	return ERR_OK;
}

/* ---- :5001 GPU client ---- */
static err_t evt_sent_cb(void *arg, struct tcp_pcb *tpcb, u16_t len) { ev_pump(); return ERR_OK; }
static err_t evt_recv_cb(void *arg, struct tcp_pcb *tpcb, struct pbuf *p, err_t err)
{
	if (!p) { xil_printf("GPU client closed\r\n"); if (evt_pcb == tpcb) { evt_pcb = NULL; ev_reset_stream(); } tcp_close(tpcb); return ERR_OK; }
	tcp_recved(tpcb, p->tot_len); pbuf_free(p);
	return ERR_OK;
}
static void evt_err_cb(void *arg, err_t err) { evt_pcb = NULL; ev_reset_stream(); }
static err_t evt_accept_cb(void *arg, struct tcp_pcb *newpcb, err_t err)
{
	if (evt_pcb) tcp_abort(evt_pcb);
	ev_reset_stream();
	evt_pcb = newpcb;
	xil_printf("GPU client connected on :5001\r\n");
	tcp_nagle_disable(newpcb);
	tcp_recv(newpcb, evt_recv_cb);
	tcp_sent(newpcb, evt_sent_cb);
	tcp_err(newpcb, evt_err_cb);
	return ERR_OK;
}

static struct tcp_pcb *listen_on(u16_t port, tcp_accept_fn fn)
{
	struct tcp_pcb *pcb = tcp_new_ip_type(IPADDR_TYPE_ANY);
	if (!pcb || tcp_bind(pcb, IP_ANY_TYPE, port) != ERR_OK) { xil_printf("ERROR: tcp bind %u failed\r\n", port); return NULL; }
	pcb = tcp_listen(pcb);
	tcp_accept(pcb, fn);
	return pcb;
}

int main(void)
{
	ip_addr_t ipaddr, netmask, gw;
	unsigned char mac[6] = {0x00, 0x0a, 0x35, 0x00, 0x01, 0x02};
	XTime t_last, t_now;
	u32 last_printed = 0xFFFFFFFFU;

	enable_mdio_pins();
	init_platform();
	crc_init(); parser_reset();
	xil_printf("\r\nEventCam board up (Step 2c: PL detectors + trigger + events)\r\n");
	xil_printf("rings: colour %u x %u B @0x%08x, IR %u x %u B @0x%08x, audio %u x %u B @0x%08x\r\n",
	           st[0].nslot, (unsigned)st[0].fbytes, (unsigned)st[0].base, st[1].nslot, (unsigned)st[1].fbytes, (unsigned)st[1].base,
	           st[2].nslot, (unsigned)st[2].fbytes, (unsigned)st[2].base);
	xil_printf("PL: image_change %08x, change_ir %08x, audio_bands %08x\r\n", (unsigned)IMG_BASE, (unsigned)IR_BASE, (unsigned)AUD_BASE);

	IP4_ADDR(&ipaddr, 192, 168, 7, 2);
	IP4_ADDR(&netmask, 255, 255, 255, 0);
	IP4_ADDR(&gw, 192, 168, 7, 1);

	lwip_init();
	if (!xemac_add(&server_netif, &ipaddr, &netmask, &gw, mac, PLATFORM_EMAC_BASEADDR)) {
		xil_printf("ERROR: xemac_add failed\r\n");
		return -1;
	}
	netif_set_default(&server_netif);
	platform_enable_interrupts();
	netif_set_up(&server_netif);
	xil_printf("board IP 192.168.7.2, listening on TCP 5000 (frames) and 5001 (events)\r\n");
	if (!listen_on(5000, accept_cb) || !listen_on(5001, evt_accept_cb)) return -1;

	XTime_GetTime(&t_last);
	while (1) {
		if (TcpFastTmrFlag) { tcp_fasttmr(); TcpFastTmrFlag = 0; }
		if (TcpSlowTmrFlag) { tcp_slowtmr(); TcpSlowTmrFlag = 0; }
		xemacif_input(&server_netif);
		ev_pump();
		XTime_GetTime(&t_now);
		if (t_now - t_last > 5ULL * COUNTS_PER_SECOND) {
			t_last = t_now;
			if (st[S_COL].count != last_printed) {
				last_printed = st[S_COL].count;
				xil_printf("col=%u ir=%u aud=%u crc_err=%u bad_len=%u gaps=%u | img reason %u score %u changed %u | onsets %u chunks %u frames_sent %u lost %u no_client %u\r\n",
				           st[S_COL].count, ir_rx, aud_rx, crc_err, bad_len, fid_gaps, img.reason, img.score, img.changed, onsets, ev.chunks_sent, ev.frames_sent, ev.frames_lost, ev.episodes_dropped);
			}
		}
	}
	return 0;
}
