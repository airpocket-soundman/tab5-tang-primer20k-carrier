# MEMV1 image (old Sipeed sample IP, 400MHz). Never programs any device. Prereq: python fpga/mem/tests/prepare_memv1.py
set fpga_root [file normalize [file join [file dirname [info script]] ../..]]
set build_name memv1
if {[info exists ::env(MEMV1_FAST_REPLY)] && $::env(MEMV1_FAST_REPLY) eq "1"} {set build_name memv1-fast}
set rtl_dir [file join $fpga_root build $build_name rtl]
set output [file join $fpga_root build $build_name out]
set sample [file join $fpga_root build sipeed-ddr-test-e469df4c src]
create_project -name mem_bist -dir $output -pn GW2A-LV18PG256C8/I7 -device_version C -force
foreach name {memv1_crc32b mem_pll mem_bist mem_mailbox mem_adapter memv1_bridge memv1_sys mem_v1_core mem_v1_top} {
 add_file [file join $rtl_dir ${name}.v]
}
if {$build_name eq "memv1-fast"} {
 foreach name {memv1_reply_raw reply_clock_filter dock_pll216} {add_file [file join $rtl_dir ${name}.v]}
}
if {![file exists [file join $sample ddr3_memory_interface ddr3_memory_interface.v]]} {error "pinned Sipeed IP missing: run prepare_memv1.py --ip-src"}
add_file [file join $sample ddr3_memory_interface ddr3_memory_interface.v]
add_file [file join $fpga_root mem config mem_bist.cst]
add_file [file join $fpga_root build $build_name mem_v1.sdc]
set_option -include_path $sample
set_option -top_module mem_v1_top
set_option -output_base_name mem_bist
set_option -use_sspi_as_gpio 1
run all
puts MEM_BUILD_FLOW_RETURNED
exit
