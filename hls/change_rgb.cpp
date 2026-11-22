// Colour camera: YUYV 640x480 -> Y -> 128x96.
#include "change_core.h"
void change_rgb(const uint8_t *frame, uint8_t pix_thresh, uint8_t bg_shift, uint8_t reset,
                uint32_t &changed, uint32_t &sum_cur, uint32_t &score_x1000, uint32_t &frames)
{
#pragma HLS INTERFACE m_axi port=frame offset=slave bundle=gmem depth=614400 max_read_burst_length=64 num_read_outstanding=4
#pragma HLS INTERFACE s_axilite port=frame bundle=ctrl
#pragma HLS INTERFACE s_axilite port=pix_thresh bundle=ctrl
#pragma HLS INTERFACE s_axilite port=bg_shift bundle=ctrl
#pragma HLS INTERFACE s_axilite port=reset bundle=ctrl
#pragma HLS INTERFACE s_axilite port=changed bundle=ctrl
#pragma HLS INTERFACE s_axilite port=sum_cur bundle=ctrl
#pragma HLS INTERFACE s_axilite port=score_x1000 bundle=ctrl
#pragma HLS INTERFACE s_axilite port=frames bundle=ctrl
#pragma HLS INTERFACE s_axilite port=return bundle=ctrl
    static ap_uint<16> bg16[128 * 96];
    static uint32_t nframes = 0;
    change_core<640, 480, 2>(frame, pix_thresh, bg_shift, reset, bg16, nframes, changed, sum_cur, score_x1000);
    frames = nframes;
}
