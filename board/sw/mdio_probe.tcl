# Read PHY registers through GEM0's MDIO (maintenance reg 0xE000B034); needs the MDIO port enabled in NWCTRL bit4.
connect
targets -set -filter {name =~ "ARM*#0"}
proc rd {a r} {
  set cmd [expr {(1<<30) | (2<<28) | ($a<<23) | ($r<<18) | (2<<16)}]
  mwr -force 0xE000B034 $cmd
  after 5
  set v [mrd -force -value 0xE000B034]
  return [expr {$v & 0xFFFF}]
}
mwr -force 0xF8000008 0xDF0D
mwr -force 0xF80007D0 0x00001280
mwr -force 0xF80007D4 0x00001280
set nw [mrd -force -value 0xE000B000]
mwr -force 0xE000B000 [expr {$nw | 0x10}]
for {set a 0} {$a < 32} {incr a} {
  set s [rd $a 1]
  if {$s != 0xFFFF && $s != 0} {
    puts [format "PHY addr %d: id1=%04x id2=%04x status=%04x ctrl=%04x" $a [rd $a 2] [rd $a 3] $s [rd $a 0]]
  }
}
puts "done"
