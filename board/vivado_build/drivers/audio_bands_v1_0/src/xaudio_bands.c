// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2024.2 (64-bit)
// Tool Version Limit: 2024.11
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2024 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================
/***************************** Include Files *********************************/
#include "xaudio_bands.h"

/************************** Function Implementation *************************/
#ifndef __linux__
int XAudio_bands_CfgInitialize(XAudio_bands *InstancePtr, XAudio_bands_Config *ConfigPtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(ConfigPtr != NULL);

    InstancePtr->Ctrl_BaseAddress = ConfigPtr->Ctrl_BaseAddress;
    InstancePtr->IsReady = XIL_COMPONENT_IS_READY;

    return XST_SUCCESS;
}
#endif

void XAudio_bands_Start(XAudio_bands *InstancePtr) {
    u32 Data;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XAudio_bands_ReadReg(InstancePtr->Ctrl_BaseAddress, XAUDIO_BANDS_CTRL_ADDR_AP_CTRL) & 0x80;
    XAudio_bands_WriteReg(InstancePtr->Ctrl_BaseAddress, XAUDIO_BANDS_CTRL_ADDR_AP_CTRL, Data | 0x01);
}

u32 XAudio_bands_IsDone(XAudio_bands *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XAudio_bands_ReadReg(InstancePtr->Ctrl_BaseAddress, XAUDIO_BANDS_CTRL_ADDR_AP_CTRL);
    return (Data >> 1) & 0x1;
}

u32 XAudio_bands_IsIdle(XAudio_bands *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XAudio_bands_ReadReg(InstancePtr->Ctrl_BaseAddress, XAUDIO_BANDS_CTRL_ADDR_AP_CTRL);
    return (Data >> 2) & 0x1;
}

u32 XAudio_bands_IsReady(XAudio_bands *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XAudio_bands_ReadReg(InstancePtr->Ctrl_BaseAddress, XAUDIO_BANDS_CTRL_ADDR_AP_CTRL);
    // check ap_start to see if the pcore is ready for next input
    return !(Data & 0x1);
}

void XAudio_bands_EnableAutoRestart(XAudio_bands *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XAudio_bands_WriteReg(InstancePtr->Ctrl_BaseAddress, XAUDIO_BANDS_CTRL_ADDR_AP_CTRL, 0x80);
}

void XAudio_bands_DisableAutoRestart(XAudio_bands *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XAudio_bands_WriteReg(InstancePtr->Ctrl_BaseAddress, XAUDIO_BANDS_CTRL_ADDR_AP_CTRL, 0);
}

void XAudio_bands_Set_samples(XAudio_bands *InstancePtr, u64 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XAudio_bands_WriteReg(InstancePtr->Ctrl_BaseAddress, XAUDIO_BANDS_CTRL_ADDR_SAMPLES_DATA, (u32)(Data));
    XAudio_bands_WriteReg(InstancePtr->Ctrl_BaseAddress, XAUDIO_BANDS_CTRL_ADDR_SAMPLES_DATA + 4, (u32)(Data >> 32));
}

u64 XAudio_bands_Get_samples(XAudio_bands *InstancePtr) {
    u64 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XAudio_bands_ReadReg(InstancePtr->Ctrl_BaseAddress, XAUDIO_BANDS_CTRL_ADDR_SAMPLES_DATA);
    Data += (u64)XAudio_bands_ReadReg(InstancePtr->Ctrl_BaseAddress, XAUDIO_BANDS_CTRL_ADDR_SAMPLES_DATA + 4) << 32;
    return Data;
}

u64 XAudio_bands_Get_sum_sq(XAudio_bands *InstancePtr) {
    u64 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XAudio_bands_ReadReg(InstancePtr->Ctrl_BaseAddress, XAUDIO_BANDS_CTRL_ADDR_SUM_SQ_DATA);
    Data += (u64)XAudio_bands_ReadReg(InstancePtr->Ctrl_BaseAddress, XAUDIO_BANDS_CTRL_ADDR_SUM_SQ_DATA + 4) << 32;
    return Data;
}

u32 XAudio_bands_Get_sum_sq_vld(XAudio_bands *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XAudio_bands_ReadReg(InstancePtr->Ctrl_BaseAddress, XAUDIO_BANDS_CTRL_ADDR_SUM_SQ_CTRL);
    return Data & 0x1;
}

u32 XAudio_bands_Get_blocks(XAudio_bands *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XAudio_bands_ReadReg(InstancePtr->Ctrl_BaseAddress, XAUDIO_BANDS_CTRL_ADDR_BLOCKS_DATA);
    return Data;
}

u32 XAudio_bands_Get_blocks_vld(XAudio_bands *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XAudio_bands_ReadReg(InstancePtr->Ctrl_BaseAddress, XAUDIO_BANDS_CTRL_ADDR_BLOCKS_CTRL);
    return Data & 0x1;
}

u32 XAudio_bands_Get_band_BaseAddress(XAudio_bands *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return (InstancePtr->Ctrl_BaseAddress + XAUDIO_BANDS_CTRL_ADDR_BAND_BASE);
}

u32 XAudio_bands_Get_band_HighAddress(XAudio_bands *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return (InstancePtr->Ctrl_BaseAddress + XAUDIO_BANDS_CTRL_ADDR_BAND_HIGH);
}

u32 XAudio_bands_Get_band_TotalBytes(XAudio_bands *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return (XAUDIO_BANDS_CTRL_ADDR_BAND_HIGH - XAUDIO_BANDS_CTRL_ADDR_BAND_BASE + 1);
}

u32 XAudio_bands_Get_band_BitWidth(XAudio_bands *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return XAUDIO_BANDS_CTRL_WIDTH_BAND;
}

u32 XAudio_bands_Get_band_Depth(XAudio_bands *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return XAUDIO_BANDS_CTRL_DEPTH_BAND;
}

u32 XAudio_bands_Write_band_Words(XAudio_bands *InstancePtr, int offset, word_type *data, int length) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr -> IsReady == XIL_COMPONENT_IS_READY);

    int i;

    if ((offset + length)*4 > (XAUDIO_BANDS_CTRL_ADDR_BAND_HIGH - XAUDIO_BANDS_CTRL_ADDR_BAND_BASE + 1))
        return 0;

    for (i = 0; i < length; i++) {
        *(int *)(InstancePtr->Ctrl_BaseAddress + XAUDIO_BANDS_CTRL_ADDR_BAND_BASE + (offset + i)*4) = *(data + i);
    }
    return length;
}

u32 XAudio_bands_Read_band_Words(XAudio_bands *InstancePtr, int offset, word_type *data, int length) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr -> IsReady == XIL_COMPONENT_IS_READY);

    int i;

    if ((offset + length)*4 > (XAUDIO_BANDS_CTRL_ADDR_BAND_HIGH - XAUDIO_BANDS_CTRL_ADDR_BAND_BASE + 1))
        return 0;

    for (i = 0; i < length; i++) {
        *(data + i) = *(int *)(InstancePtr->Ctrl_BaseAddress + XAUDIO_BANDS_CTRL_ADDR_BAND_BASE + (offset + i)*4);
    }
    return length;
}

u32 XAudio_bands_Write_band_Bytes(XAudio_bands *InstancePtr, int offset, char *data, int length) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr -> IsReady == XIL_COMPONENT_IS_READY);

    int i;

    if ((offset + length) > (XAUDIO_BANDS_CTRL_ADDR_BAND_HIGH - XAUDIO_BANDS_CTRL_ADDR_BAND_BASE + 1))
        return 0;

    for (i = 0; i < length; i++) {
        *(char *)(InstancePtr->Ctrl_BaseAddress + XAUDIO_BANDS_CTRL_ADDR_BAND_BASE + offset + i) = *(data + i);
    }
    return length;
}

u32 XAudio_bands_Read_band_Bytes(XAudio_bands *InstancePtr, int offset, char *data, int length) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr -> IsReady == XIL_COMPONENT_IS_READY);

    int i;

    if ((offset + length) > (XAUDIO_BANDS_CTRL_ADDR_BAND_HIGH - XAUDIO_BANDS_CTRL_ADDR_BAND_BASE + 1))
        return 0;

    for (i = 0; i < length; i++) {
        *(data + i) = *(char *)(InstancePtr->Ctrl_BaseAddress + XAUDIO_BANDS_CTRL_ADDR_BAND_BASE + offset + i);
    }
    return length;
}

void XAudio_bands_InterruptGlobalEnable(XAudio_bands *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XAudio_bands_WriteReg(InstancePtr->Ctrl_BaseAddress, XAUDIO_BANDS_CTRL_ADDR_GIE, 1);
}

void XAudio_bands_InterruptGlobalDisable(XAudio_bands *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XAudio_bands_WriteReg(InstancePtr->Ctrl_BaseAddress, XAUDIO_BANDS_CTRL_ADDR_GIE, 0);
}

void XAudio_bands_InterruptEnable(XAudio_bands *InstancePtr, u32 Mask) {
    u32 Register;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Register =  XAudio_bands_ReadReg(InstancePtr->Ctrl_BaseAddress, XAUDIO_BANDS_CTRL_ADDR_IER);
    XAudio_bands_WriteReg(InstancePtr->Ctrl_BaseAddress, XAUDIO_BANDS_CTRL_ADDR_IER, Register | Mask);
}

void XAudio_bands_InterruptDisable(XAudio_bands *InstancePtr, u32 Mask) {
    u32 Register;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Register =  XAudio_bands_ReadReg(InstancePtr->Ctrl_BaseAddress, XAUDIO_BANDS_CTRL_ADDR_IER);
    XAudio_bands_WriteReg(InstancePtr->Ctrl_BaseAddress, XAUDIO_BANDS_CTRL_ADDR_IER, Register & (~Mask));
}

void XAudio_bands_InterruptClear(XAudio_bands *InstancePtr, u32 Mask) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XAudio_bands_WriteReg(InstancePtr->Ctrl_BaseAddress, XAUDIO_BANDS_CTRL_ADDR_ISR, Mask);
}

u32 XAudio_bands_InterruptGetEnabled(XAudio_bands *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return XAudio_bands_ReadReg(InstancePtr->Ctrl_BaseAddress, XAUDIO_BANDS_CTRL_ADDR_IER);
}

u32 XAudio_bands_InterruptGetStatus(XAudio_bands *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return XAudio_bands_ReadReg(InstancePtr->Ctrl_BaseAddress, XAUDIO_BANDS_CTRL_ADDR_ISR);
}

