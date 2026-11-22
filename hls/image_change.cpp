// Full image-change detector in the PL (colour camera).  Mirrors image-change-detector/src/image_detector/detector.py
// (sigma-delta background, ROI = whole frame) bit-exactly.
//   input : `frame` = DDR address of the FIRST PIXEL OF THE CROP (row 112, column 64 of a 640x480 YUYV frame, i.e. frame start + 143488).
//           (the host adds that constant: a constant that large in the pointer arithmetic wrapped as a signed 18-bit value in the
//           generated RTL and shifted the read window by -262144 bytes on the board.)  Y of the centre crop rows 112..367, columns 64..575 (512x256) is block-averaged
//           (8x4 pixels, sum >> 5) to a 64x64 grey image, like Preprocessor(256, 512, "gray").
//   state : background B and variation V (64x64 uint8 each, in BRAM), persistence, hold counter, initialised flag.
//   output: fired, reason (0 warmup,1 none,2 change,3 exposure rebase,4 global hold,5 global rebase), score, region_pass,
//           active cells, changed pixels, persistence, 8x8 cell counts, frame counter.
//   limits are precomputed by the host: cell_req = ceil(64*num/den), global_limit = floor(4096*num/den) (changed > limit
//   means a global change), resid_limit likewise for the exposure residual.
#include <ap_int.h>
#include <stdint.h>
#include <string.h>

#define NPIX 4096
enum { R_WARMUP = 0, R_NONE = 1, R_CHANGE = 2, R_EXPOSURE = 3, R_HOLD = 4, R_REBASE = 5 };

static int32_t shift_toward_zero(int32_t v, int s) { return v >= 0 ? (v >> s) : -((-v) >> s); }

void image_change(const uint8_t *frame,
                  uint8_t pix_min, uint8_t var_init, uint8_t var_min, uint8_t var_max, uint8_t var_shift,
                  uint8_t min_cells, uint16_t persist_frames, uint16_t freeze_frames,
                  uint8_t illum_en, uint8_t illum_min, uint8_t cell_req, uint16_t global_limit, uint16_t resid_limit,
                  uint8_t reset,
                  uint8_t &fired, uint8_t &reason, uint8_t &score, uint8_t &region_pass, uint8_t &active_out,
                  uint16_t &changed_out, uint16_t &persist_out, uint8_t cell_counts[64], uint32_t &frames_out)
{
#pragma HLS INTERFACE m_axi port=frame offset=slave bundle=gmem depth=614400 max_read_burst_length=64 num_read_outstanding=4
#pragma HLS INTERFACE s_axilite port=frame bundle=ctrl
#pragma HLS INTERFACE s_axilite port=pix_min bundle=ctrl
#pragma HLS INTERFACE s_axilite port=var_init bundle=ctrl
#pragma HLS INTERFACE s_axilite port=var_min bundle=ctrl
#pragma HLS INTERFACE s_axilite port=var_max bundle=ctrl
#pragma HLS INTERFACE s_axilite port=var_shift bundle=ctrl
#pragma HLS INTERFACE s_axilite port=min_cells bundle=ctrl
#pragma HLS INTERFACE s_axilite port=persist_frames bundle=ctrl
#pragma HLS INTERFACE s_axilite port=freeze_frames bundle=ctrl
#pragma HLS INTERFACE s_axilite port=illum_en bundle=ctrl
#pragma HLS INTERFACE s_axilite port=illum_min bundle=ctrl
#pragma HLS INTERFACE s_axilite port=cell_req bundle=ctrl
#pragma HLS INTERFACE s_axilite port=global_limit bundle=ctrl
#pragma HLS INTERFACE s_axilite port=resid_limit bundle=ctrl
#pragma HLS INTERFACE s_axilite port=reset bundle=ctrl
#pragma HLS INTERFACE s_axilite port=fired bundle=ctrl
#pragma HLS INTERFACE s_axilite port=reason bundle=ctrl
#pragma HLS INTERFACE s_axilite port=score bundle=ctrl
#pragma HLS INTERFACE s_axilite port=region_pass bundle=ctrl
#pragma HLS INTERFACE s_axilite port=active_out bundle=ctrl
#pragma HLS INTERFACE s_axilite port=changed_out bundle=ctrl
#pragma HLS INTERFACE s_axilite port=persist_out bundle=ctrl
#pragma HLS INTERFACE s_axilite port=cell_counts bundle=ctrl
#pragma HLS INTERFACE s_axilite port=frames_out bundle=ctrl
#pragma HLS INTERFACE s_axilite port=return bundle=ctrl
    static uint8_t B[NPIX], V[NPIX];
#pragma HLS BIND_STORAGE variable=B type=ram_2p impl=bram
#pragma HLS BIND_STORAGE variable=V type=ram_2p impl=bram
    static bool initialized = false;
    static uint16_t persistence = 0, hold = 0;
    static uint32_t nframes = 0;

    uint8_t cur[NPIX], Bn[NPIX], Vn[NPIX], cellc[64];
#pragma HLS BIND_STORAGE variable=cur type=ram_2p impl=bram
#pragma HLS BIND_STORAGE variable=Bn type=ram_2p impl=bram
#pragma HLS BIND_STORAGE variable=Vn type=ram_2p impl=bram

    // ---- 1. centre crop -> 64x64 grey (8 x 4 pixel blocks) ----
    {
        uint8_t buf[1024];
#pragma HLS ARRAY_PARTITION variable=buf cyclic factor=16
        ap_uint<13> colsum[64];
        for (int r = 0; r < 64; r++) {
            for (int c = 0; c < 64; c++) colsum[c] = 0;
            for (int j = 0; j < 4; j++) {
                memcpy(buf, frame + (size_t)(4 * r + j) * 1280, 1024);
                for (int c = 0; c < 64; c++) {
#pragma HLS PIPELINE II=1
                    ap_uint<11> s = 0;
                    for (int i = 0; i < 8; i++) s += buf[(c * 8 + i) * 2];
                    colsum[c] += s;
                }
            }
            for (int c = 0; c < 64; c++) cur[r * 64 + c] = (uint8_t)(colsum[c] >> 5);
        }
    }

    if (reset) { initialized = false; persistence = 0; hold = 0; nframes = 0; }
    nframes++;

    uint8_t rsn = R_NONE;
    bool fire = false, passed = false, report_cells = false;
    uint16_t act = 0, changed16 = 0;

    if (!initialized) {
        for (int i = 0; i < NPIX; i++) {
#pragma HLS PIPELINE II=1
            B[i] = cur[i]; V[i] = var_init;
        }
        initialized = true; persistence = 0; rsn = R_WARMUP;
    } else {
        // ---- 2. classify against the background; also prepare the adapted model ----
        uint32_t changed = 0;
        int32_t sumsigned = 0;
        for (int cr = 0; cr < 8; cr++) {
            for (int cc = 0; cc < 8; cc++) {
                uint8_t cnt = 0;
                for (int p = 0; p < 64; p++) {
#pragma HLS PIPELINE II=1
                    int idx = ((cr * 8 + (p >> 3)) << 6) + cc * 8 + (p & 7);
                    int b = B[idx], v = V[idx], x = cur[idx];
                    int thr = v << var_shift; if (thr < pix_min) thr = pix_min;
                    int s = x - b;
                    int res = s < 0 ? -s : s;
                    bool ch = res > thr;
                    cnt += ch; changed += ch; sumsigned += s;
                    int nb = b + (s > 0 ? 1 : 0) - (s < 0 ? 1 : 0);
                    int dv = res - v;
                    int nv = v + (dv > 0 ? 1 : 0) - (dv < 0 ? 1 : 0);
                    if (nv < var_min) nv = var_min;
                    if (nv > var_max) nv = var_max;
                    Bn[idx] = (uint8_t)nb; Vn[idx] = (uint8_t)nv;
                }
                cellc[cr * 8 + cc] = cnt;
            }
        }
        changed16 = (uint16_t)changed;

        if (hold) {
            hold--;
            persistence = 0;
            if (hold == 0) {
                for (int i = 0; i < NPIX; i++) {
#pragma HLS PIPELINE II=1
                    B[i] = cur[i]; V[i] = var_init;
                }
                rsn = R_REBASE;
            } else rsn = R_HOLD;
        } else if (changed > global_limit) {
            bool exp_ok = false;
            int32_t offset = shift_toward_zero(sumsigned, 12);
            if (illum_en && (offset < 0 ? -offset : offset) >= illum_min) {
                uint32_t rem = 0;
                for (int i = 0; i < NPIX; i++) {
#pragma HLS PIPELINE II=1
                    int cand = (int)B[i] + offset;
                    if (cand < 0) cand = 0;
                    if (cand > 255) cand = 255;
                    int d = (int)cur[i] - cand; if (d < 0) d = -d;
                    int thr = (int)V[i] << var_shift; if (thr < pix_min) thr = pix_min;
                    rem += (d > thr);
                }
                if (rem <= resid_limit) {
                    exp_ok = true;
                    for (int i = 0; i < NPIX; i++) {
#pragma HLS PIPELINE II=1
                        int cand = (int)B[i] + offset;
                        if (cand < 0) cand = 0;
                        if (cand > 255) cand = 255;
                        B[i] = (uint8_t)cand;
                    }
                }
            }
            persistence = 0;
            if (exp_ok) rsn = R_EXPOSURE;
            else { hold = freeze_frames; rsn = R_HOLD; }
        } else {
            // ---- 3. cells, region test, persistence ----
            bool a[8][8];
            for (int r = 0; r < 8; r++)
                for (int c = 0; c < 8; c++) {
                    a[r][c] = cellc[r * 8 + c] >= cell_req;
                    act += a[r][c];
                }
            bool pair = false;
            for (int r = 0; r < 8; r++)
                for (int c = 0; c < 8; c++) {
                    if (c < 7 && a[r][c] && a[r][c + 1]) pair = true;
                    if (r < 7 && a[r][c] && a[r + 1][c]) pair = true;
                }
            passed = (act >= min_cells) && pair;
            if (passed) { if (persistence < persist_frames) persistence++; } else persistence = 0;
            fire = (persistence == persist_frames);
            rsn = fire ? R_CHANGE : R_NONE;
            report_cells = true;
            for (int i = 0; i < NPIX; i++) {
#pragma HLS PIPELINE II=1
                B[i] = Bn[i]; V[i] = Vn[i];
            }
        }
    }

    for (int k = 0; k < 64; k++) cell_counts[k] = report_cells ? cellc[k] : (uint8_t)0;
    fired = fire; reason = rsn; region_pass = passed;
    active_out = (uint8_t)act;
    score = (uint8_t)((255 * act) >> 6);
    changed_out = changed16;
    persist_out = report_cells ? persistence : (uint16_t)0;
    frames_out = nframes;
}
