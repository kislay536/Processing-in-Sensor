#include "xparameters.h"
#include "xscutimer.h"

static XScuTimer_Config cfg_table[1] = {{ 0, 0xF8F00600U }};

XScuTimer_Config *XScuTimer_LookupConfig(u16 DeviceId) { return DeviceId == 0 ? &cfg_table[0] : NULL; }

s32 XScuTimer_CfgInitialize(XScuTimer *t, XScuTimer_Config *c, UINTPTR base)
{
	t->Config = *c; t->Config.BaseAddr = base; t->IsReady = 1;
	return XST_SUCCESS;
}

s32 XScuTimer_SelfTest(XScuTimer *t)
{
	/* the real driver checks that the load register is writable */
	Xil_Out32(t->Config.BaseAddr + XSCUTIMER_LOAD_OFFSET, 0xA5A5A5A5U);
	if (Xil_In32(t->Config.BaseAddr + XSCUTIMER_LOAD_OFFSET) != 0xA5A5A5A5U) return XST_FAILURE;
	Xil_Out32(t->Config.BaseAddr + XSCUTIMER_LOAD_OFFSET, 0U);
	return XST_SUCCESS;
}
