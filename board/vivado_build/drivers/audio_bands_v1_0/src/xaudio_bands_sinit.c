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
#include "xaudio_bands.h"

extern XAudio_bands_Config XAudio_bands_ConfigTable[];

#ifdef SDT
XAudio_bands_Config *XAudio_bands_LookupConfig(UINTPTR BaseAddress) {
	XAudio_bands_Config *ConfigPtr = NULL;

	int Index;

	for (Index = (u32)0x0; XAudio_bands_ConfigTable[Index].Name != NULL; Index++) {
		if (!BaseAddress || XAudio_bands_ConfigTable[Index].Ctrl_BaseAddress == BaseAddress) {
			ConfigPtr = &XAudio_bands_ConfigTable[Index];
			break;
		}
	}

	return ConfigPtr;
}

int XAudio_bands_Initialize(XAudio_bands *InstancePtr, UINTPTR BaseAddress) {
	XAudio_bands_Config *ConfigPtr;

	Xil_AssertNonvoid(InstancePtr != NULL);

	ConfigPtr = XAudio_bands_LookupConfig(BaseAddress);
	if (ConfigPtr == NULL) {
		InstancePtr->IsReady = 0;
		return (XST_DEVICE_NOT_FOUND);
	}

	return XAudio_bands_CfgInitialize(InstancePtr, ConfigPtr);
}
#else
XAudio_bands_Config *XAudio_bands_LookupConfig(u16 DeviceId) {
	XAudio_bands_Config *ConfigPtr = NULL;

	int Index;

	for (Index = 0; Index < XPAR_XAUDIO_BANDS_NUM_INSTANCES; Index++) {
		if (XAudio_bands_ConfigTable[Index].DeviceId == DeviceId) {
			ConfigPtr = &XAudio_bands_ConfigTable[Index];
			break;
		}
	}

	return ConfigPtr;
}

int XAudio_bands_Initialize(XAudio_bands *InstancePtr, u16 DeviceId) {
	XAudio_bands_Config *ConfigPtr;

	Xil_AssertNonvoid(InstancePtr != NULL);

	ConfigPtr = XAudio_bands_LookupConfig(DeviceId);
	if (ConfigPtr == NULL) {
		InstancePtr->IsReady = 0;
		return (XST_DEVICE_NOT_FOUND);
	}

	return XAudio_bands_CfgInitialize(InstancePtr, ConfigPtr);
}
#endif

#endif

