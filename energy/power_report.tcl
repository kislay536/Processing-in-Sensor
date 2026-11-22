# Vivado's own power estimate of the routed design (vectorless, default activity): on-chip power of the Zynq PL + PS.
open_checkpoint [file normalize [file dirname [info script]]/../board/vivado_build/proj/eventcam.runs/impl_1/system_wrapper_routed.dcp]
report_power -file [file normalize [file dirname [info script]]/vivado_power.rpt]
exit
