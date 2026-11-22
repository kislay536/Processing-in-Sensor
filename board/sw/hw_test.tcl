# Hardware bring-up test of the three PL detectors, driven over JTAG (no firmware). Compares every output with the golden vectors (image detector: image_detector.ImageChangeDetector; IR/audio: sensors/golden.py).
#   xsdb board/sw/hw_test.tcl <dir with ps7_init.tcl and eventcam.bit (unzipped XSA)> <hls/vectors dir>
set xdir [lindex $argv 0]
set vdir [lindex $argv 1]
set IMG 0x40000000; set IR 0x40010000; set AUD 0x40020000
set IMG_BUF 0x10000000; set IR_BUF 0x18000000; set AUD_BUF 0x1C000000
connect
targets -set -filter {name =~ "APU*"}
rst -system
after 2000
targets -set -filter {name =~ "ARM*#0"}
catch {stop}
source $xdir/ps7_init.tcl
ps7_init
targets -set -filter {name =~ "xc7z*"}
fpga -file $xdir/eventcam.bit
targets -set -filter {name =~ "ARM*#0"}
ps7_post_config
puts "PL programmed"
proc r32 {a} { return [expr {[mrd -force -value $a] & 0xFFFFFFFF}] }
proc w32 {a v} { mwr -force $a $v }
proc run_ip {base} {
  w32 $base 1
  for {set i 0} {$i < 2000} {incr i} { if {[r32 $base] & 2} { return 1 } }
  return 0
}
proc s64 {hi lo} { set v [expr {($hi << 32) | $lo}]; if {$hi & 0x80000000} { set v [expr {$v - (1 << 64)}] }; return $v }

foreach {name base buf fbytes} [list ir $IR $IR_BUF 230400] {
  dow -data $vdir/${name}_frames.bin $buf
  set fh [open $vdir/${name}_exp.txt]; set lines [split [string trim [read $fh]] "\n"]; close $fh
  set ok 0; set bad 0; set i 0
  foreach ln $lines {
    lassign $ln thr sh rst ech esum esc efr
    w32 [expr {$base + 0x10}] [expr {$buf + $i * $fbytes}]
    w32 [expr {$base + 0x1c}] $thr; w32 [expr {$base + 0x24}] $sh; w32 [expr {$base + 0x2c}] $rst
    if {![run_ip $base]} { puts "$name frame $i: TIMEOUT (ap_done never set)"; incr bad; incr i; continue }
    set ch [r32 [expr {$base + 0x34}]]; set sm [r32 [expr {$base + 0x44}]]; set sc [r32 [expr {$base + 0x54}]]; set fr [r32 [expr {$base + 0x64}]]
    if {$ch == $ech && $sm == $esum && $sc == $esc && $fr == $efr} { incr ok } else { incr bad; puts "$name frame $i MISMATCH: changed $ch (exp $ech) sum $sm (exp $esum) score $sc (exp $esc) frames $fr (exp $efr)" }
    incr i
  }
  puts "HW $name: $ok/[expr {$ok + $bad}] frames match the golden model"
}

# ---- colour camera: full image-change detector (image_change IP). Frames are stored compactly (rows 112..367 only, 327680 B each);
# the IP takes the address of the crop's first pixel (row 112, column 64): compact buffer + 128 B.
dow -data $vdir/image_frames.bin $IMG_BUF
set fh [open $vdir/image_exp.txt]; set lines [split [string trim [read $fh]] "\n"]; close $fh
set offs {0x1c 0x24 0x2c 0x34 0x3c 0x44 0x4c 0x54 0x5c 0x64 0x6c 0x74 0x7c 0x84}
set onames {fired reason score region_pass active changed persistence frames}
set ooffs {0x8c 0x9c 0xac 0xbc 0xcc 0xdc 0xec 0x140}
set ok 0; set bad 0; set i 0
foreach ln $lines {
  set vals [split $ln " "]
  w32 [expr {$IMG + 0x10}] [expr {$IMG_BUF + $i * 327680 + 128}]
  for {set k 0} {$k < 14} {incr k} { w32 [expr {$IMG + [lindex $offs $k]}] [lindex $vals $k] }
  if {![run_ip $IMG]} { puts "image frame $i: TIMEOUT (ap_done never set)"; incr bad; incr i; continue }
  set match 1
  for {set k 0} {$k < 8} {incr k} {
    set got [expr {[r32 [expr {$IMG + [lindex $ooffs $k]}]] & 0xFFFFFFFF}]
    if {[lindex $onames $k] ne "frames" && [lindex $onames $k] ne "changed" && [lindex $onames $k] ne "persistence"} { set got [expr {$got & 0xFF}] } elseif {[lindex $onames $k] ne "frames"} { set got [expr {$got & 0xFFFF}] }
    if {$got != [lindex $vals [expr {14 + $k}]]} { set match 0; puts "image frame $i [lindex $onames $k]: got $got exp [lindex $vals [expr {14 + $k}]]" }
  }
  for {set k 0} {$k < 64} {incr k} {
    set w [r32 [expr {$IMG + 0x100 + 4 * ($k / 4)}]]
    set got [expr {($w >> (8 * ($k % 4))) & 0xFF}]
    if {$got != [lindex $vals [expr {22 + $k}]]} { set match 0; puts "image frame $i cell $k: got $got exp [lindex $vals [expr {22 + $k}]]" }
  }
  if {$match} { incr ok } else { incr bad }
  incr i
}
puts "HW image: $ok/[expr {$ok + $bad}] frames match the golden model"

dow -data $vdir/audio_blocks.bin $AUD_BUF
set fh [open $vdir/audio_exp.txt]; set lines [split [string trim [read $fh]] "\n"]; close $fh
set ok 0; set bad 0; set i 0
foreach ln $lines {
  w32 [expr {$AUD + 0x10}] [expr {$AUD_BUF + $i * 1024}]
  if {![run_ip $AUD]} { puts "audio block $i: TIMEOUT"; incr bad; incr i; continue }
  set match 1
  for {set k 0} {$k < 8} {incr k} {
    set lo [r32 [expr {$AUD + 0x40 + 8 * $k}]]; set hi [r32 [expr {$AUD + 0x44 + 8 * $k}]]
    if {[s64 $hi $lo] != [lindex $ln $k]} { set match 0; puts "audio block $i band $k: got [s64 $hi $lo] exp [lindex $ln $k]" }
  }
  set ss [expr {([r32 [expr {$AUD + 0x20}]] << 32) | [r32 [expr {$AUD + 0x1c}]]}]
  if {$ss != [lindex $ln 8] || [r32 [expr {$AUD + 0x80}]] != [lindex $ln 9]} { set match 0; puts "audio block $i sum_sq/blocks mismatch: $ss [r32 [expr {$AUD + 0x80}]]" }
  if {$match} { incr ok } else { incr bad }
  incr i
}
puts "HW audio: $ok/[expr {$ok + $bad}] blocks match the golden model"
