# Generate IP with generate_ip.tcl first. Never programs any device.
set fpga_root [file normalize [file join [file dirname [info script]] ../..]]
# Guarded sources must never overwrite preserved5c481b7 unwaived/scoped20 outputs.
set output [file join $fpga_root build mem-bist-guarded-unwaived]
# MEM_IP_TAG (e.g. clk400): use the tagged IP-derived inputs (tapped VO, guarded SDC)
set tag ""
if {[info exists env(MEM_IP_TAG)] && $env(MEM_IP_TAG) ne ""} {set tag -$env(MEM_IP_TAG)}
set timing_file [file join $fpga_root mem config mem_bist.sdc]
if {[info exists env(MEM_BIST_SCOPED)] && $env(MEM_BIST_SCOPED) eq "1"} {
 set output [file join $fpga_root build mem-bist-guarded-scoped20]
 set timing_file [file join $fpga_root build mem-bist-scoped-input mem_bist.sdc]
}
if {[info exists env(MEM_BIST_GUARDED)] && $env(MEM_BIST_GUARDED) eq "1"} {
 set output [file join $fpga_root build mem-scheduler-diag]
 set timing_file [file join $fpga_root build mem-scheduler-diag-input$tag mem_bist.sdc]
}
set rtl_dir [file join $fpga_root mem rtl]
# DDR3 isolation variants (prepare_variant.py): same flow, single-item RTL change, own output dir.
if {[info exists env(MEM_VARIANT)] && $env(MEM_VARIANT) ne ""} {
set rtl_dir [file join $fpga_root build mem-variant-$env(MEM_VARIANT) rtl]
 set output [file join $fpga_root build mem-variant-$env(MEM_VARIANT) out]
 set variant_sdc [file join $fpga_root build mem-variant-$env(MEM_VARIANT) mem_bist.sdc]
 if {[file exists $variant_sdc]} {set timing_file $variant_sdc}
}
create_project -name mem_bist -dir $output -pn GW2A-LV18PG256C8/I7 -device_version C -force
foreach name {mem_deep_monitor mem_pll mem_bist mem_mailbox mem_link mem_top} {
 add_file [file join $rtl_dir ${name}.v]
}
if {[info exists env(MEM_VARIANT)] && $env(MEM_VARIANT) eq "sampleip"} {
 # Sipeed sample IP (fetched, not committed): bisect OUR logic vs THEIR IP
 add_file [file join $fpga_root build sipeed-ddr-test-e469df4c src ddr3_memory_interface ddr3_memory_interface.v]
} else {
 add_file [file join $fpga_root build mem-deep-input$tag MemDDR3_tapped.vo]
}
add_file [file join $fpga_root mem config mem_bist.cst]
if {[info exists env(MEM_VARIANT)] && $env(MEM_VARIANT) eq "sampleip"} {set timing_file [file join $fpga_root mem config mem_bist_sampleip.sdc]}
add_file $timing_file
if {[info exists env(MEM_VARIANT)] && $env(MEM_VARIANT) eq "sampleip"} {set_option -include_path [file join $fpga_root build sipeed-ddr-test-e469df4c src]}
set_option -top_module mem_top
set_option -output_base_name mem_bist
# SUG100 PDF129: existing Dock T10 reset/N9 AUX share SSPI functions.
# Reuse them as the same GPIO already used by verified GFX; keep JTAG intact.
set_option -use_sspi_as_gpio 1
run all
puts MEM_BUILD_FLOW_RETURNED
exit
