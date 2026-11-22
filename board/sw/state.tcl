connect
targets -set -filter {name =~ "ARM*#0"}
puts "STATE: [state]"
puts [format "NWSR=0x%08x RXSR=0x%08x RXCNT(0xE000B1A4)=%d" [mrd -force -value 0xE000B008] [mrd -force -value 0xE000B020] [mrd -force -value 0xE000B1A4]]
