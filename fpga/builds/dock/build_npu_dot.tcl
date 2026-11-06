set root [file normalize [file join [file dirname [info script]] ../..]]
set output [file join $root build npu-dot-v0b]
if {[file exists $output]} {error "Fresh output required: $output"}
create_project -name npu_dot -dir $output -pn GW2A-LV18PG256C8/I7 -device_version C -force
foreach source {
 link/rtl/link_bringup.v link/rtl/link_reply_raw.v
 npu/rtl/npu_dot_command.v npu/rtl/int8_dot_job.v npu/rtl/int8_mac_lane.v npu/rtl/int8_requantize.v
 platform/dock/tab5_dock_top.v platform/dock/tab5_dock_npu_top.v
 constraints/dock/tab5_dock_link_v0.cst constraints/dock/tab5_dock.sdc
} {
 set snapshot [file join $output source_snapshot $source]
 file mkdir [file dirname $snapshot]
 file copy -force [file join $root $source] $snapshot
 add_file $snapshot
}
set_option -top_module tab5_dock_npu_top
set_option -output_base_name npu_dot
set_option -use_sspi_as_gpio 1
set_option -user_code 00004E02
run all
exit
