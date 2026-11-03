# Experimental separate vendor flow; no programming. Existing outputs preserved.
set root [file normalize [file join [file dirname [info script]] ../..]]
set output [file join $root build filtered-batch-official]
if {[file exists $output]} {error "Fresh output required: $output"}
create_project -name filtered_reply -dir $output -pn GW2A-LV18PG256C8/I7 -device_version C -force
foreach source {
 link/rtl/triangle_batch.v link/rtl/reply_clock_filter.v link/rtl/link_reply_raw.v link/rtl/link_bringup_filtered.v
 gfx/rtl/gfx_bench.v gfx/rtl/triangle_tile_vendor.v gfx/rtl/tile_dpram_vendor.v gfx/rtl/triangle_fragment.v
 gfx/rtl/triangle_coverage_pipeline.v gfx/rtl/triangle_depth.v
 platform/dock/dock_pll54.v platform/dock/dock_pll216.v
 platform/dock/tab5_dock_triangle54_filtered_top.v
 constraints/dock/tab5_dock_link_v0.cst constraints/dock/triangle54filtered_official.sdc
} {add_file [file join $root $source]}
set_option -top_module tab5_dock_triangle54_filtered_top
set_option -output_base_name filtered_reply
set_option -use_sspi_as_gpio 1
run all
puts FILTERED_BATCH_FLOW_RETURNED
exit
