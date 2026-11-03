import json,os,random,shutil,struct,subprocess,tempfile,unittest
from pathlib import Path
from reference import fire_g0 as F
ROOT=Path(__file__).resolve().parents[2]
HARNESS=r'''#include <stdio.h>
#ifdef _WIN32
#include <io.h>
#include <fcntl.h>
#endif
#include "fire_g0.h"
int main(void){
#ifdef _WIN32
_setmode(_fileno(stdin),_O_BINARY);_setmode(_fileno(stdout),_O_BINARY);
#endif
uint32_t n;if(fread(&n,4,1,stdin)!=1)return 1;
for(uint32_t i=0;i<n;i++){uint32_t r[4];if(fread(r,4,4,stdin)!=4)return 2;
 uint16_t c=fire_g0_color((int)r[0],(int)r[1],r[2],r[3]);fwrite(&c,2,1,stdout);}
return 0;}
'''
def cc_command():
    if os.environ.get('CARRIER_CC_JSON'): return json.loads(os.environ['CARRIER_CC_JSON'])
    found=shutil.which('cc')
    return [found] if found else None
class FireC(unittest.TestCase):
    def test_c_matches_python(self):
        cc=cc_command()
        if not cc: self.skipTest('no C compiler (set CARRIER_CC_JSON)')
        rng=random.Random(20261104)
        cases=[(0,0,0,2),(639,359,0,6),(320,180,17,4),(0,383,65535,6),(639,0,65535,2)]
        for _ in range(3000):
            cases.append((rng.randrange(0,672),rng.randrange(0,384),rng.choice([0,1,17,403,4095,65535,rng.randrange(65536)]),rng.choice([2,4,6])))
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);(d/'h.c').write_text(HARNESS)
            exe=d/'h.exe'
            r=subprocess.run(cc+['-O2','-I',str(ROOT/'host'),'-o',str(exe),str(d/'h.c')],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
            data=struct.pack('<I',len(cases))+b''.join(struct.pack('<4I',*c) for c in cases)
            out=subprocess.run([str(exe)],input=data,capture_output=True)
            self.assertEqual(out.returncode,0)
            got=struct.unpack('<%dH'%len(cases),out.stdout)
            for c,g in zip(cases,got): self.assertEqual(g,F.color(*c),c)
    def test_reference_range_and_variation(self):
        img=[F.color(x,y,17,4) for y in range(0,360,9) for x in range(0,640,16)]
        self.assertGreater(len(set(img)),50)
        self.assertEqual(F.color(320,359,0,6)&0xF800 >= 0x8000, True) # base of the flame is hot (red channel high)
if __name__=='__main__': unittest.main()
