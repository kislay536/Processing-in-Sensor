// Testbench: image_change vs the Python golden model (image_detector.ImageChangeDetector), bit-exact on every output.
// Frames are stored compactly: only rows 112..367 of each 640x480 YUYV frame (256 x 1280 B); the testbench places them back.
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <vector>
void image_change(const uint8_t *, uint8_t, uint8_t, uint8_t, uint8_t, uint8_t, uint8_t, uint16_t, uint16_t, uint8_t, uint8_t,
                  uint8_t, uint16_t, uint16_t, uint8_t, uint8_t &, uint8_t &, uint8_t &, uint8_t &, uint8_t &, uint16_t &,
                  uint16_t &, uint8_t[64], uint32_t &);
#define CROP_BYTES (256 * 1280)
int main()
{
    char p[512];
    snprintf(p, sizeof p, "%s/image_frames.bin", getenv("VEC_DIR")); FILE *fb = fopen(p, "rb");
    snprintf(p, sizeof p, "%s/image_exp.txt", getenv("VEC_DIR")); FILE *fe = fopen(p, "r");
    if (!fb || !fe) { printf("cannot open vectors\n"); return 2; }
    std::vector<uint8_t> full(614400, 0), crop(CROP_BYTES);
    int n = 0, bad = 0;
    unsigned a[14], e[8], ec[64];
    while (fscanf(fe, "%u %u %u %u %u %u %u %u %u %u %u %u %u %u", &a[0], &a[1], &a[2], &a[3], &a[4], &a[5], &a[6], &a[7], &a[8], &a[9], &a[10], &a[11], &a[12], &a[13]) == 14) {
        for (int i = 0; i < 8; i++) if (fscanf(fe, "%u", &e[i]) != 1) return 2;
        for (int i = 0; i < 64; i++) if (fscanf(fe, "%u", &ec[i]) != 1) return 2;
        if (fread(crop.data(), 1, CROP_BYTES, fb) != CROP_BYTES) { printf("short frame file\n"); return 2; }
        memcpy(&full[112 * 1280], crop.data(), CROP_BYTES);
        uint8_t fired, reason, score, rp, act, cells[64]; uint16_t ch, pers; uint32_t fr;
        image_change(full.data() + 112 * 1280 + 128, a[0], a[1], a[2], a[3], a[4], a[5], a[6], a[7], a[8], a[9], a[10], a[11], a[12], a[13],
                     fired, reason, score, rp, act, ch, pers, cells, fr);
        unsigned got[8] = {fired, reason, score, rp, act, ch, pers, fr};
        bool ok = true;
        for (int i = 0; i < 8; i++) ok &= got[i] == e[i];
        for (int i = 0; i < 64; i++) ok &= cells[i] == ec[i];
        if (!ok) {
            bad++;
            printf("frame %d MISMATCH: fired %u/%u reason %u/%u score %u/%u rp %u/%u active %u/%u changed %u/%u pers %u/%u frames %u/%u (got/exp)\n",
                   n, got[0], e[0], got[1], e[1], got[2], e[2], got[3], e[3], got[4], e[4], got[5], e[5], got[6], e[6], got[7], e[7]);
        }
        n++;
    }
    printf("image: %d frames compared, %d mismatches\n", n, bad);
    return bad ? 1 : 0;
}
