// Testbench: compare the HLS change detector with golden vectors (bit-exact).  Build with -DSENSOR_RGB or -DSENSOR_IR and -DVEC_DIR="..."
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <vector>
#ifdef SENSOR_RGB
#define FRAME_BYTES 614400
#define NAME "rgb"
void change_rgb(const uint8_t *, uint8_t, uint8_t, uint8_t, uint32_t &, uint32_t &, uint32_t &, uint32_t &);
#define DUT change_rgb
#else
#define FRAME_BYTES 230400
#define NAME "ir"
void change_ir(const uint8_t *, uint8_t, uint8_t, uint8_t, uint32_t &, uint32_t &, uint32_t &, uint32_t &);
#define DUT change_ir
#endif
int main()
{
    char p[512];
    snprintf(p, sizeof p, "%s/" NAME "_frames.bin", getenv("VEC_DIR")); FILE *fb = fopen(p, "rb");
    snprintf(p, sizeof p, "%s/" NAME "_exp.txt", getenv("VEC_DIR")); FILE *fe = fopen(p, "r");
    if (!fb || !fe) { printf("cannot open vectors\n"); return 2; }
    std::vector<uint8_t> buf(FRAME_BYTES);
    int n = 0, bad = 0;
    unsigned thr, sh, rst, ch, sum, sc, fr;
    while (fscanf(fe, "%u %u %u %u %u %u %u", &thr, &sh, &rst, &ch, &sum, &sc, &fr) == 7) {
        if (fread(buf.data(), 1, FRAME_BYTES, fb) != FRAME_BYTES) { printf("short frame file\n"); return 2; }
        uint32_t c, s, score, frames;
        DUT(buf.data(), thr, sh, rst, c, s, score, frames);
        if (c != ch || s != sum || score != sc || frames != fr) {
            bad++; printf("frame %d MISMATCH: changed %u (exp %u) sum %u (exp %u) score %u (exp %u) frames %u (exp %u)\n", n, c, ch, s, sum, score, sc, frames, fr);
        }
        n++;
    }
    printf("%s: %d frames compared, %d mismatches\n", NAME, n, bad);
    return bad ? 1 : 0;
}
