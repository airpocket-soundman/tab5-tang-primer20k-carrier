import json,os,shutil,subprocess,tempfile,unittest
from pathlib import Path
from reference.link_protocol import request,crc16
ROOT=Path(__file__).resolve().parents[2]
class BatchCodec(unittest.TestCase):
 def test_encode(self):
  cc=json.loads(os.environ['CARRIER_CC_JSON']) if os.environ.get('CARRIER_CC_JSON') else [shutil.which('cc')]
  if not cc[0]:self.skipTest('C compiler unavailable')
  source=r'''#include <stdio.h>
#include <string.h>
#ifdef _WIN32
#include <io.h>
#include <fcntl.h>
#endif
#include "triangle_batch.h"
int main(void){
#ifdef _WIN32
_setmode(_fileno(stdout),_O_BINARY);
#endif
uint8_t out[1292];uint16_t records[640];for(unsigned i=0;i<640;i++)records[i]=(uint16_t)(i*431+0x8000);
for(unsigned n=0;n<=65;n++)for(unsigned t=0;t<2;t++){
 memset(out,0xa7,sizeof(out));unsigned z=triangle_batch_encode(out,1290,255,t,records,n);
 if(n==0||n==65){if(z||out[0]!=0xa7)return 1;continue;}
 if(z!=10+20*n||out[z]!=0xa7||out[z+1]!=0xa7)return 2;
 unsigned short length=z;fwrite(&length,2,1,stdout);fwrite(out,1,z,stdout);
 if(triangle_batch_encode(out,z-1,0,t,records,n))return 3;
 uint8_t r[8]={0x5a,0,255,2,n,1};uint16_t c=link_crc16(r,6);r[6]=c;r[7]=c>>8;
 if(!link_validate_response(r,out))return 4;
 r[4]^=1;c=link_crc16(r,6);r[6]=c;r[7]=c>>8;if(link_validate_response(r,out))return 5;
}
return triangle_batch_encode(0,1290,0,0,records,1)||triangle_batch_encode(out,1290,0,0,0,1);}
'''
  with tempfile.TemporaryDirectory() as td:
   td=Path(td);(td/'a.c').write_text(source);exe=td/'test.exe'
   subprocess.run(cc+['-std=c11','-O2','-I',str(ROOT/'host'),str(td/'a.c'),'-o',str(exe)],check=True)
   raw=subprocess.check_output([str(exe)])
  cursor=0
  for n in range(1,65):
   for tagged in (False,True):
    length=int.from_bytes(raw[cursor:cursor+2],'little');cursor+=2;body=raw[cursor:cursor+length];cursor+=length
    q=request(0x41|(128 if tagged else 0),255,n,1)
    data=b''.join(((i*431+0x8000)&65535).to_bytes(2,'little') for i in range(10*n))
    self.assertEqual(body,q+data+crc16(q[:6]+data).to_bytes(2,'little'))
  self.assertEqual(cursor,len(raw))
