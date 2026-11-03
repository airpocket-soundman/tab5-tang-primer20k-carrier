set root [file normalize [file join [file dirname [info script]] ../..]]
set output [file join $root build filter-timing-only-official]
if {[file exists $output]} {error "Fresh output required"}
create_project -name filter_timing -dir $output -pn GW2A-LV18PG256C8/I7 -device_version C -force
foreach source {link/rtl/reply_clock_filter.v platform/dock/dock_pll216.v link/tests/filter_timing_top.v constraints/dock/tab5_dock_link_v0.cst constraints/dock/filter_timing_only.sdc} {add_file [file join $root $source]}
set_option -top_module filter_timing_top
set_option -output_base_name filter_timing
set_option -use_sspi_as_gpio 1
run all
puts FILTER_TIMING_ONLY_FLOW_RETURNED
exit
