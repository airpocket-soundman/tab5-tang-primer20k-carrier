import json,os,random,shutil,struct,subprocess,tempfile,unittest
from pathlib import Path
from reference import triangle_model as tm
from reference.link_protocol import request,crc16
ROOT=Path(__file__).resolve().parents[2]

HARNESS=r'''#include <stdio.h>
#include <string.h>
#ifdef _WIN32
#include <io.h>
#include <fcntl.h>
#endif
#include "triangle_model.h"
static int rd(void *p,size_t n){return fread(p,1,n,stdin)==n;}
static void wr(const void *p,size_t n){fwrite(p,1,n,stdout);}
int main(void){
#ifdef _WIN32
_setmode(_fileno(stdin),_O_BINARY);_setmode(_fileno(stdout),_O_BINARY);
#endif
uint8_t nv,nt,ntiles;if(!rd(&nv,1)||!rd(&nt,1))return 1;
model_vertex_t v[64];model_triangle_t t[96];model_pose_t pose;
for(unsigned i=0;i<nv;i++){int16_t c[3];if(!rd(c,6))return 2;v[i].x=c[0];v[i].y=c[1];v[i].z=c[2];}
for(unsigned i=0;i<nt;i++){uint8_t b[6];if(!rd(b,6))return 3;t[i].i0=b[0];t[i].i1=b[1];t[i].i2=b[2];t[i].color=(uint16_t)(b[4]|b[5]<<8);}
int16_t w[16];if(!rd(w,32))return 4;
for(int i=0;i<9;i++)pose.rotation[i]=w[i];for(int i=0;i<3;i++)pose.translation[i]=w[9+i];
pose.focal=w[12];pose.center_x=w[13];pose.center_y=w[14];pose.depth_shift=(uint8_t)w[15];
if(!rd(&ntiles,1))return 5;
uint8_t out[2048];
/* encoders: load tagged/untagged, pose tagged, draw, caps */
for(int tag=0;tag<2;tag++){unsigned n=model_load_encode(out,sizeof out,7,tag,v,nv,t,nt);unsigned short l=n;wr(&l,2);wr(out,n);}
{unsigned n=model_pose_encode(out,sizeof out,9,1,&pose);unsigned short l=n;wr(&l,2);wr(out,n);}
/* capacity and argument rejections must return zero without writing */
if(model_load_encode(out,model_load_size(nv,nt)-1,0,0,v,nv,t,nt))return 6;
if(model_load_encode(out,sizeof out,0,0,v,0,t,nt)||model_load_encode(out,sizeof out,0,0,v,65,t,nt))return 7;
model_pose_t bad=pose;bad.depth_shift=16;if(model_pose_encode(out,sizeof out,0,0,&bad))return 8;
model_screen_t s[64];model_project(&pose,v,nv,s);
for(unsigned i=0;i<nv;i++){uint8_t b[7]={s[i].valid,(uint8_t)s[i].x,(uint8_t)((uint16_t)s[i].x>>8),(uint8_t)s[i].y,(uint8_t)((uint16_t)s[i].y>>8),(uint8_t)s[i].depth,(uint8_t)(s[i].depth>>8)};wr(b,7);}
for(unsigned k=0;k<ntiles;k++){uint8_t tx,ty;if(!rd(&tx,1)||!rd(&ty,1))return 9;
 uint16_t rec[960];unsigned skipped=0;unsigned n=model_tile_records(rec,t,nt,s,tx,ty,&skipped);
 uint8_t h[2]={(uint8_t)n,(uint8_t)skipped};wr(h,2);wr(rec,n*20);
 uint8_t q[8];model_draw_encode(q,3,k&1,tx,ty);wr(q,8);}
uint8_t q[8],r[8];
model_caps_encode(q,1,0,0);r[0]=0x5a;r[1]=0;r[2]=1;r[3]=2;r[4]=64;r[5]=1;{uint16_t c=link_crc16(r,6);r[6]=c;r[7]=c>>8;}
if(!model_validate_response(r,q))return 10;
r[4]=65;{uint16_t c=link_crc16(r,6);r[6]=c;r[7]=c>>8;}if(model_validate_response(r,q))return 11;
return 0;}
'''

def cc_command():
    if os.environ.get('CARRIER_CC_JSON'): return json.loads(os.environ['CARRIER_CC_JSON'])
    found=shutil.which('cc')
    return [found] if found else None

class ModelCodec(unittest.TestCase):
    def test_reference_self_consistency(self):
        # Hand-checked values: identity pose, point straight ahead.
        pose=tm.Pose([16384,0,0,0,16384,0,0,0,16384],[0,0,1000],8000,5120,2880,3)
        self.assertEqual(tm.project_vertex((0,0,0),pose),(True,5120,2880,125))
        # 100 units right at depth 1000: 8000*100/1000 = 800 Q4 pixels.
        self.assertEqual(tm.project_vertex((100,-50,0),pose),(True,5120+800,2880-400,125))
        # Negative quotient truncates toward zero: -1 * 8000 / 3000 = -2 (not -3).
        pose2=tm.Pose([16384,0,0,0,16384,0,0,0,16384],[0,0,3000],8000,0,0,0)
        self.assertEqual(tm.project_vertex((-1,0,0),pose2)[1],-2)
        # Rotation shift is a floor: (-1 * 8192) >> 14 = -1 (not 0), then the
        # projection 100 * -1 / 100 = -1.
        half=tm.Pose([8192,0,0,0,16384,0,0,0,16384],[0,0,100],100,0,0,0)
        self.assertEqual(tm.project_vertex((-1,0,0),half),(True,-1,0,100))
        # Zero translation isolates the floor: x_cam = floor(-8192/16384) = -1.
        iso=tm.Pose([8192,0,0,0,16384,0,0,0,16384],[0,0,16384],16384,0,0,0)
        self.assertEqual(tm.project_vertex((-1,0,0),iso)[1],-1)
        self.assertFalse(tm.project_vertex((0,0,-1000),pose)[0])   # behind camera
        self.assertFalse(tm.project_vertex((30000,0,0),tm.Pose([16384,0,0,0,16384,0,0,0,16384],[0,0,1],32000,0,0,0))[0])  # overflow
    def test_c_codec_matches_reference(self):
        cc=cc_command()
        if not cc: self.skipTest('C compiler unavailable')
        rng=random.Random(7)
        with tempfile.TemporaryDirectory() as td:
            td=Path(td);(td/'a.c').write_text(HARNESS);exe=td/'t.exe'
            subprocess.run(cc+['-std=c11','-O2','-I',str(ROOT/'host'),str(td/'a.c'),'-o',str(exe)],check=True)
            for case in range(40):
                nv=rng.choice([1,2,8,63,64]);nt=rng.choice([1,12,95,96])
                verts=[(rng.randrange(-32768,32768) if case%5==0 else rng.randrange(-1200,1200),
                        rng.randrange(-1200,1200),rng.randrange(-1200,1200)) for _ in range(nv)]
                tris=[(rng.randrange(nv),rng.randrange(nv),rng.randrange(nv),rng.randrange(65536)) for _ in range(nt)]
                model=tm.Model(verts,tris)
                pose=tm.Pose([rng.randrange(-16384,16385) for _ in range(9)],[rng.randrange(-4000,4000),rng.randrange(-4000,4000),rng.randrange(-200,6000)],
                             rng.randrange(-32768,32768),rng.randrange(-32768,32768),rng.randrange(-32768,32768),rng.randrange(16))
                tiles=[(rng.randrange(256),rng.randrange(256)) for _ in range(2)]+[(rng.randrange(20),rng.randrange(12)) for _ in range(4)]
                data=bytes([nv,nt])+b''.join(struct.pack('<hhh',*v) for v in model.vertices)
                data+=b''.join(bytes([a,b,c,0])+col.to_bytes(2,'little') for a,b,c,col in model.triangles)
                data+=b''.join(w.to_bytes(2,'little') for w in pose.words())
                data+=bytes([len(tiles)])+b''.join(bytes(t) for t in tiles)
                raw=subprocess.run([str(exe)],input=data,capture_output=True,check=True).stdout
                cur=0
                def take(n):
                    nonlocal cur
                    out=raw[cur:cur+n];cur+=n;return out
                for tag in (False,True):
                    n=int.from_bytes(take(2),'little');self.assertEqual(take(n),tm.encode_load(7,model,tag))
                n=int.from_bytes(take(2),'little');self.assertEqual(take(n),tm.encode_pose(9,pose,True))
                screen=tm.project_model(model.vertices,pose)
                for i,expect in enumerate(screen):
                    b=take(7);got=(bool(b[0]),struct.unpack('<h',b[1:3])[0],struct.unpack('<h',b[3:5])[0],int.from_bytes(b[5:7],'little'))
                    self.assertEqual(got,expect,(case,i))
                for k,(tx,ty) in enumerate(tiles):
                    recs,drawn,skipped=tm.tile_records(model,screen,tx,ty)
                    h=take(2);self.assertEqual((h[0],h[1]),(drawn,skipped),(case,tx,ty))
                    body=take(20*drawn);want=b''.join(w.to_bytes(2,'little') for rec in recs for w in rec)
                    self.assertEqual(body,want)
                    self.assertEqual(take(8),tm.encode_draw(3,tx,ty,bool(k&1)))
                self.assertEqual(cur,len(raw))
    def test_python_encoders(self):
        small=tm.Model([(1,2,3),(4,5,6),(7,8,9)],[(0,1,2,0xabcd)])
        wire=tm.encode_load(5,small)
        self.assertEqual(len(wire),10+6*(3+1))
        self.assertEqual(int.from_bytes(wire[-2:],'little'),crc16(wire[:6]+wire[8:-2]))
        self.assertEqual(wire[:6],request(tm.MODEL_LOAD,5,3,1)[:6])
        with self.assertRaises(ValueError): tm.Model([(0,0,0)],[(0,0,1,0)])
        with self.assertRaises(ValueError): tm.Pose([0]*9,[0]*3,1,0,0,16)

if __name__=='__main__': unittest.main()
