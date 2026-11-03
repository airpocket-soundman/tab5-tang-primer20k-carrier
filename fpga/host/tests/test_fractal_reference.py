"""C fixed-point arithmetic and codec against independent Python wire/pixel oracle."""
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import tempfile
import unittest
from reference.triangle_tile import TriangleTile, fractal_pixel
from reference.link_protocol import request, seal
ROOT=Path(__file__).resolve().parents[2]

class FractalReference(unittest.TestCase):
    def test_c_pixels_and_protocol(self):
        configured=os.environ.get('CARRIER_CC_JSON')
        compiler=json.loads(configured) if configured else [shutil.which('cc') or shutil.which('gcc')]
        if not compiler[0]: self.skipTest('Existing C compiler unavailable')
        source=r'''#include "fractal_reference.h"
#include "link_protocol.h"
#include <stdio.h>
int main(void) {
    int a,b,c,d,e,f,g; unsigned index=0;
    while(scanf("%d%d%d%d%d%d%d",&a,&b,&c,&d,&e,&f,&g)==7) {
        fractal_config cfg={(int16_t)a,(int16_t)b,(uint16_t)c,(uint16_t)d,(int16_t)e,(int16_t)f,(uint8_t)g,(uint8_t)(g>>8)};
        uint16_t pixels[1024];uint32_t iterations;
        if(!fractal_reference_tile(&cfg,pixels,&iterations)) return 2;
        for(unsigned i=0;i<1024;i++) printf("%04x ",pixels[i]);
        puts("");index++;
    }
    if(!index || fractal_config_valid(NULL)) return 3;
    fractal_config bad={0,0,0,1,0,0,128,0};
    if(fractal_config_valid(&bad)) return 4;
    bad.dx=1;bad.x0=32767;if(fractal_config_valid(&bad))return 5;
    bad.x0=0;bad.limit=0;if(fractal_config_valid(&bad))return 6;
    if(fractal_floor12(-1)!=-1 || fractal_floor12(-4096)!=-1 || fractal_floor12(-4097)!=-2) return 7;
    return 0;
}
'''
        views=[[-10035,-4096,280,264,-2949,819,64],[-4096,-2048,132,132,-2949,819,0x0140],
               [-3200,-1200,32,32,-2949,819,128],[-32768,-32768,1,1,32767,-32768,0x0180],
               [-1024,-1024,64,64,-2579,-693,0x0180]]
        rng=random.Random(20261103)
        for _ in range(24):
            views.append([rng.randint(-12000,1000),rng.randint(-10000,1000),rng.randint(1,400),rng.randint(1,400),
                          rng.randint(-4096,4096),rng.randint(-4096,4096),rng.choice([1,24,64,128])|rng.randrange(2)<<8])
        with tempfile.TemporaryDirectory(prefix='fractal-reference-') as td:
            td=Path(td);src=td/'main.c';exe=td/('test.exe' if os.name=='nt' else 'test')
            src.write_text(source,encoding='ascii')
            subprocess.run([*compiler,'-std=c11','-Wall','-Wextra','-Werror','-I',str(ROOT/'host'),str(src),'-o',str(exe)],check=True)
            result=subprocess.run([str(exe)],input=''.join(' '.join(map(str,v))+'\n' for v in views),text=True,capture_output=True,check=True)
            rows=result.stdout.splitlines();self.assertEqual(len(rows),len(views))
            for values,row in zip(views,rows):
                params={i:v&65535 for i,v in enumerate(values)}
                expected=[fractal_pixel(params,x,y) for y in range(32) for x in range(32)]
                self.assertEqual([int(v,16) for v in row.split()],expected)
            # Codec must accept exact new opcode replies and reject changed
            # CRC/status/sequence/payload, even if the frame CRC is recomputed.
            source2=r'''#include "link_protocol.h"
#include <stdio.h>
int main(void) {unsigned x;uint8_t q[8],r[8];while(scanf("%u",&x)==1){q[0]=(uint8_t)x;for(int i=1;i<8;i++){if(scanf("%u",&x)!=1)return 1;q[i]=(uint8_t)x;}for(int i=0;i<8;i++){if(scanf("%u",&x)!=1)return 1;r[i]=(uint8_t)x;}printf("%d\n",link_validate_response(r,q));}return 0;}
'''
            src.write_text(source2,encoding='ascii')
            subprocess.run([*compiler,'-std=c11','-Wall','-Wextra','-Werror','-I',str(ROOT/'host'),str(src),'-o',str(exe)],check=True)
            model=TriangleTile();cases=[]
            for op,val in [(0x30,0),*[(0x31+i,v&65535) for i,v in enumerate(views[0])],(0x38,0),(0x39,0),(0x3a,0)]:
                q=request(op,len(cases)&255,val&255,val>>8);r=model.exchange(q);cases.append((q,r,1))
                for byte in range(8):
                    bad=bytearray(r);bad[byte]^=1;cases.append((q,bad,0))
            q=request(0x30,17,0,0)
            for capability,version,valid in [(3,1,1),(7,1,1),(1,1,0),(15,1,0),(7,2,0)]:
                cases.append((q,seal(bytes([0x5a,0,17,2,capability,version])),valid))
            payload=''.join(' '.join(str(b) for b in bytes(q)+bytes(r))+'\n' for q,r,_ in cases)
            result=subprocess.run([str(exe)],input=payload,text=True,capture_output=True,check=True)
            self.assertEqual(list(map(int,result.stdout.split())),[v for _,_,v in cases])
if __name__=='__main__':unittest.main()
