set root [file normalize [file join [file dirname [info script]] ../..]]
create_project -name matmul_sequencer -dir [file join $root build npu-ddr-matmul-sequencer-synth/project] -pn GW2A-LV18PG256C8/I7 -device_version C -force
add_file [file join $root build/npu-ddr-matmul-sequencer-synth/source_snapshot/npu_ddr_matmul_sequencer.v]
set_option -top_module npu_ddr_matmul_sequencer
set_option -output_base_name matmul_sequencer
run syn
exit
