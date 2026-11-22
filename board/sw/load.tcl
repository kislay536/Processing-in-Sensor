# load.tcl: initialise the Zynq PS (clocks, DDR, MIO incl. Ethernet/UART), optionally program the PL, load an ELF and run it.
#   xsdb board/sw/load.tcl <elf> <ps7_init.tcl> [bitstream.bit]
# Pattern copied from flagship/sw/load.tcl.
set elf  [lindex $argv 0]
set init [lindex $argv 1]
set bit  [lindex $argv 2]
connect
targets -set -filter {name =~ "APU*"}
rst -system
after 2000
targets -set -filter {name =~ "ARM*#0"}
catch {stop}
after 500
source $init
ps7_init
if {$bit ne ""} {
  targets -set -filter {name =~ "xc7z*"}
  fpga -file $bit
  targets -set -filter {name =~ "ARM*#0"}
}
ps7_post_config
dow $elf
puts "ELF loaded, starting core 0"
con
after 500
puts "CORE: [state]"
