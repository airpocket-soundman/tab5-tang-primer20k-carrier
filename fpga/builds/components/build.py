"""Synthesize one RTL component only; no IO, placement, timing or hardware."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[2]
TOPS = {'mac':'int8_mac_lane', 'requant':'int8_requantize', 'dot':'int8_dot_job',
        'coverage':'triangle_coverage', 'depth':'triangle_depth', 'fragment':'triangle_fragment'}


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def build(feature, yosys, root=ROOT, invoke=subprocess.run):
    top=TOPS[feature]
    directory=root/'build'/f'component-{feature}'
    run_dir=directory/'runs'/uuid.uuid4().hex
    run_dir.mkdir(parents=True, exist_ok=False)
    manifest=directory/'manifest.json'
    sources=sorted((root/('npu/rtl' if feature in ('mac','requant','dot') else 'gfx/rtl')).glob('*.v' if feature in ('mac','requant','dot') else 'triangle*.v'))
    output=run_dir/'synth.json'
    report={'feature':feature,'top':top,'status':'running','started_utc':datetime.now(timezone.utc).isoformat(),
            'run_dir':str(run_dir),'scope':'component synthesis only; no IO, constraints, placement, routing, timing or bitstream',
            'sources':{},'tool':{'path':str(yosys)},'command':None,'log':str(run_dir/'synthesis.log')}
    def save(): manifest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    save()
    try:
        if not sources: raise ValueError('no RTL sources found')
        report['sources']={str(p):sha(p) for p in sources}
        report['tool']['sha256']=sha(yosys)
        source_args=' '.join('"'+p.as_posix()+'"' for p in sources)
        script=f'read_verilog {source_args}; synth_gowin -family gw2a -noiopads -top {top} -json "{output.as_posix()}"'
        command=[str(yosys),'-Q','-T','-p',script]
        report['command']=command
        save()
        result=invoke(command,capture_output=True,text=True,encoding='utf-8',errors='replace',check=False,timeout=300)
        (run_dir/'synthesis.log').write_text((result.stdout or '')+(result.stderr or ''),encoding='utf-8')
        report['exit_code']=result.returncode
        if result.returncode: raise ValueError(f'synthesis failed with exit code {result.returncode}')
        data=json.loads(output.read_text(encoding='utf-8'))
        cells=data['modules'][top]['cells']
        counts=Counter(cell['type'] for cell in cells.values() if not cell['type'].startswith('$scopeinfo'))
        if any(name in counts for name in ('IBUF','OBUF','IOBUF','TBUF','BUFG','BUFS')):
            raise ValueError('unexpected top-level IO or clock buffer cells')
        report['resources']=dict(sorted(counts.items()))
        report['artifact']={'path':str(output),'sha256':sha(output)}
        report['status']='passed'
        print(f'{feature}: passed ({len(cells)} cells), {output}')
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        report['status']='failed'; report['error']=str(exc)
        print(f'{feature}: failed: {exc}',file=sys.stderr)
        return 1
    finally:
        report['finished_utc']=datetime.now(timezone.utc).isoformat()
        save()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('feature',choices=TOPS)
    parser.add_argument('--yosys',type=Path,default=ROOT/'build/oss-env/Scripts/yowasp-yosys.exe')
    args=parser.parse_args()
    return build(args.feature,args.yosys)


if __name__=='__main__': sys.exit(main())
