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
#include "xchange_rgb.h"

extern XChange_rgb_Config XChange_rgb_ConfigTable[];

#ifdef SDT
XChange_rgb_Config *XChange_rgb_LookupConfig(UINTPTR BaseAddress) {
	XChange_rgb_Config *ConfigPtr = NULL;

	int Index;

	for (Index = (u32)0x0; XChange_rgb_ConfigTable[Index].Name != NULL; Index++) {
		if (!BaseAddress || XChange_rgb_ConfigTable[Index].Ctrl_BaseAddress == BaseAddress) {
			ConfigPtr = &XChange_rgb_ConfigTable[Index];
			break;
		}
	}

	return ConfigPtr;
}

int XChange_rgb_Initialize(XChange_rgb *InstancePtr, UINTPTR BaseAddress) {
	XChange_rgb_Config *ConfigPtr;

	Xil_AssertNonvoid(InstancePtr != NULL);

	ConfigPtr = XChange_rgb_LookupConfig(BaseAddress);
	if (ConfigPtr == NULL) {
		InstancePtr->IsReady = 0;
		return (XST_DEVICE_NOT_FOUND);
	}

	return XChange_rgb_CfgInitialize(InstancePtr, ConfigPtr);
}
#else
XChange_rgb_Config *XChange_rgb_LookupConfig(u16 DeviceId) {
	XChange_rgb_Config *ConfigPtr = NULL;

	int Index;

	for (Index = 0; Index < XPAR_XCHANGE_RGB_NUM_INSTANCES; Index++) {
		if (XChange_rgb_ConfigTable[Index].DeviceId == DeviceId) {
			ConfigPtr = &XChange_rgb_ConfigTable[Index];
			break;
		}
	}

	return ConfigPtr;
}

int XChange_rgb_Initialize(XChange_rgb *InstancePtr, u16 DeviceId) {
	XChange_rgb_Config *ConfigPtr;

	Xil_AssertNonvoid(InstancePtr != NULL);

	ConfigPtr = XChange_rgb_LookupConfig(DeviceId);
	if (ConfigPtr == NULL) {
		InstancePtr->IsReady = 0;
		return (XST_DEVICE_NOT_FOUND);
	}

	return XChange_rgb_CfgInitialize(InstancePtr, ConfigPtr);
}
#endif

#endif

