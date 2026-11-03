"""Compare all ADDSUB inputs against independent truth values and Yosys ALU."""
import argparse
import hashlib
from pathlib import Path
import re
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser()
p.add_argument('--iverilog',default='iverilog')
p.add_argument('--vvp',default='vvp')
p.add_argument('--yosys-cells',type=Path,required=True,help='Original Gowin cells_sim.v from the installed Yosys')
a=p.parse_args()
source=a.yosys_cells.read_text(encoding='utf-8')
match=re.search(r'(?ms)^module ALU \(SUM, COUT, I0, I1, I3, CIN\);.*?^endmodule',source)
if not match:
    raise SystemExit('Could not identify original Yosys ALU module')
expected=[]
for i in range(16):
    i0,i1,i3,cin=((i>>3)&1,(i>>2)&1,(i>>1)&1,i&1)
    select=i0 ^ (i1 if i3 else 1-i1)
    expected.append(f'{i} {select ^ cin}{cin if select else i0}')
with tempfile.TemporaryDirectory(prefix='alu-table-') as tmp:
    tmp=Path(tmp)
    original=tmp/'yosys_alu.v'
    original.write_text(match.group(0)+'\n',encoding='utf-8')
    for name, model in [('test overlay', ROOT/'simulation/gowin_bench_models.v'),('Yosys original',original)]:
        binary=tmp/(name.replace(' ','_')+'.vvp')
        subprocess.run([a.iverilog,'-g2012','-s','tb_alu_table','-o',str(binary),str(model),
                        str(ROOT/'simulation/tests/tb_alu_table.v')],check=True)
        r=subprocess.run([a.vvp,str(binary)],check=True,text=True,capture_output=True)
        actual=[line for line in r.stdout.splitlines() if re.fullmatch(r'\d+ [01]{2}',line)]
        if actual!=expected:
            raise SystemExit(f'{name} differs: got {actual}, expected {expected}')
        print(f'PASS {name}: 16 vectors match independent truth table')
print('Yosys cells_sim.v SHA256:',hashlib.sha256(a.yosys_cells.read_bytes()).hexdigest())
