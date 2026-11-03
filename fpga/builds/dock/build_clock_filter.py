"""Isolated216MHz reply conditioning synthesis/PNR. No programming or waivers."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
ROOT=Path(__file__).resolve().parents[2]
SOURCES=['link/rtl/reply_clock_filter.v','link/rtl/link_reply_raw.v','link/rtl/link_bringup_filtered.v',
         'gfx/rtl/gfx_bench.v','gfx/rtl/triangle_tile.v','gfx/rtl/triangle_fragment.v','gfx/rtl/triangle_coverage.v',
         'gfx/rtl/triangle_depth.v','platform/dock/dock_pll54.v','platform/dock/dock_pll216.v',
         'platform/dock/tab5_dock_triangle54_filtered_top.v']
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('yosys','nextpnr','pack'):p.add_argument('--'+key,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise ValueError('Unique fresh output required')
    a.output.mkdir(parents=True)
    files=[ROOT/s for s in SOURCES]
    cst=ROOT/'constraints/dock/tab5_dock_link_v0.cst';sdc=ROOT/'constraints/dock/triangle54filtered.sdc'
    quote=lambda p:'"'+p.as_posix()+'"'
    synth=a.output/'synth.json';route=a.output/'output.pnr.json';fs=a.output/'output.fs'
    commands=[('synthesis',[a.yosys,'-p','read_verilog '+' '.join(map(quote,files))+'; synth_gowin -family gw2a -top tab5_dock_triangle54_filtered_top -json '+quote(synth)]),
              ('pnr',[a.nextpnr,'--json',synth.as_posix(),'--write',route.as_posix(),'--device','GW2A-LV18PG256C8/I7','--vopt','family=GW2A-18','--vopt','cst='+cst.as_posix(),'--freq','216','--sdc',sdc.as_posix()]),
              ('pack',[a.pack,'-d','GW2A-18','--sspi_as_gpio',route.as_posix(),'-o',fs.as_posix()])]
    report=dict(hardware_access=False,status='running',clocks_mhz=dict(osc=27,core=54,sampler=216,conditioned_conservative=54),
                source_sha256={str(s.relative_to(ROOT)):hashlib.sha256(s.read_bytes()).hexdigest()for s in files+[cst,sdc]},stages=[])
    for stage,cmd in commands:
        r=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors='replace')
        (a.output/(stage+'.log')).write_text(r.stdout,encoding='utf-8')
        ok=r.returncode==0 and 'matched no objects' not in r.stdout
        report['stages'].append(dict(stage=stage,command=cmd,exit_code=r.returncode,passed=ok))
        report['status']='running'if ok else 'failed'
        (a.output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
        print(stage,ok,flush=True)
        if not ok:return 1
    report['status']='pack_passed_not_hardware_qualified'
    report['fs_sha256']=hashlib.sha256(fs.read_bytes()).hexdigest()
    (a.output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    return 0
if __name__=='__main__':raise SystemExit(main())
