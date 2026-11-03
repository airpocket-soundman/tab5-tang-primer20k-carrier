# Usage: gw_sh build.tcl link|gfx (run in this directory or pass absolute path).
set here [file dirname [file normalize [info script]]]
set root [file normalize [file join $here ../..]]
set variant link
if {$argc > 0} { set variant [lindex $argv 0] }
if {$variant ni {link gfx}} { error "Expected link or gfx" }
set top tab5_dock_top
if {$variant eq "gfx"} { set top tab5_dock_gfx_top }
set out [file join $root build dock-$variant]
file mkdir $out
cd $out
set_device -name GW2A-18C GW2A-LV18PG256C8/I7
add_file [file join $root link rtl link_bringup.v]
add_file [file join $root gfx rtl gfx_bench.v]
add_file [file join $root platform dock tab5_dock_top.v]
add_file [file join $root platform dock tab5_dock_gfx_top.v]
add_file [file join $root constraints dock tab5_dock_link_v0.cst]
add_file [file join $root constraints dock tab5_dock.sdc]
set_option -top_module $top
set_option -output_base_name dock_$variant
# Key_0/T10 is SI/D2 (SSPI), not RECONFIG_N. Release SSPI to GPIO.
# Sipeed official HDMI project likewise enables SSPI pin reuse.
set_option -use_sspi_as_gpio 1
# Keep JTAG/MSPI/RECONFIG pins available. Not yet run in Gowin EDA.
run all
