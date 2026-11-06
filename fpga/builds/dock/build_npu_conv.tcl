set root [file normalize [file join [file dirname [info script]] ../..]]
set output [file join $root build npu-conv-v1b]
if {[file exists $output]} {error "Fresh output required: $output"}
create_project -name npu_conv -dir $output -pn GW2A-LV18PG256C8/I7 -device_version C -force
foreach source {
 npu/rtl/conv_tile_engine.v npu/rtl/npu_conv_link.v platform/dock/tab5_dock_npu_conv_top.v
 constraints/dock/tab5_dock_link_v0.cst constraints/dock/tab5_dock.sdc
} {
 set snapshot [file join $output source_snapshot $source]
 file mkdir [file dirname $snapshot]
 file copy -force [file join $root $source] $snapshot
 add_file $snapshot
}
set_option -top_module tab5_dock_npu_conv_top
set_option -output_base_name npu_conv
set_option -use_sspi_as_gpio 1
set_option -user_code 00004E11
run all
exit
