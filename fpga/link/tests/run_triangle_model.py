"""Pin-level MODEL_* test: real link_bringup + triangle_tile RTL against the
scalar triangle_tile oracle fed with the records the Python model predicts."""
import argparse,math,random,sys,tempfile,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from reference.link_protocol import request,crc16,seal
from reference.triangle_tile import TriangleTile
from reference import triangle_model as tm
p=argparse.ArgumentParser();p.add_argument('--iverilog',default='iverilog');p.add_argument('--vvp',default='vvp')
p.add_argument('--vectors-only',help='write the vector file and stop')
a=p.parse_args()
m=TriangleTile();vectors=[];seq=0

def response(status,value,q):return seal(bytes([0x5a,status,q[2],2,value&255,value>>8]))
def prefix(q):return bytes([0xc3])*8 if q[1]&128 else b''
def scalar(op,value=0,tag=False):
 global seq
 q=request(op,seq&255,value&255,value>>8);seq+=1;r=m.exchange(q)
 if tag:q=request(op|128,q[2],q[4],q[5]);r=bytes([0xc3])*8+r
 vectors.append((q,r));return r
def nextseq():
 global seq
 seq+=1;return (seq-1)&255
def push(wire,status,value):
 vectors.append((wire,prefix(wire)+response(status,value,wire)))
def apply_records(records):
 for rec in records:
  for f,v in enumerate(rec):m.exchange(request(0x21+f,0,v&255,(v>>8)&255))
  assert m.exchange(request(0x2c,0,0,0))[1]==0

def rotation(ax,ay,az):
 cx,sx,cy,sy,cz,sz=math.cos(ax),math.sin(ax),math.cos(ay),math.sin(ay),math.cos(az),math.sin(az)
 r=[[cy*cz,-cy*sz,sy],[sx*sy*cz+cx*sz,-sx*sy*sz+cx*cz,-sx*cy],[-cx*sy*cz+sx*sz,cx*sy*sz+sx*cz,cx*cy]]
 return [max(-32768,min(32767,round(v*16384))) for row in r for v in row]

CUBE_V=[(-500,-500,-500),(500,-500,-500),(500,500,-500),(-500,500,-500),(-500,-500,500),(500,-500,500),(500,500,500),(-500,500,500)]
FACES=[(0,1,2),(0,2,3),(5,4,7),(5,7,6),(4,0,3),(4,3,7),(1,5,6),(1,6,2),(3,2,6),(3,6,7),(4,5,1),(4,1,0)]
CUBE=tm.Model(CUBE_V,[(f[0],f[1],f[2],0x1111*(k%15+1)&0xffff) for k,f in enumerate(FACES)])
rng=random.Random(20261104)
rand_v=[(rng.randrange(-900,900),rng.randrange(-900,900),rng.randrange(-900,900)) for _ in range(64)]
BIG=tm.Model(rand_v,[(rng.randrange(64),rng.randrange(64),rng.randrange(64),rng.randrange(65536)) for _ in range(96)])

def do_caps():
 for which,expect in ((0,64|(1<<8)),(1,96)):
  q=tm.encode_caps(nextseq(),which);push(q,0,expect)
  q=tm.encode_caps(nextseq(),which,True);push(q,0,expect)
 for which,b in ((2,0),(0,1)):
  q=request(tm.MODEL_CAPS,nextseq(),which,b);push(q,3,0)
def do_draw(model,screen,tx,ty,tag):
 q=tm.encode_draw(nextseq(),tx,ty,tag)
 recs,drawn,skipped=tm.tile_records(model,screen,tx,ty)
 scalar(0x2b,0x0042)
 apply_records(recs)
 push(q,0,drawn|(skipped<<8))
 for plane in (0,1):scalar(0x3b,plane<<8,tag=True)
 return recs
def do_load(model,tag=False,corrupt=None):
 q=bytearray(tm.encode_load(nextseq(),model,tag))
 if corrupt is not None:q[corrupt]^=1
 if corrupt is None:push(bytes(q),0,len(model.vertices)|(len(model.triangles)<<8))
 else:push(bytes(q),1,0)
def do_pose(pose,model,tag=False,corrupt=None,expect_status=0):
 q=bytearray(tm.encode_pose(nextseq(),pose,tag))
 if corrupt is not None:q[corrupt]^=1
 screen=tm.project_model(model.vertices,pose)
 if corrupt is not None:push(bytes(q),1,0)
 else:push(bytes(q),expect_status,(sum(1 for v in screen if v[0])|(len(model.vertices)<<8)) if expect_status==0 else 0)
 return screen

do_caps()
# Draw before any model, and after a failed load, must refuse without touching the tile.
vectors.append((tm.encode_draw(nextseq(),0,0),response(5,0,tm.encode_draw(seq-1,0,0))))
q=bytearray(tm.encode_pose(nextseq(),tm.Pose(rotation(0,0,0),[0,0,3000],9600,5120,2880,4)))
vectors.append((bytes(q),response(5,0,bytes(q))))
# Bad counts and format are refused at the header with no body consumed.
for op,a1,b1 in ((tm.MODEL_LOAD,0,1),(tm.MODEL_LOAD,65,1),(tm.MODEL_LOAD,1,0),(tm.MODEL_LOAD,1,97),(tm.MODEL_POSE,0,0),(tm.MODEL_POSE,1,1)):
 q=request(op,nextseq(),a1,b1);push(q,3,0)
# Corrupt every byte of a small load, then confirm the model is not usable.
small=tm.Model(CUBE_V[:4],[(0,1,2,0xf800),(0,2,3,0x07e0)])
sl=tm.encode_load(0,small)
for byte in range(8,len(sl)):do_load(small,tag=bool(byte&1),corrupt=byte)
vectors.append((tm.encode_draw(nextseq(),0,0),response(5,0,tm.encode_draw(seq-1,0,0))))
# Out-of-range index and nonzero reserved byte are rejected after a valid CRC.
for model_bytes in ('index','reserved'):
 q=bytearray(tm.encode_load(nextseq(),small))
 pos=8+6*len(small.vertices)+(0 if model_bytes=='index' else 3)
 q[pos]=len(small.vertices) if model_bytes=='index' else 1
 c=crc16(bytes(q[:6])+bytes(q[8:-2]));q[-2:]=c.to_bytes(2,'little')
 push(bytes(q),3,0)

do_load(CUBE)
poses=[tm.Pose(rotation(0.5,0.7,0.2),[0,0,3200],9600,5120,2880,4),
       tm.Pose(rotation(1.1,-0.4,2.0),[150,-90,3500],8000,5120,2880,3),
       tm.Pose(rotation(0,0,0),[0,0,1100],16000,5120,2880,0),      # very close: some vertices project far off screen
       tm.Pose(rotation(0.3,0.3,0.3),[0,0,300],9600,5120,2880,15), # camera inside/behind the cube: invalid vertices
       tm.Pose(rotation(0.9,0.1,0.4),[32000,0,2000],9000,-30000,30000,2)]  # translation near int16 limits
for k,pose in enumerate(poses):
 screen=do_pose(pose,CUBE,tag=bool(k&1))
 tiles=set()
 for tx in range(0,20):
  for ty in range(0,12):
   if tm.tile_records(CUBE,screen,tx,ty)[1]:tiles.add((tx,ty))
 picks=sorted(tiles)
 rng.shuffle(picks)
 for tx,ty in picks[:3]+[(255,255),(0,0)]:do_draw(CUBE,screen,tx,ty,tag=bool((tx+ty+k)&1))
# Corrupt a pose byte: model stays loaded but not posed -> draw refused.
pose=poses[0];sc=do_pose(pose,CUBE,corrupt=20)
vectors.append((tm.encode_draw(nextseq(),10,5),response(5,0,tm.encode_draw(seq-1,10,5))))
do_pose(tm.Pose(rotation(0,0,0),[0,0,3000],9600,5120,2880,0),CUBE)
bad=bytearray(tm.encode_pose(nextseq(),tm.Pose(rotation(0,0,0),[0,0,3000],9600,5120,2880,0)))
bad[8+30]=16;bad[8+31]=0
c=crc16(bytes(bad[:6])+bytes(bad[8:-2]));bad[-2:]=c.to_bytes(2,'little')
push(bytes(bad),3,0)

# Full-size random model: negative-depth and offscreen vertices, ties, degenerates.
do_load(BIG,tag=True)
for k,pose in enumerate([tm.Pose(rotation(0.2,0.4,0.6),[0,0,2500],9000,5120,2880,3),
                          tm.Pose(rotation(2.0,1.0,0.0),[200,-300,1200],20000,5120,2880,1)]):
 screen=do_pose(pose,BIG,tag=bool(k))
 tiles=[(tx,ty) for tx in range(0,20) for ty in range(0,12) if tm.tile_records(BIG,screen,tx,ty)[1]]
 rng.shuffle(tiles)
 for tx,ty in tiles[:2]:do_draw(BIG,screen,tx,ty,tag=bool(tx&1))

if a.vectors_only:
 Path(a.vectors_only).write_text(''.join(f'{len(q)} {len(r)} '+' '.join(f'{x:02x}' for x in bytes(q)+r)+'\n' for q,r in vectors));sys.exit(0)
with tempfile.TemporaryDirectory() as t:
 t=Path(t);vf=t/'vectors';vf.write_text(''.join(f'{len(q)} {len(r)} '+' '.join(f'{x:02x}' for x in bytes(q)+r)+'\n' for q,r in vectors))
 sources=['link/rtl/triangle_batch.v','link/rtl/triangle_model.v','link/rtl/link_reply_raw.v','link/rtl/link_bringup.v','gfx/rtl/triangle_tile.v','gfx/rtl/triangle_fragment.v','gfx/rtl/triangle_coverage.v','gfx/rtl/triangle_depth.v','link/tests/tb_triangle_model.v']
 subprocess.run([a.iverilog,'-g2012','-Wall','-s','tb_triangle_model','-o',str(t/'test'),*[str(ROOT/s) for s in sources]],check=True)
 subprocess.run([a.vvp,str(t/'test'),'+vectors='+str(vf)],check=True,timeout=1500)
print('PASS model caps/load/pose/draw, exact color/depth vs scalar oracle, header/CRC/index/reserved refusals')
