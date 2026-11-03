"""Unique contiguous response recovery after lost training bytes, C vs oracle."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from reference.link_protocol import request,seal,crc16
from reference.link_sync import SyncPrefixDevice
from reference.triangle_tile import TriangleTile
ROOT=Path(__file__).resolve().parents[2]

class LinkSync(unittest.TestCase):
    def test_c_unique_capture(self):
        configured=os.environ.get('CARRIER_CC_JSON')
        compiler=json.loads(configured) if configured else [shutil.which('cc') or shutil.which('gcc')]
        if not compiler[0]:self.skipTest('Existing C compiler unavailable')
        model=SyncPrefixDevice(TriangleTile());cases=[]
        def add(q,raw,length,valid,offset=0,body=b''):
            cases.append((bytes(q),bytes(raw),length,valid,offset,body))
        replies=[]
        for op,value in [(1,0),(2,0xa55a),(3,0x55aa),(4,0),(0x30,0)]:
            q=request(op|128,len(replies),value&255,value>>8);r=model.exchange(q)
            replies.append((q,r[8:]))
        model.exchange(request(0xab,10,0x34,0x12))
        for row,plane in [(0,0),(31,0),(0,1),(31,1)]:
            q=request(0xaf,20+len(replies),row,plane);r=model.exchange(q);replies.append((q,r[8:]))
        for q,body in replies:
            for margin in (8,16):
                wire=bytes([0xc3])*margin+body
                for offset in range(margin+1):
                    raw=bytes([0xc3])*offset+body+bytes([0x7e])*(margin-offset)
                    add(q,raw,len(body),True,offset,body)
                    for byte in range(len(body)):
                        bad=bytearray(raw);bad[offset+byte]^=1
                        add(q,bad,len(body),False)
                add(q,wire[:-1],len(body),False)
                add(q,wire+b'\0',len(body),False)
                badq=bytearray(q);badq[1]^=128;add(badq,wire,len(body),False)
                badq=bytearray(q);badq[2]^=1
                badq=seal(badq[:6]);add(badq,wire,len(body),False)
                badq=bytearray(q);badq[6]^=1;add(badq,wire,len(body),False)
                add(q,wire,74 if len(body)==8 else 8,False)
        # Two disjoint valid ordinary frames must be rejected, not the first
        # one chosen. Also construct overlapping complete ROW frames at0/8.
        q,body=replies[0];add(q,body+body,8,False);add(q,body+body+bytes(8),8,False)
        q,row=replies[-1];raw=bytearray(82);raw[:8]=row[:8];raw[8:16]=row[:8]
        raw[72:74]=crc16(raw[:6]+raw[8:72]).to_bytes(2,'little')
        raw[80:82]=crc16(raw[8:14]+raw[16:80]).to_bytes(2,'little')
        add(q,raw,74,False);add(q,raw+bytes(8),74,False)
        # Metadata mismatch remains invalid even with both CRCs recomputed.
        q,body=replies[-1];bad=bytearray(body);bad[4]^=1
        bad[:8]=seal(bad[:6]);bad[72:74]=crc16(bad[:6]+bad[8:72]).to_bytes(2,'little')
        add(q,bytes([0xc3])*8+bad,74,False)
        source=r'''#include "link_sync.h"
#include <stdio.h>
#include <string.h>
int main(void){unsigned n,len,x;while(scanf("%u%u",&len,&n)==2){
uint8_t q[8],raw[128],guard[76];unsigned offset=999;memset(guard,0xcc,sizeof guard);
if(n>128)return 1;for(unsigned i=0;i<8;i++){if(scanf("%u",&x)!=1)return 2;q[i]=(uint8_t)x;}
for(unsigned i=0;i<n;i++){if(scanf("%u",&x)!=1)return 2;raw[i]=(uint8_t)x;}
bool ok=link_sync_unwrap(raw,n,q,guard+1,len,&offset);
if(guard[0]!=0xcc || guard[75]!=0xcc)return 3;
if(!ok){if(offset!=999)return 4;for(unsigned i=0;i<76;i++)if(guard[i]!=0xcc)return 5;}
printf("%u %u ",ok,offset);if(ok)for(unsigned i=0;i<len;i++)printf("%02x",guard[1+i]);puts("");
}return 0;}
'''
        with tempfile.TemporaryDirectory(prefix='link-sync-c-') as td:
            td=Path(td);src=td/'main.c';exe=td/('test.exe' if os.name=='nt' else 'test');src.write_text(source,encoding='ascii')
            subprocess.run([*compiler,'-std=c11','-Wall','-Wextra','-Werror','-I',str(ROOT/'host'),str(src),'-o',str(exe)],check=True)
            payload=''.join(f'{length} {len(raw)} '+' '.join(map(str,q+raw))+'\n' for q,raw,length,*_ in cases)
            result=subprocess.run([str(exe)],input=payload,text=True,capture_output=True,check=True)
            rows=result.stdout.splitlines();self.assertEqual(len(rows),len(cases))
            for case,row in zip(cases,rows):
                q,raw,length,valid,offset,body=case;fields=row.split()
                self.assertEqual(bool(int(fields[0])),valid,(q.hex(),raw.hex(),length))
                if valid:self.assertEqual(int(fields[1]),offset);self.assertEqual(bytes.fromhex(fields[2]),body)
        print(f'PASS {len(cases)} unique-frame C cases, capture margins8/16 offsets0..16, all body-byte corruption, badrequest/CRC/seq/metadata, truncation and two valid candidates')
if __name__=='__main__':unittest.main()
