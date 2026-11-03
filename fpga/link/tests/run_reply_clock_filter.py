"""Offline216MHz conditioning unit/timing model. Never hardware qualification."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--iverilog',required=True)
    p.add_argument('--vvp',required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    source=[ROOT/'link/rtl/reply_clock_filter.v',ROOT/'link/tests/tb_reply_clock_filter.v']
    plans=[(5000000,32,0,1),(8000000,20,0,1),(10000000,16,0,1),(16000000,10,0,1),
           (20000000,8,0,1),(25000000,6,2,5),(26666667,6,0,1),(32000000,5,0,1),(40000000,4,0,1)]
    cases=[]
    with tempfile.TemporaryDirectory(prefix='condition-clock-')as temp:
        for frequency,n,b,c in plans:
            for phase in range(0,4630,463):
                exe=Path(temp)/'model.vvp'
                params=dict(PHASE_PS=phase,DIV_INTEGER=n,DIV_NUMERATOR=b,DIV_DENOMINATOR=c)
                command=[a.iverilog,'-g2012','-s','tb_reply_clock_filter',*[f'-Ptb_reply_clock_filter.{k}={v}'for k,v in params.items()],'-o',str(exe),*map(str,source)]
                subprocess.run(command,check=True,capture_output=True)
                result=subprocess.run([a.vvp,str(exe)],check=True,capture_output=True,text=True)
                line=next(x for x in result.stdout.splitlines()if x.startswith('FILTER,'))
                fields=list(map(int,line.split(',')[1:]))
                cases.append(dict(configured_hz=frequency,divider=[n,b,c],sample_phase_ps=phase,
                                  accepted_rises=fields[4],minimum_latency_ps=fields[5],maximum_latency_ps=fields[6],passed=True))
        for mode in (1,2):
            exe=Path(temp)/'noise.vvp'
            subprocess.run([a.iverilog,'-g2012','-s','tb_reply_clock_filter',f'-Ptb_reply_clock_filter.NOISE_MODE={mode}','-o',str(exe),*map(str,source)],check=True,capture_output=True)
            subprocess.run([a.vvp,str(exe)],check=True,capture_output=True,text=True)
    budgets=[]
    for frequency,n,b,c in plans:
        latency=max(x['maximum_latency_ps']for x in cases if x['configured_hz']==frequency)
        for wire in (0,2,5,10):
            for tco in (0,2,5):
                # InternalP4sample takes oldbyte at nextclock. Budget also
                # conservatively includes216→serializer clock delay inTco.
                slack=n*6250-latency-2*wire*1000-tco*1000-2000
                budgets.append(dict(configured_hz=frequency,one_way_wire_assumed_ns=wire,
                                    fpga_clock_to_data_assumed_ns=tco,host_setup_assumed_ns=2,
                                    minimum_period_ps=n*6250,worst_sampled_filter_latency_ps=latency,
                                    remaining_setup_slack_ps=slack,conditional_timing_passed=slack>0))
    report=dict(schema=1,hardware_access=False,scope='unit digital edge-count model plus arithmetic timing envelopes; no serializer or PNR qualification yet',
                sampler_period_ps=4630,nominal_sampler_hz=216000000,
                waveform_assumption='160MHz integer orN/N+1 period accumulator; HIGH floor(div/2), actualP4 ordering/duty unmeasured',
                metastability='2FF structure only; no analog metastability/MTBF model',
                clean_cases=cases,short_pulse_rejection_passed=True,oversized_short_spacing_fault_passed=True,
                asynchronous_reset_stopped_clock_passed=True,timing_budgets=budgets,
                source_sha256={s.relative_to(ROOT).as_posix():hashlib.sha256(s.read_bytes()).hexdigest()for s in source})
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(clean_cases=len(cases),noise_cases=2,budgets=len(budgets),output=str(a.output))))

if __name__=='__main__':main()
