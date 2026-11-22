# PiSe Zedboard system: PS7 (Digilent preset; ENET0 + MDIO, UART1, DDR) + three HLS detectors (colour image-change, IR change, audio bands).
#   vivado -mode batch -source board/vivado/bd.tcl -tclargs [stop_after_bd]
# Control: PS M_AXI_GP0 -> each IP's s_axi_ctrl.  Data: each IP's m_axi_gmem -> PS S_AXI_HP0 -> DDR.  Fabric clock FCLK0 = 100 MHz.
set here [file normalize [file dirname [info script]]]
set root [file normalize $here/../..]
set out  $root/board/vivado_build
file delete -force $out; file mkdir $out
set_param board.repoPaths [list $root/../flagship/boardfiles_dl]
create_project eventcam $out/proj -part xc7z020clg484-1 -force
set_property board_part digilentinc.com:zedboard:part0:1.1 [current_project]
set_property ip_repo_paths [list $root/hls/ip/image_change $root/hls/ip/change_ir $root/hls/ip/audio_bands] [current_project]
update_ip_catalog

create_bd_design system
set ps [create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7 ps7]
apply_bd_automation -rule xilinx.com:bd_rule:processing_system7 -config {make_external "FIXED_IO, DDR" apply_board_preset "1" Master "Disable" Slave "Disable"} $ps
set_property -dict [list \
  CONFIG.PCW_USE_M_AXI_GP0 {1} CONFIG.PCW_USE_S_AXI_HP0 {1} CONFIG.PCW_S_AXI_HP0_DATA_WIDTH {64} \
  CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {100} \
  CONFIG.PCW_ENET0_GRP_MDIO_ENABLE {1} CONFIG.PCW_ENET0_GRP_MDIO_IO {MIO 52 .. 53}] $ps

foreach n {image_change change_ir audio_bands} {
  create_bd_cell -type ip -vlnv xilinx.com:hls:$n:1.0 $n
}
foreach n {image_change change_ir audio_bands} {
  apply_bd_automation -rule xilinx.com:bd_rule:axi4 -config {Master "/ps7/M_AXI_GP0" Clk "Auto"} [get_bd_intf_pins $n/s_axi_ctrl]
}
# data path, wired by hand (the HP0 automation rule does not accept HLS masters in this release)
set ic [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect hp_ic]
set_property -dict [list CONFIG.NUM_SI {3} CONFIG.NUM_MI {1}] $ic
set i 0
foreach n {image_change change_ir audio_bands} {
  connect_bd_intf_net [get_bd_intf_pins $n/m_axi_gmem] [get_bd_intf_pins hp_ic/S0${i}_AXI]
  incr i
}
connect_bd_intf_net [get_bd_intf_pins hp_ic/M00_AXI] [get_bd_intf_pins ps7/S_AXI_HP0]
set clk [get_bd_pins ps7/FCLK_CLK0]
connect_bd_net $clk [get_bd_pins hp_ic/ACLK] [get_bd_pins hp_ic/S00_ACLK] [get_bd_pins hp_ic/S01_ACLK] [get_bd_pins hp_ic/S02_ACLK] \
                    [get_bd_pins hp_ic/M00_ACLK] [get_bd_pins ps7/S_AXI_HP0_ACLK]
set rst [get_bd_cells -filter {VLNV =~ "*proc_sys_reset*"}]
connect_bd_net [get_bd_pins $rst/interconnect_aresetn] [get_bd_pins hp_ic/ARESETN]
connect_bd_net [get_bd_pins $rst/peripheral_aresetn] [get_bd_pins hp_ic/S00_ARESETN] [get_bd_pins hp_ic/S01_ARESETN] \
                    [get_bd_pins hp_ic/S02_ARESETN] [get_bd_pins hp_ic/M00_ARESETN]
assign_bd_address
validate_bd_design
save_bd_design
set wrapper [make_wrapper -files [get_files system.bd] -top]
add_files -norecurse $wrapper
set_property top system_wrapper [current_fileset]
puts "BD_DONE"
foreach s [get_bd_addr_segs -of_objects [get_bd_addr_spaces ps7/Data]] { puts "SEG [get_property NAME $s] offset [get_property OFFSET $s] range [get_property RANGE $s]" }
foreach s [get_bd_addr_segs -of_objects [get_bd_addr_spaces {image_change/Data_m_axi_gmem change_ir/Data_m_axi_gmem audio_bands/Data_m_axi_gmem}]] { puts "HPSEG [get_property PATH $s] offset [get_property OFFSET $s] range [get_property RANGE $s]" }
if {[llength $argv] > 0 && [lindex $argv 0] eq "stop_after_bd"} { puts "STOP"; exit }

launch_runs impl_1 -to_step write_bitstream -jobs 8
wait_on_run impl_1
open_run impl_1
report_timing_summary -file $out/timing.rpt
report_utilization -file $out/util.rpt
write_hw_platform -fixed -include_bit -force $out/eventcam.xsa
puts "DONE"
