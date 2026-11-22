// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2024.2 (64-bit)
// Tool Version Limit: 2024.11
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2024 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================
#ifndef XAUDIO_BANDS_H
#define XAUDIO_BANDS_H

#ifdef __cplusplus
extern "C" {
#endif

/***************************** Include Files *********************************/
#ifndef __linux__
#include "xil_types.h"
#include "xil_assert.h"
#include "xstatus.h"
#include "xil_io.h"
#else
#include <stdint.h>
#include <assert.h>
#include <dirent.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
#include <stddef.h>
#endif
#include "xaudio_bands_hw.h"

/**************************** Type Definitions ******************************/
#ifdef __linux__
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;
#else
typedef struct {
#ifdef SDT
    char *Name;
#else
    u16 DeviceId;
#endif
    u64 Ctrl_BaseAddress;
} XAudio_bands_Config;
#endif

typedef struct {
    u64 Ctrl_BaseAddress;
    u32 IsReady;
} XAudio_bands;

typedef u32 word_type;

/***************** Macros (Inline Functions) Definitions *********************/
#ifndef __linux__
#define XAudio_bands_WriteReg(BaseAddress, RegOffset, Data) \
    Xil_Out32((BaseAddress) + (RegOffset), (u32)(Data))
#define XAudio_bands_ReadReg(BaseAddress, RegOffset) \
    Xil_In32((BaseAddress) + (RegOffset))
#else
#define XAudio_bands_WriteReg(BaseAddress, RegOffset, Data) \
    *(volatile u32*)((BaseAddress) + (RegOffset)) = (u32)(Data)
#define XAudio_bands_ReadReg(BaseAddress, RegOffset) \
    *(volatile u32*)((BaseAddress) + (RegOffset))

#define Xil_AssertVoid(expr)    assert(expr)
#define Xil_AssertNonvoid(expr) assert(expr)

#define XST_SUCCESS             0
#define XST_DEVICE_NOT_FOUND    2
#define XST_OPEN_DEVICE_FAILED  3
#define XIL_COMPONENT_IS_READY  1
#endif

/************************** Function Prototypes *****************************/
#ifndef __linux__
#ifdef SDT
int XAudio_bands_Initialize(XAudio_bands *InstancePtr, UINTPTR BaseAddress);
XAudio_bands_Config* XAudio_bands_LookupConfig(UINTPTR BaseAddress);
#else
int XAudio_bands_Initialize(XAudio_bands *InstancePtr, u16 DeviceId);
XAudio_bands_Config* XAudio_bands_LookupConfig(u16 DeviceId);
#endif
int XAudio_bands_CfgInitialize(XAudio_bands *InstancePtr, XAudio_bands_Config *ConfigPtr);
#else
int XAudio_bands_Initialize(XAudio_bands *InstancePtr, const char* InstanceName);
int XAudio_bands_Release(XAudio_bands *InstancePtr);
#endif

void XAudio_bands_Start(XAudio_bands *InstancePtr);
u32 XAudio_bands_IsDone(XAudio_bands *InstancePtr);
u32 XAudio_bands_IsIdle(XAudio_bands *InstancePtr);
u32 XAudio_bands_IsReady(XAudio_bands *InstancePtr);
void XAudio_bands_EnableAutoRestart(XAudio_bands *InstancePtr);
void XAudio_bands_DisableAutoRestart(XAudio_bands *InstancePtr);

void XAudio_bands_Set_samples(XAudio_bands *InstancePtr, u64 Data);
u64 XAudio_bands_Get_samples(XAudio_bands *InstancePtr);
u64 XAudio_bands_Get_sum_sq(XAudio_bands *InstancePtr);
u32 XAudio_bands_Get_sum_sq_vld(XAudio_bands *InstancePtr);
u32 XAudio_bands_Get_blocks(XAudio_bands *InstancePtr);
u32 XAudio_bands_Get_blocks_vld(XAudio_bands *InstancePtr);
u32 XAudio_bands_Get_band_BaseAddress(XAudio_bands *InstancePtr);
u32 XAudio_bands_Get_band_HighAddress(XAudio_bands *InstancePtr);
u32 XAudio_bands_Get_band_TotalBytes(XAudio_bands *InstancePtr);
u32 XAudio_bands_Get_band_BitWidth(XAudio_bands *InstancePtr);
u32 XAudio_bands_Get_band_Depth(XAudio_bands *InstancePtr);
u32 XAudio_bands_Write_band_Words(XAudio_bands *InstancePtr, int offset, word_type *data, int length);
u32 XAudio_bands_Read_band_Words(XAudio_bands *InstancePtr, int offset, word_type *data, int length);
u32 XAudio_bands_Write_band_Bytes(XAudio_bands *InstancePtr, int offset, char *data, int length);
u32 XAudio_bands_Read_band_Bytes(XAudio_bands *InstancePtr, int offset, char *data, int length);

void XAudio_bands_InterruptGlobalEnable(XAudio_bands *InstancePtr);
void XAudio_bands_InterruptGlobalDisable(XAudio_bands *InstancePtr);
void XAudio_bands_InterruptEnable(XAudio_bands *InstancePtr, u32 Mask);
void XAudio_bands_InterruptDisable(XAudio_bands *InstancePtr, u32 Mask);
void XAudio_bands_InterruptClear(XAudio_bands *InstancePtr, u32 Mask);
u32 XAudio_bands_InterruptGetEnabled(XAudio_bands *InstancePtr);
u32 XAudio_bands_InterruptGetStatus(XAudio_bands *InstancePtr);

#ifdef __cplusplus
}
#endif

#endif
