// Microphone: 512 int16 samples (32 ms at 16 kHz) -> 8 band powers via integer Goertzel (3 adjacent 31.25 Hz bins per band) + sum of squares.
// Mirrors sensors/golden.py goertzel_bands exactly.  Bands (Hz): 125 250 500 1000 2000 3000 4000 6000.
#include <ap_int.h>
#include <stdint.h>
#include <string.h>

static const int N = 512;
static const int NF = 24;
static const int COEF[NF] = {
#include "goertzel_coefs.inc"
};

void audio_bands(const int16_t *samples, int64_t band[8], uint64_t &sum_sq, uint32_t &blocks)
{
#pragma HLS INTERFACE m_axi port=samples offset=slave bundle=gmem depth=512 max_read_burst_length=64
#pragma HLS INTERFACE s_axilite port=samples bundle=ctrl
#pragma HLS INTERFACE s_axilite port=band bundle=ctrl
#pragma HLS INTERFACE s_axilite port=sum_sq bundle=ctrl
#pragma HLS INTERFACE s_axilite port=blocks bundle=ctrl
#pragma HLS INTERFACE s_axilite port=return bundle=ctrl
    static uint32_t nblocks = 0;
    int16_t x[N];
    memcpy(x, samples, N * sizeof(int16_t));
    ap_int<40> s1[NF], s2[NF];
    for (int f = 0; f < NF; f++) { s1[f] = 0; s2[f] = 0; }
    ap_uint<64> ss = 0;
    for (int n = 0; n < N; n++) {
        ap_int<16> v = x[n];
        ss += (ap_uint<32>)(v * v);
        for (int f = 0; f < NF; f++) {
#pragma HLS PIPELINE II=1
#pragma HLS DEPENDENCE variable=s1 inter false
#pragma HLS DEPENDENCE variable=s2 inter false
            ap_int<40> a = s1[f], b = s2[f];
            ap_int<56> prod = (ap_int<17>)COEF[f] * a;
            ap_int<40> s0 = v + (ap_int<40>)(prod >> 14) - b;
            s2[f] = a;
            s1[f] = s0;
        }
    }
    int64_t out[8];
    for (int k = 0; k < 8; k++) out[k] = 0;
    for (int f = 0; f < NF; f++) {
        ap_int<110> a = s1[f], b = s2[f];
        ap_int<110> prod = ((ap_int<110>)((ap_int<17>)COEF[f]) * a * b) >> 14;
        ap_int<110> p = a * a + b * b - prod;
        out[f / 3] += (int64_t)p;
    }
    for (int k = 0; k < 8; k++) band[k] = out[k];
    sum_sq = ss;
    nblocks++;
    blocks = nblocks;
}
