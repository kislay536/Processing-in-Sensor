/* Minimal register-level shim for the Cortex-A9 private (SCU) timer.
 * This Vivado/HSI install ships no scutimer driver, but the lwIP example platform code needs exactly these calls.
 * Registers (base 0xF8F00600): LOAD 0x00, COUNTER 0x04, CONTROL 0x08 [0]=enable [1]=auto-reload [2]=irq, ISR 0x0C. */
#ifndef XSCUTIMER_SHIM_H
#define XSCUTIMER_SHIM_H
#include "xil_types.h"
#include "xil_io.h"
#include "xstatus.h"

typedef struct { u16 DeviceId; UINTPTR BaseAddr; } XScuTimer_Config;
typedef struct { XScuTimer_Config Config; u32 IsReady; } XScuTimer;

#define XSCUTIMER_LOAD_OFFSET    0x00U
#define XSCUTIMER_COUNTER_OFFSET 0x04U
#define XSCUTIMER_CONTROL_OFFSET 0x08U
#define XSCUTIMER_ISR_OFFSET     0x0CU
#define XSCUTIMER_CONTROL_ENABLE 0x1U
#define XSCUTIMER_CONTROL_AUTO   0x2U
#define XSCUTIMER_CONTROL_IRQ    0x4U

XScuTimer_Config *XScuTimer_LookupConfig(u16 DeviceId);
s32 XScuTimer_CfgInitialize(XScuTimer *t, XScuTimer_Config *c, UINTPTR base);
s32 XScuTimer_SelfTest(XScuTimer *t);

#define XScuTimer_LoadTimer(t, v)          Xil_Out32((t)->Config.BaseAddr + XSCUTIMER_LOAD_OFFSET, (v))
#define XScuTimer_EnableAutoReload(t)      Xil_Out32((t)->Config.BaseAddr + XSCUTIMER_CONTROL_OFFSET, \
                                              Xil_In32((t)->Config.BaseAddr + XSCUTIMER_CONTROL_OFFSET) | XSCUTIMER_CONTROL_AUTO)
#define XScuTimer_EnableInterrupt(t)       Xil_Out32((t)->Config.BaseAddr + XSCUTIMER_CONTROL_OFFSET, \
                                              Xil_In32((t)->Config.BaseAddr + XSCUTIMER_CONTROL_OFFSET) | XSCUTIMER_CONTROL_IRQ)
#define XScuTimer_Start(t)                 Xil_Out32((t)->Config.BaseAddr + XSCUTIMER_CONTROL_OFFSET, \
                                              Xil_In32((t)->Config.BaseAddr + XSCUTIMER_CONTROL_OFFSET) | XSCUTIMER_CONTROL_ENABLE)
#define XScuTimer_ClearInterruptStatus(t)  Xil_Out32((t)->Config.BaseAddr + XSCUTIMER_ISR_OFFSET, 1U)
#endif
