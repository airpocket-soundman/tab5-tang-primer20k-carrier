set root [file normalize [file join [file dirname [info script]] ../..]]
create_project -name fp32_epilogue -dir [file join $root build npu-fp32-epilogue-synth-v2/project] -pn GW2A-LV18PG256C8/I7 -device_version C -force
add_file [file join $root build/npu-fp32-epilogue-synth-v2/source_snapshot/npu_fp32_epilogue.v]
set_option -top_module npu_fp32_epilogue
set_option -output_base_name fp32_epilogue
run syn
exit

