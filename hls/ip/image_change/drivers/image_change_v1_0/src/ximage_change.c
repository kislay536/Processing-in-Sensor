// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2024.2 (64-bit)
// Tool Version Limit: 2024.11
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2024 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================
/***************************** Include Files *********************************/
#include "ximage_change.h"

/************************** Function Implementation *************************/
#ifndef __linux__
int XImage_change_CfgInitialize(XImage_change *InstancePtr, XImage_change_Config *ConfigPtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(ConfigPtr != NULL);

    InstancePtr->Ctrl_BaseAddress = ConfigPtr->Ctrl_BaseAddress;
    InstancePtr->IsReady = XIL_COMPONENT_IS_READY;

    return XST_SUCCESS;
}
#endif

void XImage_change_Start(XImage_change *InstancePtr) {
    u32 Data;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImage_change_ReadReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_AP_CTRL) & 0x80;
    XImage_change_WriteReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_AP_CTRL, Data | 0x01);
}

u32 XImage_change_IsDone(XImage_change *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImage_change_ReadReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_AP_CTRL);
    return (Data >> 1) & 0x1;
}

u32 XImage_change_IsIdle(XImage_change *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImage_change_ReadReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_AP_CTRL);
    return (Data >> 2) & 0x1;
}

u32 XImage_change_IsReady(XImage_change *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImage_change_ReadReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_AP_CTRL);
    // check ap_start to see if the pcore is ready for next input
    return !(Data & 0x1);
}

void XImage_change_EnableAutoRestart(XImage_change *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XImage_change_WriteReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_AP_CTRL, 0x80);
}

void XImage_change_DisableAutoRestart(XImage_change *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XImage_change_WriteReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_AP_CTRL, 0);
}

void XImage_change_Set_frame(XImage_change *InstancePtr, u64 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XImage_change_WriteReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_FRAME_DATA, (u32)(Data));
    XImage_change_WriteReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_FRAME_DATA + 4, (u32)(Data >> 32));
}

u64 XImage_change_Get_frame(XImage_change *InstancePtr) {
    u64 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImage_change_ReadReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_FRAME_DATA);
    Data += (u64)XImage_change_ReadReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_FRAME_DATA + 4) << 32;
    return Data;
}

void XImage_change_Set_pix_min(XImage_change *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XImage_change_WriteReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_PIX_MIN_DATA, Data);
}

u32 XImage_change_Get_pix_min(XImage_change *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImage_change_ReadReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_PIX_MIN_DATA);
    return Data;
}

void XImage_change_Set_var_init(XImage_change *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XImage_change_WriteReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_VAR_INIT_DATA, Data);
}

u32 XImage_change_Get_var_init(XImage_change *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImage_change_ReadReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_VAR_INIT_DATA);
    return Data;
}

void XImage_change_Set_var_min(XImage_change *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XImage_change_WriteReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_VAR_MIN_DATA, Data);
}

u32 XImage_change_Get_var_min(XImage_change *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImage_change_ReadReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_VAR_MIN_DATA);
    return Data;
}

void XImage_change_Set_var_max(XImage_change *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XImage_change_WriteReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_VAR_MAX_DATA, Data);
}

u32 XImage_change_Get_var_max(XImage_change *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImage_change_ReadReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_VAR_MAX_DATA);
    return Data;
}

void XImage_change_Set_var_shift(XImage_change *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XImage_change_WriteReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_VAR_SHIFT_DATA, Data);
}

u32 XImage_change_Get_var_shift(XImage_change *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImage_change_ReadReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_VAR_SHIFT_DATA);
    return Data;
}

void XImage_change_Set_min_cells(XImage_change *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XImage_change_WriteReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_MIN_CELLS_DATA, Data);
}

u32 XImage_change_Get_min_cells(XImage_change *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImage_change_ReadReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_MIN_CELLS_DATA);
    return Data;
}

void XImage_change_Set_persist_frames(XImage_change *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XImage_change_WriteReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_PERSIST_FRAMES_DATA, Data);
}

u32 XImage_change_Get_persist_frames(XImage_change *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImage_change_ReadReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_PERSIST_FRAMES_DATA);
    return Data;
}

void XImage_change_Set_freeze_frames(XImage_change *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XImage_change_WriteReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_FREEZE_FRAMES_DATA, Data);
}

u32 XImage_change_Get_freeze_frames(XImage_change *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImage_change_ReadReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_FREEZE_FRAMES_DATA);
    return Data;
}

void XImage_change_Set_illum_en(XImage_change *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XImage_change_WriteReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_ILLUM_EN_DATA, Data);
}

u32 XImage_change_Get_illum_en(XImage_change *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImage_change_ReadReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_ILLUM_EN_DATA);
    return Data;
}

void XImage_change_Set_illum_min(XImage_change *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XImage_change_WriteReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_ILLUM_MIN_DATA, Data);
}

u32 XImage_change_Get_illum_min(XImage_change *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImage_change_ReadReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_ILLUM_MIN_DATA);
    return Data;
}

void XImage_change_Set_cell_req(XImage_change *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XImage_change_WriteReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_CELL_REQ_DATA, Data);
}

u32 XImage_change_Get_cell_req(XImage_change *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImage_change_ReadReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_CELL_REQ_DATA);
    return Data;
}

void XImage_change_Set_global_limit(XImage_change *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XImage_change_WriteReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_GLOBAL_LIMIT_DATA, Data);
}

u32 XImage_change_Get_global_limit(XImage_change *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImage_change_ReadReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_GLOBAL_LIMIT_DATA);
    return Data;
}

void XImage_change_Set_resid_limit(XImage_change *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XImage_change_WriteReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_RESID_LIMIT_DATA, Data);
}

u32 XImage_change_Get_resid_limit(XImage_change *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImage_change_ReadReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_RESID_LIMIT_DATA);
    return Data;
}

void XImage_change_Set_reset(XImage_change *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XImage_change_WriteReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_RESET_DATA, Data);
}

u32 XImage_change_Get_reset(XImage_change *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImage_change_ReadReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_RESET_DATA);
    return Data;
}

u32 XImage_change_Get_fired(XImage_change *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImage_change_ReadReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_FIRED_DATA);
    return Data;
}

u32 XImage_change_Get_fired_vld(XImage_change *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImage_change_ReadReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_FIRED_CTRL);
    return Data & 0x1;
}

u32 XImage_change_Get_reason(XImage_change *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImage_change_ReadReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_REASON_DATA);
    return Data;
}

u32 XImage_change_Get_reason_vld(XImage_change *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImage_change_ReadReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_REASON_CTRL);
    return Data & 0x1;
}

u32 XImage_change_Get_score(XImage_change *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImage_change_ReadReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_SCORE_DATA);
    return Data;
}

u32 XImage_change_Get_score_vld(XImage_change *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImage_change_ReadReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_SCORE_CTRL);
    return Data & 0x1;
}

u32 XImage_change_Get_region_pass(XImage_change *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImage_change_ReadReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_REGION_PASS_DATA);
    return Data;
}

u32 XImage_change_Get_region_pass_vld(XImage_change *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImage_change_ReadReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_REGION_PASS_CTRL);
    return Data & 0x1;
}

u32 XImage_change_Get_active_out(XImage_change *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImage_change_ReadReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_ACTIVE_OUT_DATA);
    return Data;
}

u32 XImage_change_Get_active_out_vld(XImage_change *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImage_change_ReadReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_ACTIVE_OUT_CTRL);
    return Data & 0x1;
}

u32 XImage_change_Get_changed_out(XImage_change *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImage_change_ReadReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_CHANGED_OUT_DATA);
    return Data;
}

u32 XImage_change_Get_changed_out_vld(XImage_change *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImage_change_ReadReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_CHANGED_OUT_CTRL);
    return Data & 0x1;
}

u32 XImage_change_Get_persist_out(XImage_change *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImage_change_ReadReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_PERSIST_OUT_DATA);
    return Data;
}

u32 XImage_change_Get_persist_out_vld(XImage_change *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImage_change_ReadReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_PERSIST_OUT_CTRL);
    return Data & 0x1;
}

u32 XImage_change_Get_frames_out(XImage_change *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImage_change_ReadReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_FRAMES_OUT_DATA);
    return Data;
}

u32 XImage_change_Get_frames_out_vld(XImage_change *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImage_change_ReadReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_FRAMES_OUT_CTRL);
    return Data & 0x1;
}

u32 XImage_change_Get_cell_counts_BaseAddress(XImage_change *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return (InstancePtr->Ctrl_BaseAddress + XIMAGE_CHANGE_CTRL_ADDR_CELL_COUNTS_BASE);
}

u32 XImage_change_Get_cell_counts_HighAddress(XImage_change *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return (InstancePtr->Ctrl_BaseAddress + XIMAGE_CHANGE_CTRL_ADDR_CELL_COUNTS_HIGH);
}

u32 XImage_change_Get_cell_counts_TotalBytes(XImage_change *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return (XIMAGE_CHANGE_CTRL_ADDR_CELL_COUNTS_HIGH - XIMAGE_CHANGE_CTRL_ADDR_CELL_COUNTS_BASE + 1);
}

u32 XImage_change_Get_cell_counts_BitWidth(XImage_change *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return XIMAGE_CHANGE_CTRL_WIDTH_CELL_COUNTS;
}

u32 XImage_change_Get_cell_counts_Depth(XImage_change *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return XIMAGE_CHANGE_CTRL_DEPTH_CELL_COUNTS;
}

u32 XImage_change_Write_cell_counts_Words(XImage_change *InstancePtr, int offset, word_type *data, int length) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr -> IsReady == XIL_COMPONENT_IS_READY);

    int i;

    if ((offset + length)*4 > (XIMAGE_CHANGE_CTRL_ADDR_CELL_COUNTS_HIGH - XIMAGE_CHANGE_CTRL_ADDR_CELL_COUNTS_BASE + 1))
        return 0;

    for (i = 0; i < length; i++) {
        *(int *)(InstancePtr->Ctrl_BaseAddress + XIMAGE_CHANGE_CTRL_ADDR_CELL_COUNTS_BASE + (offset + i)*4) = *(data + i);
    }
    return length;
}

u32 XImage_change_Read_cell_counts_Words(XImage_change *InstancePtr, int offset, word_type *data, int length) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr -> IsReady == XIL_COMPONENT_IS_READY);

    int i;

    if ((offset + length)*4 > (XIMAGE_CHANGE_CTRL_ADDR_CELL_COUNTS_HIGH - XIMAGE_CHANGE_CTRL_ADDR_CELL_COUNTS_BASE + 1))
        return 0;

    for (i = 0; i < length; i++) {
        *(data + i) = *(int *)(InstancePtr->Ctrl_BaseAddress + XIMAGE_CHANGE_CTRL_ADDR_CELL_COUNTS_BASE + (offset + i)*4);
    }
    return length;
}

u32 XImage_change_Write_cell_counts_Bytes(XImage_change *InstancePtr, int offset, char *data, int length) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr -> IsReady == XIL_COMPONENT_IS_READY);

    int i;

    if ((offset + length) > (XIMAGE_CHANGE_CTRL_ADDR_CELL_COUNTS_HIGH - XIMAGE_CHANGE_CTRL_ADDR_CELL_COUNTS_BASE + 1))
        return 0;

    for (i = 0; i < length; i++) {
        *(char *)(InstancePtr->Ctrl_BaseAddress + XIMAGE_CHANGE_CTRL_ADDR_CELL_COUNTS_BASE + offset + i) = *(data + i);
    }
    return length;
}

u32 XImage_change_Read_cell_counts_Bytes(XImage_change *InstancePtr, int offset, char *data, int length) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr -> IsReady == XIL_COMPONENT_IS_READY);

    int i;

    if ((offset + length) > (XIMAGE_CHANGE_CTRL_ADDR_CELL_COUNTS_HIGH - XIMAGE_CHANGE_CTRL_ADDR_CELL_COUNTS_BASE + 1))
        return 0;

    for (i = 0; i < length; i++) {
        *(data + i) = *(char *)(InstancePtr->Ctrl_BaseAddress + XIMAGE_CHANGE_CTRL_ADDR_CELL_COUNTS_BASE + offset + i);
    }
    return length;
}

void XImage_change_InterruptGlobalEnable(XImage_change *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XImage_change_WriteReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_GIE, 1);
}

void XImage_change_InterruptGlobalDisable(XImage_change *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XImage_change_WriteReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_GIE, 0);
}

void XImage_change_InterruptEnable(XImage_change *InstancePtr, u32 Mask) {
    u32 Register;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Register =  XImage_change_ReadReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_IER);
    XImage_change_WriteReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_IER, Register | Mask);
}

void XImage_change_InterruptDisable(XImage_change *InstancePtr, u32 Mask) {
    u32 Register;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Register =  XImage_change_ReadReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_IER);
    XImage_change_WriteReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_IER, Register & (~Mask));
}

void XImage_change_InterruptClear(XImage_change *InstancePtr, u32 Mask) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XImage_change_WriteReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_ISR, Mask);
}

u32 XImage_change_InterruptGetEnabled(XImage_change *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return XImage_change_ReadReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_IER);
}

u32 XImage_change_InterruptGetStatus(XImage_change *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return XImage_change_ReadReg(InstancePtr->Ctrl_BaseAddress, XIMAGE_CHANGE_CTRL_ADDR_ISR);
}

