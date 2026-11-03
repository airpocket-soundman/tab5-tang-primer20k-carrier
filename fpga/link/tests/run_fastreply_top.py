import argparse,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--iverilog',default='iverilog');p.add_argument('--vvp',default='vvp');a=p.parse_args()
sources=['link/rtl/link_reply_raw.v','link/rtl/triangle_batch.v','link/rtl/link_bringup.v','gfx/rtl/gfx_bench.v','gfx/rtl/triangle_tile.v','gfx/rtl/triangle_fragment.v','gfx/rtl/triangle_coverage.v','gfx/rtl/triangle_depth.v','platform/dock/tab5_dock_top.v','platform/dock/dock_pll54.v','platform/dock/tab5_dock_triangle54_fast_top.v','link/tests/tb_fastreply_top.v']
with tempfile.TemporaryDirectory() as td:
 exe=Path(td)/'pll54.vvp';subprocess.run([a.iverilog,'-g2012','-s','tb_fastreply_top','-o',str(exe),*[str(ROOT/s) for s in sources]],check=True);subprocess.run([a.vvp,str(exe)],check=True,timeout=120)
