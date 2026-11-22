// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2024.2 (64-bit)
// Tool Version Limit: 2024.11
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2024 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================
#ifndef XCHANGE_IR_H
#define XCHANGE_IR_H

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
#include "xchange_ir_hw.h"

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
} XChange_ir_Config;
#endif

typedef struct {
    u64 Ctrl_BaseAddress;
    u32 IsReady;
} XChange_ir;

typedef u32 word_type;

/***************** Macros (Inline Functions) Definitions *********************/
#ifndef __linux__
#define XChange_ir_WriteReg(BaseAddress, RegOffset, Data) \
    Xil_Out32((BaseAddress) + (RegOffset), (u32)(Data))
#define XChange_ir_ReadReg(BaseAddress, RegOffset) \
    Xil_In32((BaseAddress) + (RegOffset))
#else
#define XChange_ir_WriteReg(BaseAddress, RegOffset, Data) \
    *(volatile u32*)((BaseAddress) + (RegOffset)) = (u32)(Data)
#define XChange_ir_ReadReg(BaseAddress, RegOffset) \
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
int XChange_ir_Initialize(XChange_ir *InstancePtr, UINTPTR BaseAddress);
XChange_ir_Config* XChange_ir_LookupConfig(UINTPTR BaseAddress);
#else
int XChange_ir_Initialize(XChange_ir *InstancePtr, u16 DeviceId);
XChange_ir_Config* XChange_ir_LookupConfig(u16 DeviceId);
#endif
int XChange_ir_CfgInitialize(XChange_ir *InstancePtr, XChange_ir_Config *ConfigPtr);
#else
int XChange_ir_Initialize(XChange_ir *InstancePtr, const char* InstanceName);
int XChange_ir_Release(XChange_ir *InstancePtr);
#endif

void XChange_ir_Start(XChange_ir *InstancePtr);
u32 XChange_ir_IsDone(XChange_ir *InstancePtr);
u32 XChange_ir_IsIdle(XChange_ir *InstancePtr);
u32 XChange_ir_IsReady(XChange_ir *InstancePtr);
void XChange_ir_EnableAutoRestart(XChange_ir *InstancePtr);
void XChange_ir_DisableAutoRestart(XChange_ir *InstancePtr);

void XChange_ir_Set_frame(XChange_ir *InstancePtr, u64 Data);
u64 XChange_ir_Get_frame(XChange_ir *InstancePtr);
void XChange_ir_Set_pix_thresh(XChange_ir *InstancePtr, u32 Data);
u32 XChange_ir_Get_pix_thresh(XChange_ir *InstancePtr);
void XChange_ir_Set_bg_shift(XChange_ir *InstancePtr, u32 Data);
u32 XChange_ir_Get_bg_shift(XChange_ir *InstancePtr);
void XChange_ir_Set_reset(XChange_ir *InstancePtr, u32 Data);
u32 XChange_ir_Get_reset(XChange_ir *InstancePtr);
u32 XChange_ir_Get_changed(XChange_ir *InstancePtr);
u32 XChange_ir_Get_changed_vld(XChange_ir *InstancePtr);
u32 XChange_ir_Get_sum_cur(XChange_ir *InstancePtr);
u32 XChange_ir_Get_sum_cur_vld(XChange_ir *InstancePtr);
u32 XChange_ir_Get_score_x1000(XChange_ir *InstancePtr);
u32 XChange_ir_Get_score_x1000_vld(XChange_ir *InstancePtr);
u32 XChange_ir_Get_frames(XChange_ir *InstancePtr);
u32 XChange_ir_Get_frames_vld(XChange_ir *InstancePtr);

void XChange_ir_InterruptGlobalEnable(XChange_ir *InstancePtr);
void XChange_ir_InterruptGlobalDisable(XChange_ir *InstancePtr);
void XChange_ir_InterruptEnable(XChange_ir *InstancePtr, u32 Mask);
void XChange_ir_InterruptDisable(XChange_ir *InstancePtr, u32 Mask);
void XChange_ir_InterruptClear(XChange_ir *InstancePtr, u32 Mask);
u32 XChange_ir_InterruptGetEnabled(XChange_ir *InstancePtr);
u32 XChange_ir_InterruptGetStatus(XChange_ir *InstancePtr);

#ifdef __cplusplus
}
#endif

#endif
