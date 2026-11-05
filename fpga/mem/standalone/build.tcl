set fpga_root [file normalize [file join [file dirname [info script]] ../..]]
set dir [file join $fpga_root mem standalone]
set ip [file join $fpga_root build sipeed-ddr-test-e469df4c src]
create_project -name ddr_bw_standalone -dir [file join $fpga_root build ddr-bw-standalone] -pn GW2A-LV18PG256C8/I7 -device_version C -force
foreach f [list [file join $ip ddr3_memory_interface ddr3_memory_interface.v] [file join $dir mem_pll.v] [file join $fpga_root mem rtl mem_bw.v] [file join $dir standalone.v] [file join $dir standalone.cst] [file join $dir standalone.sdc]] {add_file $f}
set_option -top_module ddr_bw_top
set_option -output_base_name ddr_bw_standalone
set_option -include_path $ip
set_option -use_sspi_as_gpio 1
run all
exit
