"""Edge-monitor (track J) simulation: EDGE_MONITOR_ENABLE 0 and 1. No hardware access."""
import argparse,json,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
FILES=['link/rtl/reply_clock_filter.v','link/rtl/reply_edge_monitor.v','link/rtl/link_reply_raw.v','link/rtl/link_bringup_filtered.v',
       'gfx/rtl/gfx_bench.v','gfx/rtl/triangle_tile.v','gfx/rtl/triangle_fragment.v','gfx/rtl/triangle_coverage.v','gfx/rtl/triangle_depth.v',
       'link/rtl/triangle_batch.v','link/tests/lut1_model.v','link/tests/tb_edge_monitor.v']
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--iverilog',required=True);p.add_argument('--vvp',required=True)
    p.add_argument('--output',type=Path);a=p.parse_args();out={}
    with tempfile.TemporaryDirectory(prefix='edge-monitor-')as td:
        for edge in (0,1):
            exe=Path(td)/f'e{edge}.vvp'
            subprocess.run([a.iverilog,'-g2012','-s','tb_edge_monitor',f'-Ptb_edge_monitor.EDGE={edge}','-o',str(exe),*[str(ROOT/f)for f in FILES]],check=True,capture_output=True)
            r=subprocess.run([a.vvp,str(exe)],text=True,capture_output=True,timeout=900)
            if r.returncode or 'PASS' not in r.stdout or 'FATAL' in r.stdout:raise SystemExit(f'EDGE={edge} FAILED\n'+r.stdout+r.stderr)
            out[f'EDGE={edge}']=r.stdout;print(r.stdout)
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(dict(hardware_access=False,passed=True,runs=out),indent=2)+'\n')
if __name__=='__main__':main()
