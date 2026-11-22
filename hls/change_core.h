// Frame-change detector core, shared by the colour and IR tops.  Mirrors sensors/golden.py ChangeDetector exactly (integer arithmetic).
//   input  : frame in DDR (BPP=2: YUYV, Y = even bytes; BPP=1: 8-bit grey), W x H pixels
//   steps  : 5x5 box mean (floor) -> (W/5)x(H/5) image; |cur - (bg16>>4)| > pix_thresh counts as changed; bg16 += (cur*16 - bg16) >> bg_shift
//   output : number of changed pixels, sum of the downscaled image (mean brightness), changed per mille, running frame counter
#pragma once
#include <ap_int.h>
#include <stdint.h>
#include <string.h>

template <int W, int H, int BPP>
void change_core(const uint8_t *frame, uint8_t pix_thresh, uint8_t bg_shift, uint8_t reset,
                 ap_uint<16> *bg16, uint32_t &nframes,
                 uint32_t &changed_out, uint32_t &sum_out, uint32_t &score_out)
{
    constexpr int OW = W / 5, OH = H / 5;
    uint8_t buf[W * BPP];
#pragma HLS ARRAY_PARTITION variable=buf cyclic factor=10
    ap_uint<16> rowsum[OW];
    uint32_t changed = 0, sum_cur = 0;

    for (int r = 0; r < OH; r++) {
        for (int c = 0; c < OW; c++) rowsum[c] = 0;
        for (int j = 0; j < 5; j++) {
            memcpy(buf, frame + (size_t)(r * 5 + j) * (W * BPP), W * BPP);
            for (int c = 0; c < OW; c++) {
#pragma HLS PIPELINE II=1
                ap_uint<11> s = 0;
                for (int i = 0; i < 5; i++) s += buf[(c * 5 + i) * BPP];
                rowsum[c] += s;
            }
        }
        for (int c = 0; c < OW; c++) {
#pragma HLS PIPELINE II=2
            int idx = r * OW + c;
            ap_uint<8> cur = (ap_uint<16>)rowsum[c] / 25;
            ap_int<20> bg = reset ? (ap_int<20>)(cur * 16) : (ap_int<20>)bg16[idx];
            ap_uint<8> bgq = (ap_uint<8>)(bg >> 4);
            ap_uint<8> diff = cur > bgq ? (ap_uint<8>)(cur - bgq) : (ap_uint<8>)(bgq - cur);
            if (diff > pix_thresh) changed++;
            ap_int<20> upd = bg + (((ap_int<20>)(cur * 16) - bg) >> bg_shift);
            bg16[idx] = (ap_uint<16>)upd;
            sum_cur += cur;
        }
    }
    nframes++;
    changed_out = changed;
    sum_out = sum_cur;
    score_out = (changed * 1000) / (OW * OH);
}
