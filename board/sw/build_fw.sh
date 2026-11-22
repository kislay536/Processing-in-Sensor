#!/bin/bash
# Build the PiSe firmware without the Vitis GUI/Lopper flow (which is broken on this install:
# "Invalid Lopper Installation Directory"). Uses HSI from the Vivado-bundled xsct to generate the BSP from an XSA,
# then compiles it and the app with the system arm-none-eabi-gcc.
#
#   board/sw/build_fw.sh <design.xsa> [out_dir]      -> <out_dir>/eventcam.elf
set -euo pipefail
XSA=$(readlink -f "$1"); HERE=$(cd "$(dirname "$0")" && pwd); OUT=${2:-$HERE/../fw_build}
VIV=/tools/Xilinx/Vivado/2024.2
OVERLAY=${XSCT_OVERLAY:-$HOME/.cache/eventcam/xsct_overlay}
CPU_HZ=${CPU_HZ:-650000000}          # Zedboard preset: TTC 108.33 MHz = CPU/6
CFLAGS_CPU="-mcpu=cortex-a9 -mfpu=vfpv3 -mfloat-abi=hard"

# 1. the Vivado-bundled xsct lacks scripts/hsm; build a private overlay once (the root-owned install is not touched)
if [ ! -x "$OVERLAY/bin/xsct" ]; then
  mkdir -p "$(dirname "$OVERLAY")"; cp -a $VIV/xsct-trim "$OVERLAY"; cp -a $VIV/scripts/hsm "$OVERLAY/scripts/hsm"
fi

# 2. BSP sources from the XSA
rm -rf "$OUT"; mkdir -p "$OUT"; cd "$OUT"
cat > gen.tcl <<TCL
hsi::set_repo_path $VIV/data/embeddedsw
hsi::open_hw_design $XSA
hsi::create_sw_design bsp0 -proc ps7_cortexa9_0 -os standalone
hsi::add_library lwip220
hsi::generate_bsp -dir ./bsp
exit
TCL
"$OVERLAY/bin/xsct" gen.tcl > gen.log 2>&1 || { tail -20 gen.log; exit 1; }

# 3. the HSI-generated Makefile blanks the compiler settings and the header misses the CPU clock: patch both
cd bsp
sed -i 's/"COMPILER_FLAGS= "/"COMPILER_FLAGS=$(COMPILER_FLAGS)" "EXTRA_COMPILER_FLAGS=$(EXTRA_COMPILER_FLAGS)" "COMPILER=$(COMPILER)" "ARCHIVER=$(ARCHIVER)" "GCC_COMPILER=$(COMPILER)"/' Makefile
sed -i "0,/#define XPAR_XEMACPS_0_ENET_CLK_FREQ_HZ/s//#define XPAR_CPU_CORTEXA9_0_CPU_CLK_FREQ_HZ $CPU_HZ\n#define XPAR_XEMACPS_0_ENET_CLK_FREQ_HZ/" ps7_cortexa9_0/include/xparameters.h
make -j8 all COMPILER=arm-none-eabi-gcc ARCHIVER=arm-none-eabi-ar \
  "COMPILER_FLAGS=-O2 -c $CFLAGS_CPU" "EXTRA_COMPILER_FLAGS=-g -Wall -Wextra -fno-tree-loop-distribute-patterns" > ../bsp_make.log 2>&1 || { grep -E "error" ../bsp_make.log | head; exit 1; }
rm -f ps7_cortexa9_0/lib/libxil.a; arm-none-eabi-ar rcs ps7_cortexa9_0/lib/libxil.a $(ls ps7_cortexa9_0/lib/*.o | grep -v xil-crt0.o)
cd ..

# 4. app
BSP=$PWD/bsp/ps7_cortexa9_0
SRC=$HERE/src
arm-none-eabi-gcc $CFLAGS_CPU -O2 -g -Wall -Wno-unused-parameter -I$BSP/include -I$SRC \
  $SRC/*.c -o eventcam.elf -Wl,-T,$HERE/lscript.ld -Wl,-Map,eventcam.map -specs=/tools/Xilinx/Vivado/2024.2/data/embeddedsw/scripts/specs/arm/Xilinx.spec $BSP/lib/xil-crt0.o \
  -L$BSP/lib -Wl,--start-group,-lxil,-llwip4,-lgcc,-lc,--end-group > app.log 2>&1 || { cat app.log | head -30; exit 1; }
arm-none-eabi-size eventcam.elf
echo "ELF: $PWD/eventcam.elf"
