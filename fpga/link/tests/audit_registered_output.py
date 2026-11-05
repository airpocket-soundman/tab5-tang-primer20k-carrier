"""Audit mapped output FFs and per-bit structural SDF pad paths (not measured)."""
import argparse,hashlib,json,re
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--netlist',type=Path,required=True)
p.add_argument('--pad-proof',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();s=a.netlist.read_text()
cells=[(t,n,{k:v.strip()for k,v in re.findall(r'\.(\w+)\((.*?)\)',b)})for t,n,b in re.findall(r'^([A-Za-z0-9_]+)\s+(\\\S+)\s+\((.*?)\);',s,re.M|re.S)]
regs=[dict(type=t,name=n,clock=ps['CLK'],q=ps['Q'])for t,n,ps in cells if t.startswith('DFF')and 'serializer/registered_byte_'in n]
assert len(regs)==8 and len({x['clock']for x in regs})==1
pad=json.loads(a.pad_proof.read_text());assert len(pad['bits'])==8
for row in pad['bits']:
    for key in ['min_path','max_path']:assert f'registered_byte_{row["bit"]}_'in row[key][0]
a.output.write_text(json.dumps(dict(hardware_access=False,scope='mapped topology and structural SDF only; no analog qualification',netlist_sha256=hashlib.sha256(a.netlist.read_bytes()).hexdigest(),registered_byte_ffs=regs,pad_all8_from_corresponding_ff=True),indent=2))
print('REGISTERED BYTE8 mapped FF/commonCLK/corresponding pad path PASS')
