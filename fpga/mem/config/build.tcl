# Generate IP with generate_ip.tcl first. Never programs any device.
set fpga_root [file normalize [file join [file dirname [info script]] ../..]]
# Guarded sources must never overwrite preserved5c481b7 unwaived/scoped20 outputs.
set output [file join $fpga_root build mem-bist-guarded-unwaived]
set timing_file [file join $fpga_root mem config mem_bist.sdc]
if {[info exists env(MEM_BIST_SCOPED)] && $env(MEM_BIST_SCOPED) eq "1"} {
 set output [file join $fpga_root build mem-bist-guarded-scoped20]
 set timing_file [file join $fpga_root build mem-bist-scoped-input mem_bist.sdc]
}
if {[info exists env(MEM_BIST_GUARDED)] && $env(MEM_BIST_GUARDED) eq "1"} {
 set output [file join $fpga_root build mem-native-diag]
 set timing_file [file join $fpga_root build mem-native-diag-input mem_bist.sdc]
}
create_project -name mem_bist -dir $output -pn GW2A-LV18PG256C8/I7 -device_version C -force
foreach name {mem_pll mem_bist mem_mailbox mem_link mem_top} {
 add_file [file join $fpga_root mem rtl ${name}.v]
}
add_file [file join $fpga_root build mem-bist-ip generated MemDDR3 MemDDR3.vo]
add_file [file join $fpga_root mem config mem_bist.cst]
add_file $timing_file
set_option -top_module mem_top
set_option -output_base_name mem_bist
# SUG100 PDF129: existing Dock T10 reset/N9 AUX share SSPI functions.
# Reuse them as the same GPIO already used by verified GFX; keep JTAG intact.
set_option -use_sspi_as_gpio 1
run all
puts MEM_BUILD_FLOW_RETURNED
exit
