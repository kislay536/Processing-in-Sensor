// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2024.2 (64-bit)
// Tool Version Limit: 2024.11
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2024 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================
#ifndef __linux__

#include "xstatus.h"
#ifdef SDT
#include "xparameters.h"
#endif
#include "ximage_change.h"

extern XImage_change_Config XImage_change_ConfigTable[];

#ifdef SDT
XImage_change_Config *XImage_change_LookupConfig(UINTPTR BaseAddress) {
	XImage_change_Config *ConfigPtr = NULL;

	int Index;

	for (Index = (u32)0x0; XImage_change_ConfigTable[Index].Name != NULL; Index++) {
		if (!BaseAddress || XImage_change_ConfigTable[Index].Ctrl_BaseAddress == BaseAddress) {
			ConfigPtr = &XImage_change_ConfigTable[Index];
			break;
		}
	}

	return ConfigPtr;
}

int XImage_change_Initialize(XImage_change *InstancePtr, UINTPTR BaseAddress) {
	XImage_change_Config *ConfigPtr;

	Xil_AssertNonvoid(InstancePtr != NULL);

	ConfigPtr = XImage_change_LookupConfig(BaseAddress);
	if (ConfigPtr == NULL) {
		InstancePtr->IsReady = 0;
		return (XST_DEVICE_NOT_FOUND);
	}

	return XImage_change_CfgInitialize(InstancePtr, ConfigPtr);
}
#else
XImage_change_Config *XImage_change_LookupConfig(u16 DeviceId) {
	XImage_change_Config *ConfigPtr = NULL;

	int Index;

	for (Index = 0; Index < XPAR_XIMAGE_CHANGE_NUM_INSTANCES; Index++) {
		if (XImage_change_ConfigTable[Index].DeviceId == DeviceId) {
			ConfigPtr = &XImage_change_ConfigTable[Index];
			break;
		}
	}

	return ConfigPtr;
}

int XImage_change_Initialize(XImage_change *InstancePtr, u16 DeviceId) {
	XImage_change_Config *ConfigPtr;

	Xil_AssertNonvoid(InstancePtr != NULL);

	ConfigPtr = XImage_change_LookupConfig(DeviceId);
	if (ConfigPtr == NULL) {
		InstancePtr->IsReady = 0;
		return (XST_DEVICE_NOT_FOUND);
	}

	return XImage_change_CfgInitialize(InstancePtr, ConfigPtr);
}
#endif

#endif

