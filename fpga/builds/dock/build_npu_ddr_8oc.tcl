# Isolated 8OC candidate: USERCODE4E21, unchanged wire CAPS4E20.
# NPU+DDR diagnostic build. Vendor IP is external/pinned and stays ignored.
set root [file normalize [file join [file dirname [info script]] ../..]]
set output [file join $root build npu-ddr-8oc-v1]
if {[file exists $output]} {error "Fresh output required: $output"}
set ip [file join $root build sipeed-ddr-test-e469df4c src ddr3_memory_interface ddr3_memory_interface.v]
set pll [file join $root build memv1 rtl mem_pll.v]
# Verify exact external source before copying; do not execute any download script.
exec python -c {import hashlib,pathlib,sys; p=pathlib.Path(sys.argv[1]); d=p.read_bytes().replace(b'\r\n',b'\n'); assert hashlib.sha256(d).hexdigest()=='04ef287b2caf7779b8464c28f4e2176b35f24b181aab9c7509d8b3d9f734bed2', 'Pinned DDR IP missing/changed'; s=pathlib.Path(sys.argv[2]).read_text(); assert 'pll.IDIV_SEL=3' in s and 'pll.FBDIV_SEL=58' in s and 'pll.ODIV_SEL=2' in s, 'Expected398.25MHzPLL'} $ip $pll
create_project -name npu_ddr -dir $output -pn GW2A-LV18PG256C8/I7 -device_version C -force
foreach source {
 npu/rtl/conv_tile_engine_8oc.v npu/rtl/npu_ddr_tile_loader_8oc.v npu/rtl/npu_ddr_arbiter.v npu/rtl/npu_ddr_sys.v npu/rtl/npu_ddr_core_8oc.v
 mem/rtl/memv1_bridge.v mem/rtl/mem_adapter.v mem/rtl/memv1_crc32b.v
 platform/dock/tab5_dock_npu_ddr_8oc_top.v mem/config/mem_bist.cst
} {
 set snapshot [file join $output source_snapshot $source]
 file mkdir [file dirname $snapshot]
 file copy -force [file join $root $source] $snapshot
 add_file $snapshot
}
set vendor [file join $output external_snapshot ddr3_memory_interface.v]
file mkdir [file dirname $vendor]
file copy -force $ip $vendor
add_file $vendor
set pll_snapshot [file join $output external_snapshot mem_pll.v]
file copy -force $pll $pll_snapshot
add_file $pll_snapshot
set sdc [file join $output npu_ddr_initial.sdc]
set fh [open $sdc w]
puts $fh {create_clock -name sys27 -period 37.037037 [get_ports {sys_clk}]}
puts $fh {create_generated_clock -name memory398 -source [get_ports {sys_clk}] -multiply_by 59 -divide_by 4 [get_nets {memory_clk}]}
puts $fh {create_generated_clock -name user99 -source [get_nets {memory_clk}] -divide_by 4 [get_nets {user_clk}]}
puts $fh {// Initial unwaived diagnostic. No mailbox exceptions, asynchronous clock groups or blanket false paths.}
puts $fh {report_timing -setup -max_paths 100 -max_common_paths 1}
puts $fh {report_timing -hold -max_paths 100 -max_common_paths 1}
puts $fh {report_timing -recovery -max_paths 100 -max_common_paths 1}
puts $fh {report_timing -removal -max_paths 100 -max_common_paths 1}
close $fh
add_file $sdc
set_option -top_module tab5_dock_npu_ddr_8oc_top
set_option -output_base_name npu_ddr
set_option -use_sspi_as_gpio 1
set_option -gen_sdf 1
set_option -gen_verilog_sim_netlist 1
set_option -user_code 00004E21
run all
exit
