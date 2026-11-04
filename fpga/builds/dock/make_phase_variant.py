"""Generate ONE reply-phase image variant (wrapper top + Gowin build script). No device access.

One variable per image: pass either --ticks or --fine (the other stays 0) unless you
deliberately combine them and record both. Run the generated build.tcl with gw_sh
yourself; this script never builds or programs.
"""
import argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SOURCES=['link/rtl/triangle_batch.v','link/rtl/reply_clock_filter.v','link/rtl/reply_phase_delay.v','link/rtl/link_reply_raw.v','link/rtl/link_bringup_filtered.v',
 'gfx/rtl/gfx_bench.v','gfx/rtl/triangle_tile_vendor.v','gfx/rtl/tile_dpram_vendor.v','gfx/rtl/triangle_fragment.v','gfx/rtl/triangle_coverage_pipeline.v','gfx/rtl/triangle_depth.v',
 'platform/dock/dock_pll54.v','platform/dock/dock_pll216.v','platform/dock/tab5_dock_triangle54_filtered_phase_top.v',
 'constraints/dock/tab5_dock_link_v0.cst','constraints/dock/triangle54filtered_official.sdc']
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ticks',type=int,default=0);p.add_argument('--fine',type=int,default=0)
    a=p.parse_args()
    if not 0<=a.ticks<=15 or not 0<=a.fine<=127:raise SystemExit('ticks 0..15, fine 0..127')
    name=f'phase_t{a.ticks}_f{a.fine}';out=ROOT/'build'/'phase-variants'/name
    if out.exists():raise SystemExit(f'Fresh output required: {out}')
    out.mkdir(parents=True)
    top=f'tab5_dock_{name}_top'
    (out/'top.v').write_text(f'''// Generated wrapper: REPLY_PHASE_TICKS={a.ticks} REPLY_FINE_DLY={a.fine}
module {top}(input wire sys_clk,reset_n,arm_sw,bus_clk,dir,input wire [3:0]aux,inout wire [7:0]data,output wire ready,output wire [3:0]led);
    tab5_dock_triangle54_filtered_phase_top #(.REPLY_PHASE_TICKS({a.ticks}),.REPLY_FINE_DLY({a.fine})) core(sys_clk,reset_n,arm_sw,bus_clk,dir,aux,data,ready,led);
endmodule
''')
    files=''.join(f' {(ROOT/s).as_posix()}\n' for s in SOURCES)
    (out/'build.tcl').write_text(f'''# Generated. Experimental; synthesis/PnR only, never programs.
create_project -name {name} -dir {(out/'gowin').as_posix()} -pn GW2A-LV18PG256C8/I7 -device_version C -force
foreach source {{
{files} {(out/'top.v').as_posix()}
}} {{add_file $source}}
set_option -top_module {top}
set_option -output_base_name {name}
set_option -use_sspi_as_gpio 1
run all
puts PHASE_FLOW_RETURNED
exit
''')
    print(out/'build.tcl')
if __name__=='__main__':main()
