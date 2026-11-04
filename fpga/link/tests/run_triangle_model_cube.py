"""Host-cube MODEL_* test: LOAD -> POSE -> DRAW of the Tab5 host's real cube scene
(tab5-fpga-gpu lab::model_instances poses, integer projection) through the real
link_bringup + triangle RTL at pin level, compared pixel for pixel (colour and depth)
with the host's CPU integer-raster full frame stored in vectors/host_cube_frames.json.

Chain of evidence: RTL replies == Python oracle (every vector, via tb_triangle_model.v)
and Python oracle tile read == host CPU frame (asserted here before simulation).
Regenerate the fixture with tab5-fpga-gpu tests/test_model_fixture.py.
"""
import argparse,base64,json,sys,tempfile,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from reference.link_protocol import request,seal
from reference.triangle_tile import TriangleTile
from reference import triangle_model as tm
p=argparse.ArgumentParser();p.add_argument('--iverilog',default='iverilog');p.add_argument('--vvp',default='vvp')
p.add_argument('--fixture',default=str(ROOT/'link/tests/vectors/host_cube_frames.json'))
p.add_argument('--filtered',action='store_true',help='run against link_bringup_filtered (216MHz reply filter) instead of link_bringup')
p.add_argument('--vectors-only',help='write the vector file and stop (still runs the oracle-vs-CPU check)')
a=p.parse_args()
fx=json.loads(Path(a.fixture).read_text())
W,H=fx['width'],fx['height']
def plane(b64):
 raw=base64.b64decode(b64);return [raw[i]|raw[i+1]<<8 for i in range(0,len(raw),2)]
m=TriangleTile();vectors=[];seq=0
def nextseq():
 global seq
 seq+=1;return (seq-1)&255
def response(status,value,q):return seal(bytes([0x5a,status,q[2],2,value&255,value>>8]))
def prefix(q):return bytes([0xc3])*8 if q[1]&128 else b''
def push(wire,status,value):vectors.append((wire,prefix(wire)+response(status,value,wire)))
def scalar(op,value=0,tag=False):
 q=request(op,nextseq(),value&255,value>>8);r=m.exchange(q)
 if tag:q=request(op|128,q[2],q[4],q[5]);r=bytes([0xc3])*8+r
 vectors.append((q,r));return r
def apply_records(recs):
 for rec in recs:
  for f,v in enumerate(rec):m.exchange(request(0x21+f,0,v&255,(v>>8)&255))
  assert m.exchange(request(0x2c,0,0,0))[1]==0
# CAPS first, as the host does (both queries, status must be success).
for which,expect in ((0,64|(1<<8)),(1,96)):push(tm.encode_caps(nextseq(),which),0,expect)
model=tm.Model([tuple(v) for v in fx['vertices']],[tuple(t) for t in fx['triangles']])
push(tm.encode_load(nextseq(),model),0,len(model.vertices)|(len(model.triangles)<<8))
def pose_of(d):return tm.Pose(d['rotation'],d['translation'],d['focal'],d['center_x'],d['center_y'],d['depth_shift'])
def touches(screen,tx,ty):
 valid=[v for v in screen if v[0]]
 if not valid:return False
 x0,y0=tx*tm.TILE_Q4,ty*tm.TILE_Q4
 xs=[v[1] for v in valid];ys=[v[2] for v in valid]
 return not (max(xs)<x0 or min(xs)>x0+tm.TILE_Q4-1 or max(ys)<y0 or min(ys)>y0+tm.TILE_Q4-1)
stats={'frames':0,'tiles':0,'poses':0,'draws':0,'drawn_triangles':0,'pixels':0,'covered_pixels':0}
for fr in fx['frames']:
 cpu_color,cpu_depth=plane(fr['color_rgb565le_b64']),plane(fr['depth_u16le_b64'])
 assert len(cpu_color)==W*H==len(cpu_depth)
 poses=[pose_of(d) for d in fr['poses']];screens=[tm.project_model(model.vertices,ps) for ps in poses]
 for ty in range(0,(H+31)//32):
  for tx in range(0,(W+31)//32):
   scalar(0x2b,0x0042)
   for n,(ps,sc) in enumerate(zip(poses,screens)):
    if not touches(sc,tx,ty):continue
    push(tm.encode_pose(nextseq(),ps,bool(n&1)),0,sum(1 for v in sc if v[0])|(len(model.vertices)<<8));stats['poses']+=1
    recs,drawn,skipped=tm.tile_records(model,sc,tx,ty);assert skipped==0,(fr['load'],fr['frame'],tx,ty,skipped)
    apply_records(recs)
    push(tm.encode_draw(nextseq(),tx,ty,bool((tx+ty+n)&1)),0,drawn|(skipped<<8));stats['draws']+=1;stats['drawn_triangles']+=drawn
   for pl in (0,1):scalar(0x3b,pl<<8,tag=True)
   # the oracle tile (= what the RTL must return) must equal the host CPU frame
   for y in range(min(32,H-ty*32)):
    for x in range(min(32,W-tx*32)):
     i=(ty*32+y)*W+tx*32+x;j=y*32+x
     if m.frame.color[j]!=cpu_color[i] or m.frame.depth[j]!=cpu_depth[i]:
      sys.exit('MISMATCH oracle vs host CPU load%d frame%d px(%d,%d) color %04x/%04x depth %04x/%04x'%(fr['load'],fr['frame'],tx*32+x,ty*32+y,m.frame.color[j],cpu_color[i],m.frame.depth[j],cpu_depth[i]))
     stats['pixels']+=1;stats['covered_pixels']+=cpu_color[i]!=0x0042
   stats['tiles']+=1
 stats['frames']+=1
assert stats['covered_pixels']>0
def dump(path):Path(path).write_text(''.join(f'{len(q)} {len(r)} '+' '.join(f'{x:02x}' for x in bytes(q)+r)+'\n' for q,r in vectors))
if a.vectors_only:dump(a.vectors_only);print(json.dumps(stats));sys.exit(0)
with tempfile.TemporaryDirectory() as t:
 t=Path(t);vf=t/'vectors';dump(vf)
 sources=['link/rtl/triangle_batch.v','link/rtl/triangle_model.v','link/rtl/link_reply_raw.v','link/rtl/link_bringup.v','gfx/rtl/triangle_tile.v','gfx/rtl/triangle_fragment.v','gfx/rtl/triangle_coverage.v','gfx/rtl/triangle_depth.v','link/tests/tb_triangle_model.v']
 top='tb_triangle_model'
 if a.filtered:
  sources=['link/rtl/reply_clock_filter.v','link/rtl/link_reply_raw.v','link/rtl/link_bringup_filtered.v','gfx/rtl/gfx_bench.v','gfx/rtl/triangle_tile.v','gfx/rtl/triangle_fragment.v','gfx/rtl/triangle_coverage.v','gfx/rtl/triangle_depth.v','link/rtl/triangle_batch.v','link/rtl/triangle_model.v','link/tests/sim_gowin_lut1.v','link/tests/tb_triangle_model_filtered.v'];top='tb_triangle_model_filtered'
 subprocess.run([a.iverilog,'-g2012','-s',top,'-o',str(t/'test'),*[str(ROOT/s) for s in sources]],check=True)
 subprocess.run([a.vvp,str(t/'test'),'+vectors='+str(vf)],check=True,timeout=3000)
print('PASS'+(' (link_bringup_filtered)' if a.filtered else ' (link_bringup)'),'host cube LOAD/POSE/DRAW RTL == host CPU integer frame, all pixels colour+depth:',json.dumps(stats))
