set output [file normalize [file dirname [info script]]]
create_project -name local_cpu -dir [file join $output project] -pn GW2A-LV18PG256C8/I7 -device_version C -force
add_file [file join $output source_snapshot picorv32_local.v]
add_file [file join $output source_snapshot npu_local_cpu_subsystem.v]
add_file [file join $output source_snapshot npu_rv32_ddr_cache.v]
add_file [file join $output source_snapshot npu_local_rv32_regs.v]
add_file [file join $output clock.sdc]
set_option -top_module npu_local_cpu_subsystem
set_option -output_base_name local_cpu
run syn
exit
