set root [file normalize [file join [file dirname [info script]] ../..]]
set output [file join $root build request-ff-v1]
if {[file exists $output]} {error "Fresh output required: $output"}
create_project -name request_ff -dir $output -pn GW2A-LV18PG256C8/I7 -device_version C -force
foreach source {
 link/rtl/triangle_batch.v link/rtl/reply_clock_filter.v link/rtl/link_reply_raw.v link/rtl/link_bringup_filtered.v
 gfx/rtl/raster2d.v gfx/rtl/fire_tile.v gfx/rtl/gfx_bench.v gfx/rtl/triangle_tile_vendor.v gfx/rtl/tile_dpram_vendor.v gfx/rtl/triangle_fragment.v
 gfx/rtl/triangle_coverage_pipeline.v gfx/rtl/triangle_depth.v
 platform/dock/dock_pll54.v platform/dock/dock_pll216.v
 platform/dock/tab5_dock_request_ff_top.v
 constraints/dock/tab5_dock_link_v0.cst constraints/dock/all_scenes.sdc
} {
 set snapshot [file join $output source_snapshot $source]
 file mkdir [file dirname $snapshot]
 file copy -force [file join $root $source] $snapshot
 add_file $snapshot
}
set_option -top_module tab5_dock_request_ff_top
set_option -output_base_name request_ff
set_option -use_sspi_as_gpio 1
set_option -route_option 1
set_option -gen_sdf 1
set_option -gen_verilog_sim_netlist 1
run all
puts SPEED_FILTER_CANDIDATE_RETURNED
exit
