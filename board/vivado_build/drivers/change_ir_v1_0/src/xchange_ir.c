// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2024.2 (64-bit)
// Tool Version Limit: 2024.11
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2024 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================
/***************************** Include Files *********************************/
#include "xchange_ir.h"

/************************** Function Implementation *************************/
#ifndef __linux__
int XChange_ir_CfgInitialize(XChange_ir *InstancePtr, XChange_ir_Config *ConfigPtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(ConfigPtr != NULL);

    InstancePtr->Ctrl_BaseAddress = ConfigPtr->Ctrl_BaseAddress;
    InstancePtr->IsReady = XIL_COMPONENT_IS_READY;

    return XST_SUCCESS;
}
#endif

void XChange_ir_Start(XChange_ir *InstancePtr) {
    u32 Data;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XChange_ir_ReadReg(InstancePtr->Ctrl_BaseAddress, XCHANGE_IR_CTRL_ADDR_AP_CTRL) & 0x80;
    XChange_ir_WriteReg(InstancePtr->Ctrl_BaseAddress, XCHANGE_IR_CTRL_ADDR_AP_CTRL, Data | 0x01);
}

u32 XChange_ir_IsDone(XChange_ir *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XChange_ir_ReadReg(InstancePtr->Ctrl_BaseAddress, XCHANGE_IR_CTRL_ADDR_AP_CTRL);
    return (Data >> 1) & 0x1;
}

u32 XChange_ir_IsIdle(XChange_ir *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XChange_ir_ReadReg(InstancePtr->Ctrl_BaseAddress, XCHANGE_IR_CTRL_ADDR_AP_CTRL);
    return (Data >> 2) & 0x1;
}

u32 XChange_ir_IsReady(XChange_ir *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XChange_ir_ReadReg(InstancePtr->Ctrl_BaseAddress, XCHANGE_IR_CTRL_ADDR_AP_CTRL);
    // check ap_start to see if the pcore is ready for next input
    return !(Data & 0x1);
}

void XChange_ir_EnableAutoRestart(XChange_ir *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XChange_ir_WriteReg(InstancePtr->Ctrl_BaseAddress, XCHANGE_IR_CTRL_ADDR_AP_CTRL, 0x80);
}

void XChange_ir_DisableAutoRestart(XChange_ir *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XChange_ir_WriteReg(InstancePtr->Ctrl_BaseAddress, XCHANGE_IR_CTRL_ADDR_AP_CTRL, 0);
}

void XChange_ir_Set_frame(XChange_ir *InstancePtr, u64 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XChange_ir_WriteReg(InstancePtr->Ctrl_BaseAddress, XCHANGE_IR_CTRL_ADDR_FRAME_DATA, (u32)(Data));
    XChange_ir_WriteReg(InstancePtr->Ctrl_BaseAddress, XCHANGE_IR_CTRL_ADDR_FRAME_DATA + 4, (u32)(Data >> 32));
}

u64 XChange_ir_Get_frame(XChange_ir *InstancePtr) {
    u64 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XChange_ir_ReadReg(InstancePtr->Ctrl_BaseAddress, XCHANGE_IR_CTRL_ADDR_FRAME_DATA);
    Data += (u64)XChange_ir_ReadReg(InstancePtr->Ctrl_BaseAddress, XCHANGE_IR_CTRL_ADDR_FRAME_DATA + 4) << 32;
    return Data;
}

void XChange_ir_Set_pix_thresh(XChange_ir *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XChange_ir_WriteReg(InstancePtr->Ctrl_BaseAddress, XCHANGE_IR_CTRL_ADDR_PIX_THRESH_DATA, Data);
}

u32 XChange_ir_Get_pix_thresh(XChange_ir *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XChange_ir_ReadReg(InstancePtr->Ctrl_BaseAddress, XCHANGE_IR_CTRL_ADDR_PIX_THRESH_DATA);
    return Data;
}

void XChange_ir_Set_bg_shift(XChange_ir *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XChange_ir_WriteReg(InstancePtr->Ctrl_BaseAddress, XCHANGE_IR_CTRL_ADDR_BG_SHIFT_DATA, Data);
}

u32 XChange_ir_Get_bg_shift(XChange_ir *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XChange_ir_ReadReg(InstancePtr->Ctrl_BaseAddress, XCHANGE_IR_CTRL_ADDR_BG_SHIFT_DATA);
    return Data;
}

void XChange_ir_Set_reset(XChange_ir *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XChange_ir_WriteReg(InstancePtr->Ctrl_BaseAddress, XCHANGE_IR_CTRL_ADDR_RESET_DATA, Data);
}

u32 XChange_ir_Get_reset(XChange_ir *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XChange_ir_ReadReg(InstancePtr->Ctrl_BaseAddress, XCHANGE_IR_CTRL_ADDR_RESET_DATA);
    return Data;
}

u32 XChange_ir_Get_changed(XChange_ir *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XChange_ir_ReadReg(InstancePtr->Ctrl_BaseAddress, XCHANGE_IR_CTRL_ADDR_CHANGED_DATA);
    return Data;
}

u32 XChange_ir_Get_changed_vld(XChange_ir *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XChange_ir_ReadReg(InstancePtr->Ctrl_BaseAddress, XCHANGE_IR_CTRL_ADDR_CHANGED_CTRL);
    return Data & 0x1;
}

u32 XChange_ir_Get_sum_cur(XChange_ir *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XChange_ir_ReadReg(InstancePtr->Ctrl_BaseAddress, XCHANGE_IR_CTRL_ADDR_SUM_CUR_DATA);
    return Data;
}

u32 XChange_ir_Get_sum_cur_vld(XChange_ir *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XChange_ir_ReadReg(InstancePtr->Ctrl_BaseAddress, XCHANGE_IR_CTRL_ADDR_SUM_CUR_CTRL);
    return Data & 0x1;
}

u32 XChange_ir_Get_score_x1000(XChange_ir *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XChange_ir_ReadReg(InstancePtr->Ctrl_BaseAddress, XCHANGE_IR_CTRL_ADDR_SCORE_X1000_DATA);
    return Data;
}

u32 XChange_ir_Get_score_x1000_vld(XChange_ir *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XChange_ir_ReadReg(InstancePtr->Ctrl_BaseAddress, XCHANGE_IR_CTRL_ADDR_SCORE_X1000_CTRL);
    return Data & 0x1;
}

u32 XChange_ir_Get_frames(XChange_ir *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XChange_ir_ReadReg(InstancePtr->Ctrl_BaseAddress, XCHANGE_IR_CTRL_ADDR_FRAMES_DATA);
    return Data;
}

u32 XChange_ir_Get_frames_vld(XChange_ir *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XChange_ir_ReadReg(InstancePtr->Ctrl_BaseAddress, XCHANGE_IR_CTRL_ADDR_FRAMES_CTRL);
    return Data & 0x1;
}

void XChange_ir_InterruptGlobalEnable(XChange_ir *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XChange_ir_WriteReg(InstancePtr->Ctrl_BaseAddress, XCHANGE_IR_CTRL_ADDR_GIE, 1);
}

void XChange_ir_InterruptGlobalDisable(XChange_ir *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XChange_ir_WriteReg(InstancePtr->Ctrl_BaseAddress, XCHANGE_IR_CTRL_ADDR_GIE, 0);
}

void XChange_ir_InterruptEnable(XChange_ir *InstancePtr, u32 Mask) {
    u32 Register;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Register =  XChange_ir_ReadReg(InstancePtr->Ctrl_BaseAddress, XCHANGE_IR_CTRL_ADDR_IER);
    XChange_ir_WriteReg(InstancePtr->Ctrl_BaseAddress, XCHANGE_IR_CTRL_ADDR_IER, Register | Mask);
}

void XChange_ir_InterruptDisable(XChange_ir *InstancePtr, u32 Mask) {
    u32 Register;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Register =  XChange_ir_ReadReg(InstancePtr->Ctrl_BaseAddress, XCHANGE_IR_CTRL_ADDR_IER);
    XChange_ir_WriteReg(InstancePtr->Ctrl_BaseAddress, XCHANGE_IR_CTRL_ADDR_IER, Register & (~Mask));
}

void XChange_ir_InterruptClear(XChange_ir *InstancePtr, u32 Mask) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XChange_ir_WriteReg(InstancePtr->Ctrl_BaseAddress, XCHANGE_IR_CTRL_ADDR_ISR, Mask);
}

u32 XChange_ir_InterruptGetEnabled(XChange_ir *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return XChange_ir_ReadReg(InstancePtr->Ctrl_BaseAddress, XCHANGE_IR_CTRL_ADDR_IER);
}

u32 XChange_ir_InterruptGetStatus(XChange_ir *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return XChange_ir_ReadReg(InstancePtr->Ctrl_BaseAddress, XCHANGE_IR_CTRL_ADDR_ISR);
}

