import argparse,random,sys,tempfile,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from reference.link_protocol import request,crc16,seal
from reference.triangle_tile import TriangleTile
p=argparse.ArgumentParser();p.add_argument('--iverilog',default='iverilog');p.add_argument('--vvp',default='vvp');p.add_argument('--filtered',action='store_true');p.add_argument('--vendor-primitive-lib',type=Path);p.add_argument('--pipeline-coverage',action='store_true');a=p.parse_args()
m=TriangleTile();vectors=[];seq=0

def response(status,value,q):return seal(bytes([0x5a,status,q[2],2,value&255,value>>8]))
def scalar(op,value=0,tag=False):
 global seq
 q=request(op,seq&255,value&255,value>>8);seq+=1;r=m.exchange(q)
 if tag:q=request(op|128,q[2],q[4],q[5]);r=bytes([0xc3])*8+r
 vectors.append((q,r));return r

def batch(records,tag=False,corrupt=None):
 global seq
 q=request(0x41|(128 if tag else 0),seq&255,len(records),1);seq+=1
 payload=b''.join(int(v&65535).to_bytes(2,'little') for rec in records for v in rec)
 c=crc16(q[:6]+payload);wire=bytearray(q+payload+c.to_bytes(2,'little'))
 if corrupt is not None:wire[corrupt]^=1
 if corrupt is None:
  for rec in records:
   for f,v in enumerate(rec):m.exchange(request(0x21+f,0,v&255,(v>>8)&255))
   z=m.exchange(request(0x2c,0,0,0));assert z[1]==0
 r=response(1 if corrupt is not None else 0,0x100|len(records),q)
 if tag:r=bytes([0xc3])*8+r
 vectors.append((wire,r))

for tag in (False,True):
 q=request(0x40|(128 if tag else 0),seq&255,0,0);seq+=1
 vectors.append((q,(bytes([0xc3])*8 if tag else b'')+response(0,0x140,q)))
for op,count,fmt in [(0x40,1,0),(0x40,0,1),(0x41,0,1),(0x41,65,1),(0x41,1,0),(0xc1,64,2)]:
 q=request(op,seq&255,count,fmt);seq+=1
 vectors.append((q,(bytes([0xc3])*8 if op&128 else b'')+response(3,0,q)))
rng=random.Random(20261104)
for count in (1,2,63,64):
 scalar(0x2b,0x42)
 records=[]
 for k in range(count):
  # Mix signed clipping, clockwise/counterclockwise, tie depths and degenerates.
  xy=[rng.randrange(-128,640) for _ in range(6)]
  if k%7==0:xy=[0,0,512,0,0,512]
  if k%11==0:xy=[0,0,0,0,0,0]
  records.append(xy+[rng.choice([0,100,100,65535]) for _ in range(3)]+[rng.randrange(65536)])
 batch(records,tag=count%2==0)
 for plane in (0,1):scalar(0x3b,plane<<8,tag=True)
# Corrupted records and trailer must leave both complete planes unchanged.
rec=[[0,0,512,0,0,512,0,0,0,0xffff]]
for byte in range(8,30):batch(rec,tag=bool(byte&1),corrupt=byte)
for plane in (0,1):scalar(0x3b,plane<<8,tag=True)
with tempfile.TemporaryDirectory() as t:
 t=Path(t);vf=t/'vectors';vf.write_text(''.join(f'{len(q)} {len(r)} '+' '.join(f'{x:02x}' for x in bytes(q)+r)+'\n' for q,r in vectors))
 sources=['link/rtl/triangle_batch.v','link/rtl/link_reply_raw.v','link/rtl/link_bringup.v','gfx/rtl/triangle_tile.v','gfx/rtl/triangle_fragment.v','gfx/rtl/triangle_coverage.v','gfx/rtl/triangle_depth.v','link/tests/tb_triangle_batch.v']
 paths=[str(ROOT/s)for s in sources]
 bench=(ROOT/sources[-1]).read_text()
 if a.filtered:
  paths[2]=str(ROOT/'link/rtl/link_bringup_filtered.v');paths +=[str(ROOT/'link/rtl/reply_clock_filter.v')]
  bench=bench.replace('module tb_triangle_batch;','module tb_triangle_batch;\nreg filter_clk=0;always #2.315 filter_clk=~filter_clk;').replace('link_bringup #(','link_bringup_filtered #(').replace('dut(clk,reset_n,arm,bus_clk,dir,data_i,data_o,oe,ready);','dut(clk,reset_n,arm,bus_clk,dir,data_i,data_o,oe,ready,filter_clk,reset_n && arm);').replace('always #5 clk=~clk;','always #9.259 clk=~clk;')
 if a.pipeline_coverage:paths[5]=str(ROOT/'gfx/rtl/triangle_coverage_pipeline.v')
 if a.vendor_primitive_lib:
  paths[3]=str(ROOT/'gfx/rtl/triangle_tile_vendor.v');paths +=[str(ROOT/'gfx/rtl/tile_dpram_vendor.v'),str(a.vendor_primitive_lib)]
  bench=bench.replace('module tb_triangle_batch;',"module tb_triangle_batch;\nGSR GSR(1'b1);")
 generated=t/'bench.v';generated.write_text(bench);paths[7]=str(generated)
 subprocess.run([a.iverilog,'-g2012','-Wall','-s','tb_triangle_batch','-o',str(t/'test'),*paths],check=True)
 subprocess.run([a.vvp,str(t/'test'),'+vectors='+str(vf)],check=True,timeout=180)
print('PASS batch counts1/2/63/64, exact reference color/depth, corruption each record/trailer byte')
