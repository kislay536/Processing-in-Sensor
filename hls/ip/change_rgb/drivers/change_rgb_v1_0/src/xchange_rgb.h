// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2024.2 (64-bit)
// Tool Version Limit: 2024.11
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2024 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================
#ifndef XCHANGE_RGB_H
#define XCHANGE_RGB_H

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
#include "xchange_rgb_hw.h"

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
} XChange_rgb_Config;
#endif

typedef struct {
    u64 Ctrl_BaseAddress;
    u32 IsReady;
} XChange_rgb;

typedef u32 word_type;

/***************** Macros (Inline Functions) Definitions *********************/
#ifndef __linux__
#define XChange_rgb_WriteReg(BaseAddress, RegOffset, Data) \
    Xil_Out32((BaseAddress) + (RegOffset), (u32)(Data))
#define XChange_rgb_ReadReg(BaseAddress, RegOffset) \
    Xil_In32((BaseAddress) + (RegOffset))
#else
#define XChange_rgb_WriteReg(BaseAddress, RegOffset, Data) \
    *(volatile u32*)((BaseAddress) + (RegOffset)) = (u32)(Data)
#define XChange_rgb_ReadReg(BaseAddress, RegOffset) \
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
int XChange_rgb_Initialize(XChange_rgb *InstancePtr, UINTPTR BaseAddress);
XChange_rgb_Config* XChange_rgb_LookupConfig(UINTPTR BaseAddress);
#else
int XChange_rgb_Initialize(XChange_rgb *InstancePtr, u16 DeviceId);
XChange_rgb_Config* XChange_rgb_LookupConfig(u16 DeviceId);
#endif
int XChange_rgb_CfgInitialize(XChange_rgb *InstancePtr, XChange_rgb_Config *ConfigPtr);
#else
int XChange_rgb_Initialize(XChange_rgb *InstancePtr, const char* InstanceName);
int XChange_rgb_Release(XChange_rgb *InstancePtr);
#endif

void XChange_rgb_Start(XChange_rgb *InstancePtr);
u32 XChange_rgb_IsDone(XChange_rgb *InstancePtr);
u32 XChange_rgb_IsIdle(XChange_rgb *InstancePtr);
u32 XChange_rgb_IsReady(XChange_rgb *InstancePtr);
void XChange_rgb_EnableAutoRestart(XChange_rgb *InstancePtr);
void XChange_rgb_DisableAutoRestart(XChange_rgb *InstancePtr);

void XChange_rgb_Set_frame(XChange_rgb *InstancePtr, u64 Data);
u64 XChange_rgb_Get_frame(XChange_rgb *InstancePtr);
void XChange_rgb_Set_pix_thresh(XChange_rgb *InstancePtr, u32 Data);
u32 XChange_rgb_Get_pix_thresh(XChange_rgb *InstancePtr);
void XChange_rgb_Set_bg_shift(XChange_rgb *InstancePtr, u32 Data);
u32 XChange_rgb_Get_bg_shift(XChange_rgb *InstancePtr);
void XChange_rgb_Set_reset(XChange_rgb *InstancePtr, u32 Data);
u32 XChange_rgb_Get_reset(XChange_rgb *InstancePtr);
u32 XChange_rgb_Get_changed(XChange_rgb *InstancePtr);
u32 XChange_rgb_Get_changed_vld(XChange_rgb *InstancePtr);
u32 XChange_rgb_Get_sum_cur(XChange_rgb *InstancePtr);
u32 XChange_rgb_Get_sum_cur_vld(XChange_rgb *InstancePtr);
u32 XChange_rgb_Get_score_x1000(XChange_rgb *InstancePtr);
u32 XChange_rgb_Get_score_x1000_vld(XChange_rgb *InstancePtr);
u32 XChange_rgb_Get_frames(XChange_rgb *InstancePtr);
u32 XChange_rgb_Get_frames_vld(XChange_rgb *InstancePtr);

void XChange_rgb_InterruptGlobalEnable(XChange_rgb *InstancePtr);
void XChange_rgb_InterruptGlobalDisable(XChange_rgb *InstancePtr);
void XChange_rgb_InterruptEnable(XChange_rgb *InstancePtr, u32 Mask);
void XChange_rgb_InterruptDisable(XChange_rgb *InstancePtr, u32 Mask);
void XChange_rgb_InterruptClear(XChange_rgb *InstancePtr, u32 Mask);
u32 XChange_rgb_InterruptGetEnabled(XChange_rgb *InstancePtr);
u32 XChange_rgb_InterruptGetStatus(XChange_rgb *InstancePtr);

#ifdef __cplusplus
}
#endif

#endif
