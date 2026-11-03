"""Portable bounded stream parser: independent wire fixtures and DMA split points."""
import json,os,shutil,subprocess,tempfile,unittest
from pathlib import Path
from reference.link_protocol import request
from reference.triangle_tile import TriangleTile
from reference.link_sync import SyncPrefixDevice
ROOT=Path(__file__).resolve().parents[2]

class StreamTests(unittest.TestCase):
 def test_observed_stream_boundaries(self):
  configured=os.environ.get('CARRIER_CC_JSON')
  cc=json.loads(configured) if configured else [shutil.which('cc') or shutil.which('gcc')]
  if not cc[0]:self.skipTest('C compiler unavailable')
  model=SyncPrefixDevice(TriangleTile());fixtures=[]
  def fixture(op,a=0,b=0,tag=True):
   q=request(op|(128 if tag else 0),255,a,b);wire=model.exchange(q);fixtures.append((q,wire[8:] if tag else wire))
  fixture(1);fixture(1,tag=False);model.exchange(request(0x2b,1,0x34,0x12))
  for i,v in enumerate([8,8,440,8,8,440,100,500,900,0xf81f]):
   model.exchange(request(0x21+i,2,v&255,v>>8))
  model.exchange(request(0x2c,3,0,0))
  for plane in (0,1):fixture(0x2f,12,plane);fixture(0x3b,0,plane)
  arrays=[];entries=[]
  for i,(q,body) in enumerate(fixtures):
   arrays.append('static const unsigned char q%d[]={%s},b%d[]={%s};'%(i,','.join(map(str,q)),i,','.join(map(str,body))))
   entries.append('{q%d,b%d,sizeof(b%d)}'%(i,i,i))
  code=r'''
#include "link_stream.h"
#include <stdio.h>
#include <stdlib.h>
static unsigned long tests=0;
#define CHECK(x) do{++tests;if(!(x)){fprintf(stderr,"line%d assertion %s\n",__LINE__,#x);return 1;}}while(0)
struct fixture {const uint8_t*q,*body;size_t n;};
ARRAYS
static const struct fixture fixtures[]={ENTRIES};
static void reseal(uint8_t *r,size_t n){uint16_t c=link_crc16(r,6);r[6]=(uint8_t)c;r[7]=(uint8_t)(c>>8);
 if(n>8){c=link_crc16_extend(link_crc16(r,6),r+8,(unsigned)n-10);r[n-2]=(uint8_t)c;r[n-1]=(uint8_t)(c>>8);}}
static int run(const struct fixture*f){
 uint8_t raw[8192],window[8192],q[8],bad[8192];link_stream s;size_t n=f->n,total=n+24;
 memset(raw,0xc3,8);memcpy(raw+8,f->body,n);memset(raw+8+n,0x7e,16);
 // Split every byte boundary, including both CRCs and complete body endpoints.
 for(size_t split=0;split<=total;split++){
  CHECK(link_stream_begin(&s,f->q,n,1000,4096,window,sizeof window)==LINK_STREAM_NEED_MORE);
  CHECK(link_stream_feed(&s,1000,raw,split)!=LINK_STREAM_UNIQUE);
  CHECK(link_stream_body(&s)==NULL);
  CHECK(link_stream_feed(&s,1000+split,raw+split,total-split)==LINK_STREAM_CANDIDATE);
  CHECK(link_stream_finalize(&s)==LINK_STREAM_UNIQUE);CHECK(link_stream_finalize(&s)==LINK_STREAM_UNIQUE);
  CHECK(s.matched_offset==1008 && s.matched_end==1008+n);
  CHECK(memcmp(link_stream_body(&s),f->body,n)==0);
  CHECK(s.window_size==total && memcmp(window,raw,total)==0);
 }
 const unsigned chunks[]={1,2,3,7,8,31,127,128,129,255,256,257,512,1024};
 for(unsigned k=0;k<sizeof chunks/sizeof *chunks;k++){
  CHECK(link_stream_begin(&s,f->q,n,1000,4096,window,sizeof window)==LINK_STREAM_NEED_MORE);
  for(size_t pos=0;pos<total;){size_t len=chunks[k];if(len>total-pos)len=total-pos;
   CHECK(!link_stream_failed(link_stream_feed(&s,1000+pos,raw+pos,len)));pos+=len;}
  CHECK(link_stream_finalize(&s)==LINK_STREAM_UNIQUE);CHECK(s.matched_offset==1008);
 }
 // No missing byte is reconstructed, and corruption of every body byte fails.
 for(size_t byte=0;byte<n;byte++){
  memcpy(bad,raw,total);bad[8+byte]^=1;
  CHECK(link_stream_begin(&s,f->q,n,1000,4096,window,sizeof window)==LINK_STREAM_NEED_MORE);
  CHECK(link_stream_feed(&s,1000,bad,total)==LINK_STREAM_NEED_MORE);
  CHECK(link_stream_finalize(&s)==LINK_STREAM_NO_MATCH);CHECK(link_stream_body(&s)==NULL);
 }
 for(size_t missing=0;missing<n;missing++){
  memcpy(bad,raw,8+missing);memcpy(bad+8+missing,raw+9+missing,total-9-missing);
  CHECK(link_stream_begin(&s,f->q,n,1000,4096,window,sizeof window)==LINK_STREAM_NEED_MORE);
  CHECK(link_stream_feed(&s,1000,bad,total-1)==LINK_STREAM_NEED_MORE);
  CHECK(link_stream_finalize(&s)==LINK_STREAM_NO_MATCH);
 }
 // Correct-CRC response with wrong sequence or metadata remains invalid.
 memcpy(bad,raw,total);bad[10]^=1;reseal(bad+8,n);
 CHECK(link_stream_begin(&s,f->q,n,1000,4096,window,sizeof window)==LINK_STREAM_NEED_MORE);
 CHECK(link_stream_feed(&s,1000,bad,total)==LINK_STREAM_NEED_MORE);CHECK(link_stream_finalize(&s)==LINK_STREAM_NO_MATCH);
 memcpy(bad,raw,total);bad[13]^=1;reseal(bad+8,n);
 CHECK(link_stream_begin(&s,f->q,n,1000,4096,window,sizeof window)==LINK_STREAM_NEED_MORE);
 CHECK(link_stream_feed(&s,1000,bad,total)==LINK_STREAM_NEED_MORE);CHECK(link_stream_finalize(&s)==LINK_STREAM_NO_MATCH);
 // Previous accepted body has the SAME seq after wrap. Fence excludes it.
 memcpy(bad,f->body,n);memset(bad+n,0x7e,13);memcpy(bad+n+13,raw,total);
 CHECK(link_stream_begin(&s,f->q,n,1000+n,4096,window,sizeof window)==LINK_STREAM_NEED_MORE);
 CHECK(link_stream_feed(&s,1000,bad,n+13+total)==LINK_STREAM_CANDIDATE);
 CHECK(link_stream_finalize(&s)==LINK_STREAM_UNIQUE);CHECK(s.matched_offset==1000+n+21);
 // Fence inside header rejects a stale body's start, even if its tail arrives later.
 CHECK(link_stream_begin(&s,f->q,n,1001,4096,window,sizeof window)==LINK_STREAM_NEED_MORE);
 CHECK(link_stream_feed(&s,1000,f->body,n)==LINK_STREAM_NEED_MORE);CHECK(link_stream_finalize(&s)==LINK_STREAM_NO_MATCH);
 // Actual seq255->0 wrap accepts only newly observed seq0, not the previous255.
 memcpy(q,f->q,8);link_make_request(q,q[1],0,q[4],q[5]);
 memcpy(bad,raw,total);bad[10]=0;reseal(bad+8,n);
 CHECK(link_stream_begin(&s,q,n,1000,4096,window,sizeof window)==LINK_STREAM_NEED_MORE);
 CHECK(link_stream_feed(&s,1000,raw,total)==LINK_STREAM_NEED_MORE);
 CHECK(link_stream_feed(&s,1000+total,bad,total)==(2*total>4096?LINK_STREAM_OVERFLOW:LINK_STREAM_CANDIDATE));
 if(2*total<=4096){CHECK(link_stream_finalize(&s)==LINK_STREAM_UNIQUE);CHECK(s.matched_offset==1008+total);}
 // Real255->0 wrap also succeeds for full tiles under the previous-end fence.
 CHECK(link_stream_begin(&s,q,n,1000+total,4096,window,sizeof window)==LINK_STREAM_NEED_MORE);
 CHECK(link_stream_feed(&s,1000,raw,total)==LINK_STREAM_NEED_MORE);
 CHECK(link_stream_feed(&s,1000+total,bad,total)==LINK_STREAM_CANDIDATE);
 CHECK(link_stream_finalize(&s)==LINK_STREAM_UNIQUE);CHECK(s.matched_offset==1008+total);
 // Gaps, duplicate chunks, limits and invalid requests fail closed.
 CHECK(link_stream_begin(&s,f->q,n,0,4096,window,sizeof window)==LINK_STREAM_NEED_MORE);
 CHECK(link_stream_feed(&s,20,raw,3)==LINK_STREAM_NEED_MORE);
 CHECK(link_stream_feed(&s,24,raw+3,4)==LINK_STREAM_GAP);CHECK(link_stream_finalize(&s)==LINK_STREAM_GAP);
 CHECK(link_stream_begin(&s,f->q,n,0,4096,window,sizeof window)==LINK_STREAM_NEED_MORE);
 CHECK(link_stream_feed(&s,20,raw,3)==LINK_STREAM_NEED_MORE);CHECK(link_stream_feed(&s,20,raw,3)==LINK_STREAM_GAP);
 CHECK(link_stream_begin(&s,f->q,n,0,n,window,sizeof window)==LINK_STREAM_NEED_MORE);
 CHECK(link_stream_feed(&s,0,f->body,n)==LINK_STREAM_CANDIDATE);
 CHECK(link_stream_feed(&s,n,raw,1)==LINK_STREAM_OVERFLOW);CHECK(link_stream_finalize(&s)==LINK_STREAM_OVERFLOW);CHECK(link_stream_body(&s)==NULL);
 memcpy(q,f->q,8);q[6]^=1;CHECK(link_stream_begin(&s,q,n,0,4096,window,sizeof window)==LINK_STREAM_INVALID);
 CHECK(link_stream_begin(&s,f->q,n,0,4096,window,8)==LINK_STREAM_INVALID);
 CHECK(link_stream_begin(&s,f->q,n+1,0,4096,window,sizeof window)==LINK_STREAM_INVALID);
 CHECK(link_stream_begin(&s,f->q,n,0,4096,window,sizeof window)==LINK_STREAM_NEED_MORE);
 CHECK(link_stream_feed(&s,UINT64_MAX,raw,1)==LINK_STREAM_OVERFLOW);
 // Two disjoint short frames or overlapping large frames must not choose first.
 if(n==8){memcpy(bad,f->body,n);memcpy(bad+n,f->body,n);total=2*n;}
 else{memset(bad,0,n+16);memcpy(bad,f->body,n);memcpy(bad+16,f->body,8);reseal(bad,n);reseal(bad+16,n);total=n+16;}
 CHECK(link_stream_begin(&s,f->q,n,0,4096,window,sizeof window)==LINK_STREAM_NEED_MORE);
 CHECK(link_stream_feed(&s,0,bad,n)==LINK_STREAM_CANDIDATE);
 CHECK(link_stream_feed(&s,n,bad+n,total-n)==LINK_STREAM_AMBIGUOUS);
 CHECK(link_stream_finalize(&s)==LINK_STREAM_AMBIGUOUS);CHECK(link_stream_body(&s)==NULL);
 return 0;
}
int main(void){for(unsigned i=0;i<sizeof fixtures/sizeof *fixtures;i++)if(run(&fixtures[i]))return 1;
 printf("PASS %lu stream assertions: every split/body corruption/deletion, chunks1/128/256, fence+seqwrap, metadata, ambiguity, gaps/overflow\n",tests);return 0;}
'''.replace('ARRAYS','\n'.join(arrays)).replace('ENTRIES',','.join(entries))
  with tempfile.TemporaryDirectory(prefix='stream-parser-') as td:
   td=Path(td);src=td/'test.c';exe=td/('test.exe' if os.name=='nt' else 'test');src.write_text(code,encoding='ascii')
   for language,standard in [('c','c11'),('c++','c++17')]:
    subprocess.run([*cc,'-x',language,'-std='+standard,'-Wall','-Wextra','-Werror','-I',str(ROOT/'host'),str(src),'-o',str(exe)],check=True)
    r=subprocess.run([str(exe)],capture_output=True,text=True,check=True,timeout=180);print(language+': '+r.stdout.strip())
if __name__=='__main__':unittest.main()
