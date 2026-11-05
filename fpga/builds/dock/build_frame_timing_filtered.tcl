set root [file normalize [file join [file dirname [info script]] ../..]]
set output [file join $root build frame-timing-filtered-v2]
if {[file exists $output]} {error "Fresh output required: $output"}
create_project -name frame_timing -dir $output -pn GW2A-LV18PG256C8/I7 -device_version C -force
foreach source {
 link/rtl/triangle_batch.v link/rtl/reply_clock_filter.v link/rtl/link_reply_raw.v link/rtl/link_bringup_filtered.v
 gfx/rtl/raster2d.v gfx/rtl/fire_tile.v gfx/rtl/gfx_bench.v gfx/rtl/triangle_tile_vendor.v gfx/rtl/tile_dpram_vendor.v gfx/rtl/triangle_fragment.v
 gfx/rtl/triangle_coverage_pipeline.v gfx/rtl/triangle_depth.v
 platform/dock/dock_pll54.v platform/dock/dock_pll216.v
 platform/dock/tab5_dock_frame_timing_top.v
 constraints/dock/tab5_dock_link_v0.cst constraints/dock/all_scenes.sdc
} {add_file [file join $root $source]}
set_option -top_module tab5_dock_frame_timing_top
set_option -output_base_name frame_timing
set_option -use_sspi_as_gpio 1
set_option -route_option 1
set_option -gen_sdf 1
set_option -gen_verilog_sim_netlist 1
run all
puts FRAME_TIMING_FILTERED_BUILD_RETURNED
exit
