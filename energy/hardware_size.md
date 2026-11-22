# PiSe detector hardware size (gate / transistor estimate)

Source: the HLS-exported RTL that went into the board build (`hls/ip/{image_change,change_ir,audio_bands}/hdl/verilog`), synthesised with Yosys 0.57 to a
generic gate netlist (flatten, techmap, ABC mapped to NAND2 + inverter only, flops left as plain D flip-flops, RAMs kept as memories).
`change_rgb` is not in the board design and is not counted. Not counted: PS7 (hard ARM block), AXI interconnect and reset (~1,600 LUTs).

## Result

| Detector | NAND2 | INV | Flip-flops | Logic + flops (transistors) | Logic + flops (gate eq.) | RAM bits | RAM (transistors) |
|---|---|---|---|---|---|---|---|
| image_change | 16,710 | 6,301 | 2,954 | 138,522 | 34,630 | 178,526 | 1,071,156 |
| change_ir | 16,842 | 5,960 | 2,228 | 123,848 | 30,962 | 161,502 | 969,012 |
| audio_bands | 68,653 | 29,416 | 3,253 | 398,504 | 99,626 | 46,302 | 277,812 |
| **Sum** | 102,205 | 41,677 | 8,435 | **660,874** | **165,219** | 386,330 | **2,317,980** |

Everything together: about 3.0 million transistors (0.66 M logic and flops, 2.3 M RAM).

Video (RGB) and audio detectors only, i.e. image_change + audio_bands: 537,026 transistors for logic and flops (about 134k gate equivalents) and 224,828 RAM bits (about 1.35 M transistors as 6T cells). The IR detector (`change_ir`) is not part of this subtotal.

FPGA view of the same design (Vivado 2024.2, xc7z020, routed): 6,884 LUTs, 8,932 flip-flops, 26 DSP48, 18.5 BRAM tiles.
Per block (LUT / FF / DSP / BRAM36+18): image_change 2,177 / 2,697 / 0 / 5+1, change_ir 1,500 / 1,845 / 5 / 8+2, audio_bands 1,616 / 2,394 / 21 / 2+4.

## Assumptions (change them in one place if your comparison uses others)
- 1 gate equivalent (GE) = one NAND2 = 4 transistors; inverter = 2 transistors.
- Flip-flop = 20 transistors (static master-slave). Enable and reset were converted into logic and counted as gates.
- RAM = 6 transistors per bit (6T SRAM cell), without sense amplifiers / decoders.

## Caveats
- No vendor standard-cell library was available, so this is a technology-independent count; a real library mapping would differ by roughly +-20 %.
- audio_bands is large mainly because its 21 multipliers are expanded to plain gates (Yosys array multipliers); the FPGA used DSP48 blocks for them.
- The counts include the HLS AXI-lite control registers and AXI master wrappers (RAM bits of those: 9,182 / 8,670 / 35,294), which a purpose-built chip would not need in this form.
- Small memories that Yosys converted into registers are inside the flip-flop count, not the RAM bits.
