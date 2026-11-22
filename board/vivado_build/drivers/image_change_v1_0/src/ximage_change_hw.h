// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2024.2 (64-bit)
// Tool Version Limit: 2024.11
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2024 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================
// ctrl
// 0x000 : Control signals
//         bit 0  - ap_start (Read/Write/COH)
//         bit 1  - ap_done (Read/COR)
//         bit 2  - ap_idle (Read)
//         bit 3  - ap_ready (Read/COR)
//         bit 7  - auto_restart (Read/Write)
//         bit 9  - interrupt (Read)
//         others - reserved
// 0x004 : Global Interrupt Enable Register
//         bit 0  - Global Interrupt Enable (Read/Write)
//         others - reserved
// 0x008 : IP Interrupt Enable Register (Read/Write)
//         bit 0 - enable ap_done interrupt (Read/Write)
//         bit 1 - enable ap_ready interrupt (Read/Write)
//         others - reserved
// 0x00c : IP Interrupt Status Register (Read/TOW)
//         bit 0 - ap_done (Read/TOW)
//         bit 1 - ap_ready (Read/TOW)
//         others - reserved
// 0x010 : Data signal of frame
//         bit 31~0 - frame[31:0] (Read/Write)
// 0x014 : Data signal of frame
//         bit 31~0 - frame[63:32] (Read/Write)
// 0x018 : reserved
// 0x01c : Data signal of pix_min
//         bit 7~0 - pix_min[7:0] (Read/Write)
//         others  - reserved
// 0x020 : reserved
// 0x024 : Data signal of var_init
//         bit 7~0 - var_init[7:0] (Read/Write)
//         others  - reserved
// 0x028 : reserved
// 0x02c : Data signal of var_min
//         bit 7~0 - var_min[7:0] (Read/Write)
//         others  - reserved
// 0x030 : reserved
// 0x034 : Data signal of var_max
//         bit 7~0 - var_max[7:0] (Read/Write)
//         others  - reserved
// 0x038 : reserved
// 0x03c : Data signal of var_shift
//         bit 7~0 - var_shift[7:0] (Read/Write)
//         others  - reserved
// 0x040 : reserved
// 0x044 : Data signal of min_cells
//         bit 7~0 - min_cells[7:0] (Read/Write)
//         others  - reserved
// 0x048 : reserved
// 0x04c : Data signal of persist_frames
//         bit 15~0 - persist_frames[15:0] (Read/Write)
//         others   - reserved
// 0x050 : reserved
// 0x054 : Data signal of freeze_frames
//         bit 15~0 - freeze_frames[15:0] (Read/Write)
//         others   - reserved
// 0x058 : reserved
// 0x05c : Data signal of illum_en
//         bit 7~0 - illum_en[7:0] (Read/Write)
//         others  - reserved
// 0x060 : reserved
// 0x064 : Data signal of illum_min
//         bit 7~0 - illum_min[7:0] (Read/Write)
//         others  - reserved
// 0x068 : reserved
// 0x06c : Data signal of cell_req
//         bit 7~0 - cell_req[7:0] (Read/Write)
//         others  - reserved
// 0x070 : reserved
// 0x074 : Data signal of global_limit
//         bit 15~0 - global_limit[15:0] (Read/Write)
//         others   - reserved
// 0x078 : reserved
// 0x07c : Data signal of resid_limit
//         bit 15~0 - resid_limit[15:0] (Read/Write)
//         others   - reserved
// 0x080 : reserved
// 0x084 : Data signal of reset
//         bit 7~0 - reset[7:0] (Read/Write)
//         others  - reserved
// 0x088 : reserved
// 0x08c : Data signal of fired
//         bit 7~0 - fired[7:0] (Read)
//         others  - reserved
// 0x090 : Control signal of fired
//         bit 0  - fired_ap_vld (Read/COR)
//         others - reserved
// 0x09c : Data signal of reason
//         bit 7~0 - reason[7:0] (Read)
//         others  - reserved
// 0x0a0 : Control signal of reason
//         bit 0  - reason_ap_vld (Read/COR)
//         others - reserved
// 0x0ac : Data signal of score
//         bit 7~0 - score[7:0] (Read)
//         others  - reserved
// 0x0b0 : Control signal of score
//         bit 0  - score_ap_vld (Read/COR)
//         others - reserved
// 0x0bc : Data signal of region_pass
//         bit 7~0 - region_pass[7:0] (Read)
//         others  - reserved
// 0x0c0 : Control signal of region_pass
//         bit 0  - region_pass_ap_vld (Read/COR)
//         others - reserved
// 0x0cc : Data signal of active_out
//         bit 7~0 - active_out[7:0] (Read)
//         others  - reserved
// 0x0d0 : Control signal of active_out
//         bit 0  - active_out_ap_vld (Read/COR)
//         others - reserved
// 0x0dc : Data signal of changed_out
//         bit 15~0 - changed_out[15:0] (Read)
//         others   - reserved
// 0x0e0 : Control signal of changed_out
//         bit 0  - changed_out_ap_vld (Read/COR)
//         others - reserved
// 0x0ec : Data signal of persist_out
//         bit 15~0 - persist_out[15:0] (Read)
//         others   - reserved
// 0x0f0 : Control signal of persist_out
//         bit 0  - persist_out_ap_vld (Read/COR)
//         others - reserved
// 0x140 : Data signal of frames_out
//         bit 31~0 - frames_out[31:0] (Read)
// 0x144 : Control signal of frames_out
//         bit 0  - frames_out_ap_vld (Read/COR)
//         others - reserved
// 0x100 ~
// 0x13f : Memory 'cell_counts' (64 * 8b)
//         Word n : bit [ 7: 0] - cell_counts[4n]
//                  bit [15: 8] - cell_counts[4n+1]
//                  bit [23:16] - cell_counts[4n+2]
//                  bit [31:24] - cell_counts[4n+3]
// (SC = Self Clear, COR = Clear on Read, TOW = Toggle on Write, COH = Clear on Handshake)

#define XIMAGE_CHANGE_CTRL_ADDR_AP_CTRL             0x000
#define XIMAGE_CHANGE_CTRL_ADDR_GIE                 0x004
#define XIMAGE_CHANGE_CTRL_ADDR_IER                 0x008
#define XIMAGE_CHANGE_CTRL_ADDR_ISR                 0x00c
#define XIMAGE_CHANGE_CTRL_ADDR_FRAME_DATA          0x010
#define XIMAGE_CHANGE_CTRL_BITS_FRAME_DATA          64
#define XIMAGE_CHANGE_CTRL_ADDR_PIX_MIN_DATA        0x01c
#define XIMAGE_CHANGE_CTRL_BITS_PIX_MIN_DATA        8
#define XIMAGE_CHANGE_CTRL_ADDR_VAR_INIT_DATA       0x024
#define XIMAGE_CHANGE_CTRL_BITS_VAR_INIT_DATA       8
#define XIMAGE_CHANGE_CTRL_ADDR_VAR_MIN_DATA        0x02c
#define XIMAGE_CHANGE_CTRL_BITS_VAR_MIN_DATA        8
#define XIMAGE_CHANGE_CTRL_ADDR_VAR_MAX_DATA        0x034
#define XIMAGE_CHANGE_CTRL_BITS_VAR_MAX_DATA        8
#define XIMAGE_CHANGE_CTRL_ADDR_VAR_SHIFT_DATA      0x03c
#define XIMAGE_CHANGE_CTRL_BITS_VAR_SHIFT_DATA      8
#define XIMAGE_CHANGE_CTRL_ADDR_MIN_CELLS_DATA      0x044
#define XIMAGE_CHANGE_CTRL_BITS_MIN_CELLS_DATA      8
#define XIMAGE_CHANGE_CTRL_ADDR_PERSIST_FRAMES_DATA 0x04c
#define XIMAGE_CHANGE_CTRL_BITS_PERSIST_FRAMES_DATA 16
#define XIMAGE_CHANGE_CTRL_ADDR_FREEZE_FRAMES_DATA  0x054
#define XIMAGE_CHANGE_CTRL_BITS_FREEZE_FRAMES_DATA  16
#define XIMAGE_CHANGE_CTRL_ADDR_ILLUM_EN_DATA       0x05c
#define XIMAGE_CHANGE_CTRL_BITS_ILLUM_EN_DATA       8
#define XIMAGE_CHANGE_CTRL_ADDR_ILLUM_MIN_DATA      0x064
#define XIMAGE_CHANGE_CTRL_BITS_ILLUM_MIN_DATA      8
#define XIMAGE_CHANGE_CTRL_ADDR_CELL_REQ_DATA       0x06c
#define XIMAGE_CHANGE_CTRL_BITS_CELL_REQ_DATA       8
#define XIMAGE_CHANGE_CTRL_ADDR_GLOBAL_LIMIT_DATA   0x074
#define XIMAGE_CHANGE_CTRL_BITS_GLOBAL_LIMIT_DATA   16
#define XIMAGE_CHANGE_CTRL_ADDR_RESID_LIMIT_DATA    0x07c
#define XIMAGE_CHANGE_CTRL_BITS_RESID_LIMIT_DATA    16
#define XIMAGE_CHANGE_CTRL_ADDR_RESET_DATA          0x084
#define XIMAGE_CHANGE_CTRL_BITS_RESET_DATA          8
#define XIMAGE_CHANGE_CTRL_ADDR_FIRED_DATA          0x08c
#define XIMAGE_CHANGE_CTRL_BITS_FIRED_DATA          8
#define XIMAGE_CHANGE_CTRL_ADDR_FIRED_CTRL          0x090
#define XIMAGE_CHANGE_CTRL_ADDR_REASON_DATA         0x09c
#define XIMAGE_CHANGE_CTRL_BITS_REASON_DATA         8
#define XIMAGE_CHANGE_CTRL_ADDR_REASON_CTRL         0x0a0
#define XIMAGE_CHANGE_CTRL_ADDR_SCORE_DATA          0x0ac
#define XIMAGE_CHANGE_CTRL_BITS_SCORE_DATA          8
#define XIMAGE_CHANGE_CTRL_ADDR_SCORE_CTRL          0x0b0
#define XIMAGE_CHANGE_CTRL_ADDR_REGION_PASS_DATA    0x0bc
#define XIMAGE_CHANGE_CTRL_BITS_REGION_PASS_DATA    8
#define XIMAGE_CHANGE_CTRL_ADDR_REGION_PASS_CTRL    0x0c0
#define XIMAGE_CHANGE_CTRL_ADDR_ACTIVE_OUT_DATA     0x0cc
#define XIMAGE_CHANGE_CTRL_BITS_ACTIVE_OUT_DATA     8
#define XIMAGE_CHANGE_CTRL_ADDR_ACTIVE_OUT_CTRL     0x0d0
#define XIMAGE_CHANGE_CTRL_ADDR_CHANGED_OUT_DATA    0x0dc
#define XIMAGE_CHANGE_CTRL_BITS_CHANGED_OUT_DATA    16
#define XIMAGE_CHANGE_CTRL_ADDR_CHANGED_OUT_CTRL    0x0e0
#define XIMAGE_CHANGE_CTRL_ADDR_PERSIST_OUT_DATA    0x0ec
#define XIMAGE_CHANGE_CTRL_BITS_PERSIST_OUT_DATA    16
#define XIMAGE_CHANGE_CTRL_ADDR_PERSIST_OUT_CTRL    0x0f0
#define XIMAGE_CHANGE_CTRL_ADDR_FRAMES_OUT_DATA     0x140
#define XIMAGE_CHANGE_CTRL_BITS_FRAMES_OUT_DATA     32
#define XIMAGE_CHANGE_CTRL_ADDR_FRAMES_OUT_CTRL     0x144
#define XIMAGE_CHANGE_CTRL_ADDR_CELL_COUNTS_BASE    0x100
#define XIMAGE_CHANGE_CTRL_ADDR_CELL_COUNTS_HIGH    0x13f
#define XIMAGE_CHANGE_CTRL_WIDTH_CELL_COUNTS        8
#define XIMAGE_CHANGE_CTRL_DEPTH_CELL_COUNTS        64

