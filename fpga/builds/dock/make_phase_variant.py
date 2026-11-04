"""Generate ONE reply-phase image variant (patched top + Gowin build script). No device access.

The variant top is a copy of tab5_dock_triangle54_filtered_phase_top.v with only the two
parameter DEFAULTS changed, so the instance hierarchy (core/...) stays identical to the
qualified 85bac224 image and its CDC exceptions (constraints/dock/triangle54filtered_batch_cdc.sdc)
still apply. One variable per image: pass --ticks OR --fine (the other stays 0).
This script never builds or programs; run the printed build.tcl with gw_sh yourself.
"""
import argparse,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
TOP='platform/dock/tab5_dock_triangle54_filtered_phase_top.v'
SOURCES=['link/rtl/triangle_batch.v','link/rtl/reply_clock_filter.v','link/rtl/reply_phase_delay.v','link/rtl/link_reply_raw.v','link/rtl/link_bringup_filtered.v',
 'gfx/rtl/gfx_bench.v','gfx/rtl/triangle_tile_vendor.v','gfx/rtl/tile_dpram_vendor.v','gfx/rtl/triangle_fragment.v','gfx/rtl/triangle_coverage_pipeline.v','gfx/rtl/triangle_depth.v',
 'platform/dock/dock_pll54.v','platform/dock/dock_pll216.v']
CONSTRAINTS=['constraints/dock/tab5_dock_link_v0.cst','constraints/dock/triangle54filtered_batch_cdc.sdc']
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ticks',type=int,default=0);p.add_argument('--fine',type=int,default=0)
    a=p.parse_args()
    if not 0<=a.ticks<=15 or not 0<=a.fine<=127:raise SystemExit('ticks 0..15, fine 0..127')
    name=f'phase_t{a.ticks}_f{a.fine}';out=ROOT/'build'/'phase-variants'/name
    if out.exists():raise SystemExit(f'Fresh output required: {out}')
    out.mkdir(parents=True)
    text=(ROOT/TOP).read_text(encoding='utf-8')
    text,n1=re.subn(r'parameter REPLY_PHASE_TICKS = 0',f'parameter REPLY_PHASE_TICKS = {a.ticks}',text)
    text,n2=re.subn(r'parameter REPLY_FINE_DLY = 0',f'parameter REPLY_FINE_DLY = {a.fine}',text)
    if n1!=1 or n2!=1:raise SystemExit('top parameter defaults not found')
    (out/'top.v').write_text(f'// Generated variant {name}: only the parameter defaults differ from {TOP}\n'+text,encoding='utf-8')
    files=''.join(f' {(ROOT/s).as_posix()}\n' for s in SOURCES+CONSTRAINTS)
    (out/'build.tcl').write_text(f'''# Generated. Experimental; synthesis/PnR only, never programs.
create_project -name filtered_reply -dir {(out/'gowin').as_posix()} -pn GW2A-LV18PG256C8/I7 -device_version C -force
foreach source {{
{files} {(out/'top.v').as_posix()}
}} {{add_file $source}}
set_option -top_module tab5_dock_triangle54_filtered_phase_top
set_option -output_base_name {name}
set_option -use_sspi_as_gpio 1
set_option -route_option 1
set_option -gen_sdf 1
set_option -gen_verilog_sim_netlist 1
run all
puts PHASE_FLOW_RETURNED
exit
''',encoding='utf-8')
    print(out/'build.tcl')
if __name__=='__main__':main()
