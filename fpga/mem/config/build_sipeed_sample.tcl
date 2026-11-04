# Builds the UNMODIFIED Sipeed DDR-test sample (commit e469df4c) for GW2A-LV18PG256C8/I7 with the official flow.
# Sources are fetched into fpga/build/sipeed-ddr-test-e469df4c (not committed: contains vendor encrypted IP).
# Never programs any device. Purpose: does the reference design pass on THIS physical Core?
set fpga_root [file normalize [file join [file dirname [info script]] ../..]]
set src [file join $fpga_root build sipeed-ddr-test-e469df4c src]
set output [file join $fpga_root build sipeed-ddr-test-out]
create_project -name sipeed_ddr_test -dir $output -pn GW2A-LV18PG256C8/I7 -device_version C -force
foreach f {ddr3_memory_interface/ddr3_memory_interface.v ddr3_syn_top.v gowin_rpll/gowin_rpll.v tester.v uart_tx_V2.v} {
 add_file [file join $src $f]
}
add_file [file join $src ddr3.cst]
add_file [file join $src ddr3.sdc]
set_option -top_module ddr3_syn_top
set_option -output_base_name sipeed_ddr_test
set_option -include_path $src
# As in the main session's successful build: Dock T10/N9 share SSPI functions.
set_option -use_sspi_as_gpio 1
run all
puts SIPEED_SAMPLE_BUILD_FLOW_RETURNED
exit
