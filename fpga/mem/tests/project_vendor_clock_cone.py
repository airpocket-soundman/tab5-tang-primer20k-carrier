"""Project public generated-cell clock-init cone, with explicit pre-calibration cuts.

Not a protected-source reader, a DRAM model, or full controller verification.
Only copied public generated cells are emitted under ignored build output.
"""
from pathlib import Path
import re,json,hashlib

root=Path(__file__).resolve().parents[2]
import os
TAG=os.environ.get('MEM_IP_TAG','');SFX=('-'+TAG) if TAG else ''
vo=root/f'build/mem-bist-ip{SFX}/generated/MemDDR3/MemDDR3.vo'
text=vo.read_text()
rx=r'^(\w+) (\\[^\n]+?|\w+)\s+\(\n(.*?)^\);'
cells=[];drivers={}
def nets(value):
    escaped=re.findall(r'\\([^\s,{}]+)',value)
    simple=re.findall(r'(?<![\\\w/])\b(clk|memory_clk|pll_lock|rst_n|clk_out|ddr_rst|VCC|GND)\b',value)
    return set(escaped+simple)
for match in re.finditer(rx,text,re.M|re.S):
    kind,inst,body=match.groups();ports=dict(re.findall(r'\.(\w+)\((.*?)\)',body,re.S))
    out={'VCC':['V'],'GND':['G'],'INV':['O'],'BUF':['O'],'DLL':['STEP','LOCK'],'DHCEN':['CLKOUT'],'CLKDIV':['CLKOUT']}.get(kind,
        ['F'] if kind.startswith('LUT') else ['Q'] if kind.startswith('DFF') else [])
    index=len(cells);cells.append((kind,inst,match.group(0),ports,out))
    for port in out:
        for net in nets(ports[port]):drivers.setdefault(net,[]).append(index)
prefix='gw3_top/u_ddr_phy_top/'
cuts={prefix+'sys_reset_Z':'0', 'gw3_top/ddr_init_internal':'0'}
roots=[prefix+n for n in ['uddcntln','ddr_init_st_Z','dll_step','dll_lock','n1426_3']]+['clk_out']
pending=list(roots);seen=set();selected=set();primary={'clk','memory_clk','pll_lock','rst_n'}
while pending:
    net=pending.pop()
    if net in seen:continue
    seen.add(net)
    if net in cuts or net in primary:continue
    assert net in drivers,('undriven cone signal',net)
    for index in drivers[net]:
        if index in selected:continue
        selected.add(index);kind,inst,body,ports,out=cells[index]
        for port,value in ports.items():
            if port not in out:pending.extend(nets(value))
first=re.search(rx,text,re.M|re.S).start()
declarations=text[:first].replace('module MemDDR3(','module MemClockCone(',1)
body=[]
for index in sorted(selected):
    kind,inst,source,ports,out=cells[index];body.append(source)
    body.extend(re.findall(r'^defparam '+re.escape(inst)+r'\s+\.[^\n]+',text,re.M))
for net,value in cuts.items():body.append('assign \\'+net+' =1\'b'+value+';')
dest=root/f'build/mem-clock-cone{SFX}';dest.mkdir(parents=True,exist_ok=True)
(dest/'MemClockCone.v').write_text(declarations+'\n'.join(body)+'\nendmodule\n')
tb=(root/'mem/tests/tb_vendor_init.v').read_text().replace('MemDDR3 dut(','MemClockCone dut(')
if TAG.startswith('clk400'):
    # 27MHz sys clock, 398.25MHz memory clock (27*59/4), USER = memory/4 = 99.5625MHz: two USER periods = 20.09ns
    for old,new in [('always #1.543210 memory_clk','always #1.255331 memory_clk'),('<24.69','<20.0')]:
        assert tb.count(old)==1,old;tb=tb.replace(old,new)
(dest/'tb_vendor_init.v').write_text(tb)
record={'scope':'clock initialization cone only, not full DDR calibration',
 'generated_source_sha256':hashlib.sha256(vo.read_bytes()).hexdigest(),
 'selected_public_cells':len(selected),'total_public_cells':len(cells),
 'boundary_assumptions':cuts,'roots':roots}
(dest/'projection.json').write_text(json.dumps(record,indent=2)+'\n')
print(record)
