# Experimental separate vendor flow; no programming. Existing outputs preserved.
# NOTE: the metadata-CDC proof (generate_metadata_cdc_constraints.py --verify) is NOT re-run: it pins the source SHA of link_reply_raw.v /
# reply_clock_filter.v, which this diagnostic changes. The committed exception SDC from 85bac224 is reused as-is; its 30 exact-name
# metadata paths are unchanged by this branch, but that is not re-proven. Read the STA report, do not assume closure.
set root [file normalize [file join [file dirname [info script]] ../..]]
set output [file join $root build filtered-edge-cdc]
if {[file exists $output]} {error "Fresh output required: $output"}
create_project -name filtered_reply -dir $output -pn GW2A-LV18PG256C8/I7 -device_version C -force
foreach source {
 link/rtl/triangle_batch.v link/rtl/reply_clock_filter.v link/rtl/reply_edge_monitor.v link/rtl/link_reply_raw.v link/rtl/link_bringup_filtered.v
 gfx/rtl/gfx_bench.v gfx/rtl/triangle_tile_vendor.v gfx/rtl/tile_dpram_vendor.v gfx/rtl/triangle_fragment.v
 gfx/rtl/triangle_coverage_pipeline.v gfx/rtl/triangle_depth.v
 platform/dock/dock_pll54.v platform/dock/dock_pll216.v
 platform/dock/tab5_dock_triangle54_filtered_edge_top.v
 constraints/dock/tab5_dock_link_v0.cst constraints/dock/triangle54filtered_batch_cdc.sdc
} {add_file [file join $root $source]}
set_option -top_module tab5_dock_triangle54_filtered_edge_top
set_option -output_base_name filtered_edge
set_option -use_sspi_as_gpio 1
set_option -route_option 1
set_option -gen_sdf 1
set_option -gen_verilog_sim_netlist 1
run all
puts FILTERED_EDGE_CDC_RETURNED
exit
