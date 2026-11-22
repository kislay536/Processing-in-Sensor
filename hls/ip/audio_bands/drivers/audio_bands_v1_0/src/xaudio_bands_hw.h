// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2024.2 (64-bit)
// Tool Version Limit: 2024.11
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2024 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================
// ctrl
// 0x00 : Control signals
//        bit 0  - ap_start (Read/Write/COH)
//        bit 1  - ap_done (Read/COR)
//        bit 2  - ap_idle (Read)
//        bit 3  - ap_ready (Read/COR)
//        bit 7  - auto_restart (Read/Write)
//        bit 9  - interrupt (Read)
//        others - reserved
// 0x04 : Global Interrupt Enable Register
//        bit 0  - Global Interrupt Enable (Read/Write)
//        others - reserved
// 0x08 : IP Interrupt Enable Register (Read/Write)
//        bit 0 - enable ap_done interrupt (Read/Write)
//        bit 1 - enable ap_ready interrupt (Read/Write)
//        others - reserved
// 0x0c : IP Interrupt Status Register (Read/TOW)
//        bit 0 - ap_done (Read/TOW)
//        bit 1 - ap_ready (Read/TOW)
//        others - reserved
// 0x10 : Data signal of samples
//        bit 31~0 - samples[31:0] (Read/Write)
// 0x14 : Data signal of samples
//        bit 31~0 - samples[63:32] (Read/Write)
// 0x18 : reserved
// 0x1c : Data signal of sum_sq
//        bit 31~0 - sum_sq[31:0] (Read)
// 0x20 : Data signal of sum_sq
//        bit 31~0 - sum_sq[63:32] (Read)
// 0x24 : Control signal of sum_sq
//        bit 0  - sum_sq_ap_vld (Read/COR)
//        others - reserved
// 0x80 : Data signal of blocks
//        bit 31~0 - blocks[31:0] (Read)
// 0x84 : Control signal of blocks
//        bit 0  - blocks_ap_vld (Read/COR)
//        others - reserved
// 0x40 ~
// 0x7f : Memory 'band' (8 * 64b)
//        Word 2n   : bit [31:0] - band[n][31: 0]
//        Word 2n+1 : bit [31:0] - band[n][63:32]
// (SC = Self Clear, COR = Clear on Read, TOW = Toggle on Write, COH = Clear on Handshake)

#define XAUDIO_BANDS_CTRL_ADDR_AP_CTRL      0x00
#define XAUDIO_BANDS_CTRL_ADDR_GIE          0x04
#define XAUDIO_BANDS_CTRL_ADDR_IER          0x08
#define XAUDIO_BANDS_CTRL_ADDR_ISR          0x0c
#define XAUDIO_BANDS_CTRL_ADDR_SAMPLES_DATA 0x10
#define XAUDIO_BANDS_CTRL_BITS_SAMPLES_DATA 64
#define XAUDIO_BANDS_CTRL_ADDR_SUM_SQ_DATA  0x1c
#define XAUDIO_BANDS_CTRL_BITS_SUM_SQ_DATA  64
#define XAUDIO_BANDS_CTRL_ADDR_SUM_SQ_CTRL  0x24
#define XAUDIO_BANDS_CTRL_ADDR_BLOCKS_DATA  0x80
#define XAUDIO_BANDS_CTRL_BITS_BLOCKS_DATA  32
#define XAUDIO_BANDS_CTRL_ADDR_BLOCKS_CTRL  0x84
#define XAUDIO_BANDS_CTRL_ADDR_BAND_BASE    0x40
#define XAUDIO_BANDS_CTRL_ADDR_BAND_HIGH    0x7f
#define XAUDIO_BANDS_CTRL_WIDTH_BAND        64
#define XAUDIO_BANDS_CTRL_DEPTH_BAND        8

