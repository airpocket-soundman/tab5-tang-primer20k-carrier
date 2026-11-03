"""Routed sampler-only nextpnr timing-coverage reproduction. Never packs/flashes."""
import argparse,json,subprocess,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--yosys',required=True);p.add_argument('--nextpnr',required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    files=[ROOT/f for f in ['link/rtl/reply_clock_filter.v','platform/dock/dock_pll216.v','link/tests/filter_timing_top.v']]
    synth=a.output/'synth.json';routed=a.output/'routed.json';report=a.output/'timing.json'
    script='read_verilog '+' '.join('"'+p.as_posix()+'"'for p in files)+'; synth_gowin -family gw2a -top filter_timing_top -json "'+synth.as_posix()+'"'
    cmds=[('synthesis',[a.yosys,'-p',script]),('pnr',[a.nextpnr,'--json',synth.as_posix(),'--write',routed.as_posix(),'--device','GW2A-LV18PG256C8/I7','--vopt','family=GW2A-18','--vopt','cst='+(ROOT/'constraints/dock/tab5_dock_link_v0.cst').as_posix(),'--freq','216','--sdc',(ROOT/'constraints/dock/filter_timing_only_oss.sdc').as_posix(),'--report',report.as_posix(),'--detailed-timing-report'])]
    for stage,command in cmds:
        result=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors='replace');(a.output/(stage+'.log')).write_text(result.stdout,encoding='utf-8')
        if result.returncode:raise RuntimeError(f'{stage} failed:{result.returncode}')
    timing=json.loads(report.read_text());netlist=json.loads(routed.read_text())['modules']['top'];clk=netlist['netnames']['filter_clk']['bits']
    registers=[(n,c)for n,c in netlist['cells'].items()if c.get('connections',{}).get('CLK')==clk]
    endpoints=[e for n in timing['detailed_net_timings']for e in n['endpoints']if 'sampler216'in str(e)or 'filter_clk'in str(e)]
    d=dict(hardware_access=False,clocked_sampler_ff_count=len(registers),sampler_detailed_endpoint_count=len(endpoints),
           fmax=timing['fmax'],passthrough_cells=sum('passthrough_lut$'in n for n in netlist['cells']),
           no_pack=True,qualification='coverage-reproduction-only',source_sha256={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in files})
    (a.output/'coverage.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps(d))
if __name__=='__main__':main()
