# Usage: HLS_TOP=change_rgb HLS_SRC="change_rgb.cpp" HLS_TB=tb_change.cpp HLS_TBFLAGS="-DSENSOR_RGB" HLS_STEPS="csim syn export" vitis_hls -f hls/run_hls.tcl
set root [file normalize [file dirname [info script]]]
set top $::env(HLS_TOP)
cd $root
open_project -reset proj_$top
foreach f $::env(HLS_SRC) { add_files $f -cflags "-I$root" }
add_files -tb $::env(HLS_TB) -cflags "-I$root $::env(HLS_TBFLAGS)"
set_top $top
open_solution -reset sol -flow_target vivado
set_part {xc7z020clg484-1}
create_clock -period 10 -name default
set steps $::env(HLS_STEPS)
if {[lsearch $steps csim] >= 0}   { csim_design }
if {[lsearch $steps syn] >= 0}    { csynth_design }
if {[lsearch $steps cosim] >= 0}   { cosim_design -rtl verilog -trace_level none }
if {[lsearch $steps export] >= 0} { export_design -format ip_catalog -output $root/proj_${top}_ip.zip }
exit
