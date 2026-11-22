// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2024.2 (64-bit)
// Tool Version Limit: 2024.11
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2024 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================
#ifndef XIMAGE_CHANGE_H
#define XIMAGE_CHANGE_H

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
#include "ximage_change_hw.h"

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
} XImage_change_Config;
#endif

typedef struct {
    u64 Ctrl_BaseAddress;
    u32 IsReady;
} XImage_change;

typedef u32 word_type;

/***************** Macros (Inline Functions) Definitions *********************/
#ifndef __linux__
#define XImage_change_WriteReg(BaseAddress, RegOffset, Data) \
    Xil_Out32((BaseAddress) + (RegOffset), (u32)(Data))
#define XImage_change_ReadReg(BaseAddress, RegOffset) \
    Xil_In32((BaseAddress) + (RegOffset))
#else
#define XImage_change_WriteReg(BaseAddress, RegOffset, Data) \
    *(volatile u32*)((BaseAddress) + (RegOffset)) = (u32)(Data)
#define XImage_change_ReadReg(BaseAddress, RegOffset) \
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
int XImage_change_Initialize(XImage_change *InstancePtr, UINTPTR BaseAddress);
XImage_change_Config* XImage_change_LookupConfig(UINTPTR BaseAddress);
#else
int XImage_change_Initialize(XImage_change *InstancePtr, u16 DeviceId);
XImage_change_Config* XImage_change_LookupConfig(u16 DeviceId);
#endif
int XImage_change_CfgInitialize(XImage_change *InstancePtr, XImage_change_Config *ConfigPtr);
#else
int XImage_change_Initialize(XImage_change *InstancePtr, const char* InstanceName);
int XImage_change_Release(XImage_change *InstancePtr);
#endif

void XImage_change_Start(XImage_change *InstancePtr);
u32 XImage_change_IsDone(XImage_change *InstancePtr);
u32 XImage_change_IsIdle(XImage_change *InstancePtr);
u32 XImage_change_IsReady(XImage_change *InstancePtr);
void XImage_change_EnableAutoRestart(XImage_change *InstancePtr);
void XImage_change_DisableAutoRestart(XImage_change *InstancePtr);

void XImage_change_Set_frame(XImage_change *InstancePtr, u64 Data);
u64 XImage_change_Get_frame(XImage_change *InstancePtr);
void XImage_change_Set_pix_min(XImage_change *InstancePtr, u32 Data);
u32 XImage_change_Get_pix_min(XImage_change *InstancePtr);
void XImage_change_Set_var_init(XImage_change *InstancePtr, u32 Data);
u32 XImage_change_Get_var_init(XImage_change *InstancePtr);
void XImage_change_Set_var_min(XImage_change *InstancePtr, u32 Data);
u32 XImage_change_Get_var_min(XImage_change *InstancePtr);
void XImage_change_Set_var_max(XImage_change *InstancePtr, u32 Data);
u32 XImage_change_Get_var_max(XImage_change *InstancePtr);
void XImage_change_Set_var_shift(XImage_change *InstancePtr, u32 Data);
u32 XImage_change_Get_var_shift(XImage_change *InstancePtr);
void XImage_change_Set_min_cells(XImage_change *InstancePtr, u32 Data);
u32 XImage_change_Get_min_cells(XImage_change *InstancePtr);
void XImage_change_Set_persist_frames(XImage_change *InstancePtr, u32 Data);
u32 XImage_change_Get_persist_frames(XImage_change *InstancePtr);
void XImage_change_Set_freeze_frames(XImage_change *InstancePtr, u32 Data);
u32 XImage_change_Get_freeze_frames(XImage_change *InstancePtr);
void XImage_change_Set_illum_en(XImage_change *InstancePtr, u32 Data);
u32 XImage_change_Get_illum_en(XImage_change *InstancePtr);
void XImage_change_Set_illum_min(XImage_change *InstancePtr, u32 Data);
u32 XImage_change_Get_illum_min(XImage_change *InstancePtr);
void XImage_change_Set_cell_req(XImage_change *InstancePtr, u32 Data);
u32 XImage_change_Get_cell_req(XImage_change *InstancePtr);
void XImage_change_Set_global_limit(XImage_change *InstancePtr, u32 Data);
u32 XImage_change_Get_global_limit(XImage_change *InstancePtr);
void XImage_change_Set_resid_limit(XImage_change *InstancePtr, u32 Data);
u32 XImage_change_Get_resid_limit(XImage_change *InstancePtr);
void XImage_change_Set_reset(XImage_change *InstancePtr, u32 Data);
u32 XImage_change_Get_reset(XImage_change *InstancePtr);
u32 XImage_change_Get_fired(XImage_change *InstancePtr);
u32 XImage_change_Get_fired_vld(XImage_change *InstancePtr);
u32 XImage_change_Get_reason(XImage_change *InstancePtr);
u32 XImage_change_Get_reason_vld(XImage_change *InstancePtr);
u32 XImage_change_Get_score(XImage_change *InstancePtr);
u32 XImage_change_Get_score_vld(XImage_change *InstancePtr);
u32 XImage_change_Get_region_pass(XImage_change *InstancePtr);
u32 XImage_change_Get_region_pass_vld(XImage_change *InstancePtr);
u32 XImage_change_Get_active_out(XImage_change *InstancePtr);
u32 XImage_change_Get_active_out_vld(XImage_change *InstancePtr);
u32 XImage_change_Get_changed_out(XImage_change *InstancePtr);
u32 XImage_change_Get_changed_out_vld(XImage_change *InstancePtr);
u32 XImage_change_Get_persist_out(XImage_change *InstancePtr);
u32 XImage_change_Get_persist_out_vld(XImage_change *InstancePtr);
u32 XImage_change_Get_frames_out(XImage_change *InstancePtr);
u32 XImage_change_Get_frames_out_vld(XImage_change *InstancePtr);
u32 XImage_change_Get_cell_counts_BaseAddress(XImage_change *InstancePtr);
u32 XImage_change_Get_cell_counts_HighAddress(XImage_change *InstancePtr);
u32 XImage_change_Get_cell_counts_TotalBytes(XImage_change *InstancePtr);
u32 XImage_change_Get_cell_counts_BitWidth(XImage_change *InstancePtr);
u32 XImage_change_Get_cell_counts_Depth(XImage_change *InstancePtr);
u32 XImage_change_Write_cell_counts_Words(XImage_change *InstancePtr, int offset, word_type *data, int length);
u32 XImage_change_Read_cell_counts_Words(XImage_change *InstancePtr, int offset, word_type *data, int length);
u32 XImage_change_Write_cell_counts_Bytes(XImage_change *InstancePtr, int offset, char *data, int length);
u32 XImage_change_Read_cell_counts_Bytes(XImage_change *InstancePtr, int offset, char *data, int length);

void XImage_change_InterruptGlobalEnable(XImage_change *InstancePtr);
void XImage_change_InterruptGlobalDisable(XImage_change *InstancePtr);
void XImage_change_InterruptEnable(XImage_change *InstancePtr, u32 Mask);
void XImage_change_InterruptDisable(XImage_change *InstancePtr, u32 Mask);
void XImage_change_InterruptClear(XImage_change *InstancePtr, u32 Mask);
u32 XImage_change_InterruptGetEnabled(XImage_change *InstancePtr);
u32 XImage_change_InterruptGetStatus(XImage_change *InstancePtr);

#ifdef __cplusplus
}
#endif

#endif
