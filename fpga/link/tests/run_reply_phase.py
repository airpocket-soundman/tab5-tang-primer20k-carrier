"""Reply-phase (track N) simulation: REPLY_PHASE_TICKS sweep. No hardware access."""
import argparse,json,re,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
FILES=['link/rtl/reply_clock_filter.v','link/rtl/reply_phase_delay.v','link/rtl/link_reply_raw.v','link/rtl/link_bringup_filtered.v',
       'gfx/rtl/gfx_bench.v','gfx/rtl/triangle_tile.v','gfx/rtl/triangle_fragment.v','gfx/rtl/triangle_coverage.v','gfx/rtl/triangle_depth.v',
       'link/rtl/triangle_batch.v','link/tests/lut1_model.v','link/tests/tb_reply_phase.v']
TICK_PS=4630
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--iverilog',required=True);p.add_argument('--vvp',required=True)
    p.add_argument('--ticks',type=int,nargs='*',default=[0,1,2,3,5,8,15]);p.add_argument('--output',type=Path);a=p.parse_args()
    res={}
    with tempfile.TemporaryDirectory(prefix='reply-phase-')as td:
        for t in a.ticks:
            exe=Path(td)/f't{t}.vvp'
            subprocess.run([a.iverilog,'-g2012','-s','tb_reply_phase',f'-Ptb_reply_phase.TICKS={t}','-o',str(exe),*[str(ROOT/f)for f in FILES]],check=True,capture_output=True)
            r=subprocess.run([a.vvp,str(exe)],text=True,capture_output=True,timeout=900)
            if r.returncode or 'PASS' not in r.stdout or 'FATAL' in r.stdout:raise SystemExit(f'TICKS={t} FAILED\n'+r.stdout+r.stderr)
            m=re.search(r'dmin_ps=(\d+) dmax_ps=(\d+)',r.stdout);res[t]=(int(m.group(1)),int(m.group(2)))
            print(f'ticks={t} data-change delay after host CLK rise: min={res[t][0]}ps max={res[t][1]}ps')
    base=res[0][0]if 0 in res else None
    if base is not None:
        for t,(lo,hi) in res.items():
            if abs((lo-base)-t*TICK_PS)>1500:raise SystemExit(f'TICKS={t}: added delay {lo-base}ps != {t*TICK_PS}ps')
        print('added delay matches ticks x 4.63ns (+-1.5ns)')
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(dict(hardware_access=False,passed=True,delay_ps={str(k):v for k,v in res.items()}),indent=2)+'\n')
if __name__=='__main__':main()
