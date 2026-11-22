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
// 0x10 : Data signal of frame
//        bit 31~0 - frame[31:0] (Read/Write)
// 0x14 : Data signal of frame
//        bit 31~0 - frame[63:32] (Read/Write)
// 0x18 : reserved
// 0x1c : Data signal of pix_thresh
//        bit 7~0 - pix_thresh[7:0] (Read/Write)
//        others  - reserved
// 0x20 : reserved
// 0x24 : Data signal of bg_shift
//        bit 7~0 - bg_shift[7:0] (Read/Write)
//        others  - reserved
// 0x28 : reserved
// 0x2c : Data signal of reset
//        bit 7~0 - reset[7:0] (Read/Write)
//        others  - reserved
// 0x30 : reserved
// 0x34 : Data signal of changed
//        bit 31~0 - changed[31:0] (Read)
// 0x38 : Control signal of changed
//        bit 0  - changed_ap_vld (Read/COR)
//        others - reserved
// 0x44 : Data signal of sum_cur
//        bit 31~0 - sum_cur[31:0] (Read)
// 0x48 : Control signal of sum_cur
//        bit 0  - sum_cur_ap_vld (Read/COR)
//        others - reserved
// 0x54 : Data signal of score_x1000
//        bit 31~0 - score_x1000[31:0] (Read)
// 0x58 : Control signal of score_x1000
//        bit 0  - score_x1000_ap_vld (Read/COR)
//        others - reserved
// 0x64 : Data signal of frames
//        bit 31~0 - frames[31:0] (Read)
// 0x68 : Control signal of frames
//        bit 0  - frames_ap_vld (Read/COR)
//        others - reserved
// (SC = Self Clear, COR = Clear on Read, TOW = Toggle on Write, COH = Clear on Handshake)

#define XCHANGE_IR_CTRL_ADDR_AP_CTRL          0x00
#define XCHANGE_IR_CTRL_ADDR_GIE              0x04
#define XCHANGE_IR_CTRL_ADDR_IER              0x08
#define XCHANGE_IR_CTRL_ADDR_ISR              0x0c
#define XCHANGE_IR_CTRL_ADDR_FRAME_DATA       0x10
#define XCHANGE_IR_CTRL_BITS_FRAME_DATA       64
#define XCHANGE_IR_CTRL_ADDR_PIX_THRESH_DATA  0x1c
#define XCHANGE_IR_CTRL_BITS_PIX_THRESH_DATA  8
#define XCHANGE_IR_CTRL_ADDR_BG_SHIFT_DATA    0x24
#define XCHANGE_IR_CTRL_BITS_BG_SHIFT_DATA    8
#define XCHANGE_IR_CTRL_ADDR_RESET_DATA       0x2c
#define XCHANGE_IR_CTRL_BITS_RESET_DATA       8
#define XCHANGE_IR_CTRL_ADDR_CHANGED_DATA     0x34
#define XCHANGE_IR_CTRL_BITS_CHANGED_DATA     32
#define XCHANGE_IR_CTRL_ADDR_CHANGED_CTRL     0x38
#define XCHANGE_IR_CTRL_ADDR_SUM_CUR_DATA     0x44
#define XCHANGE_IR_CTRL_BITS_SUM_CUR_DATA     32
#define XCHANGE_IR_CTRL_ADDR_SUM_CUR_CTRL     0x48
#define XCHANGE_IR_CTRL_ADDR_SCORE_X1000_DATA 0x54
#define XCHANGE_IR_CTRL_BITS_SCORE_X1000_DATA 32
#define XCHANGE_IR_CTRL_ADDR_SCORE_X1000_CTRL 0x58
#define XCHANGE_IR_CTRL_ADDR_FRAMES_DATA      0x64
#define XCHANGE_IR_CTRL_BITS_FRAMES_DATA      32
#define XCHANGE_IR_CTRL_ADDR_FRAMES_CTRL      0x68

