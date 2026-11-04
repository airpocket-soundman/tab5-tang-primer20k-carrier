set_device GW2A-LV18PG256C8/I7 -device_version C
add_file -type verilog compute_simd.v
add_file -type verilog pnr_top.v
add_file -type cst pnr.cst
add_file -type sdc pnr.sdc
set_option -top_module pnr_top
set_option -verilog_std sysv2017
set_option -use_sspi_as_gpio 1
set_option -use_ready_as_gpio 1
set_option -use_done_as_gpio 1
set_option -use_mspi_as_gpio 1
run all
