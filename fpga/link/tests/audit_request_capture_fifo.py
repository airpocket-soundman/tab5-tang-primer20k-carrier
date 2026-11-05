"""Verify physical request DATA FF pairs and exclusive first-stage fanout."""
import argparse,hashlib,json,re
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--netlist',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();s=a.netlist.read_text();cells=[]
for typ,name,body in re.findall(r'^([A-Za-z0-9_]+)\s+(\\\S+)\s+\((.*?)\);',s,re.M|re.S):
    ports={k:v.strip() for k,v in re.findall(r'\.(\w+)\((.*?)\)',body)}
    cells.append((typ,name,ports))
ff=[c for c in cells if 'request_fifo.capture/physical_capture.lane' in c[1]];lanes=[]
for i in range(8):
    first=next(c for c in ff if f'lane[{i}].meta_ff' in c[1])
    second=next(c for c in ff if f'lane[{i}].sampled_ff' in c[1])
    consumers=[(n,k) for t,n,ps in cells for k,v in ps.items() if k!='Q' and v==first[2]['Q']]
    assert first[0]==second[0]=='DFFC'
    assert first[2]['CLK']==second[2]['CLK']=='filter_clk'
    assert first[2]['D']==f'data_in[{i}]'
    assert consumers==[(second[1],'D')]
    lanes.append(dict(bit=i,first=first[1],second=second[1],sole_fanout=consumers,clock=first[2]['CLK']))
assert len(ff)==16
ram=[n for t,n,ps in cells if t=='RAM16S4' and 'request_fifo.capture' in n]
assert not ram
gray=[]
for group in ('read_gray','write_gray'):
    for i in range(5):
        x=next(c for c in cells if f'capture/{group}_meta_{i}_s0' in c[1])
        y=next(c for c in cells if f'capture/{group}_sampled_{i}_s0' in c[1])
        consumers=[(n,k) for t,n,ps in cells for k,v in ps.items() if k!='Q' and v==x[2]['Q']]
        assert x[0]==y[0]=='DFFC' and consumers==[(y[1],'D')]
        gray.append(dict(group=group,bit=i,clock=x[2]['CLK'],consumers=consumers))
clocks=[c for c in cells if 'physical_capture.clock' in c[1]]
assert len(clocks)==3 and all(c[0]=='DFFC' and c[2]['CLK']=='filter_clk' for c in clocks)
mem=[n for t,n,ps in cells if t=='RAM16SDP4' and 'request_fifo.capture' in n]
assert len(mem)==2
out=dict(gray_pairs=gray,capture_clock_dffc=3,storage_ram16sdp4=mem,hardware_access=False,netlist_sha256=hashlib.sha256(a.netlist.read_bytes()).hexdigest(),mapped_dffc_count=len(ff),request_ram16s4=ram,stage0_only_stage1_fanout=True,lanes=lanes)
a.output.write_text(json.dumps(out,indent=2))
print('DFFC16, request RAM16S4=0, stage0 sole-stage1 fanout PASS')
