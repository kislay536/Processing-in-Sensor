#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <vector>
void audio_bands(const int16_t *, int64_t[8], uint64_t &, uint32_t &);
int main()
{
    char p[512];
    snprintf(p, sizeof p, "%s/audio_blocks.bin", getenv("VEC_DIR")); FILE *fb = fopen(p, "rb");
    snprintf(p, sizeof p, "%s/audio_exp.txt", getenv("VEC_DIR")); FILE *fe = fopen(p, "r");
    if (!fb || !fe) { printf("cannot open vectors\n"); return 2; }
    std::vector<int16_t> x(512);
    int n = 0, bad = 0;
    long long e[8], ess; unsigned eb;
    while (fscanf(fe, "%lld %lld %lld %lld %lld %lld %lld %lld %lld %u", &e[0], &e[1], &e[2], &e[3], &e[4], &e[5], &e[6], &e[7], &ess, &eb) == 10) {
        if (fread(x.data(), 2, 512, fb) != 512) { printf("short file\n"); return 2; }
        int64_t band[8]; uint64_t ss; uint32_t blocks;
        audio_bands(x.data(), band, ss, blocks);
        bool ok = (long long)ss == ess && blocks == eb;
        for (int k = 0; k < 8; k++) ok = ok && band[k] == e[k];
        if (!ok) { bad++; printf("block %d MISMATCH\n", n); for (int k = 0; k < 8; k++) printf("  band%d got %lld exp %lld\n", k, (long long)band[k], e[k]); }
        n++;
    }
    printf("audio: %d blocks compared, %d mismatches\n", n, bad);
    return bad ? 1 : 0;
}
