"""Portable codec CRC against Python's independent C-library implementation."""
import binascii
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import tempfile
import unittest

HOST = Path(__file__).resolve().parents[1]


class IncrementalCrc(unittest.TestCase):
    def test_all_bytes_and_split_buffers(self):
        compiler = json.loads(os.environ['CARRIER_CC_JSON']) if os.environ.get('CARRIER_CC_JSON') else [shutil.which('cc') or shutil.which('gcc')]
        if not compiler[0]:
            self.skipTest('C compiler unavailable')
        rng = random.Random(20261103)
        cases = [(seed, bytes([value]), 0) for seed in (0, 0xffff, 0x1234) for value in range(256)]
        for size in (0, 6, 8, 64, 70, 74, 128, 2048):
            for _ in range(12):
                cases.append((rng.randrange(65536), rng.randbytes(size), rng.randrange(size + 1)))
        program = r'''#include "link_protocol.h"
#include <stdio.h>
int main(void) {
    unsigned seed,n,split,value; unsigned char data[2048];
    while(scanf("%u%u%u",&seed,&n,&split)==3) {
        if(n>sizeof(data)||split>n) return 1;
        for(unsigned i=0;i<n;i++){if(scanf("%u",&value)!=1)return 2;data[i]=(unsigned char)value;}
        unsigned whole=link_crc16_extend((uint16_t)seed,data,n);
        unsigned part=link_crc16_extend((uint16_t)seed,data,split);
        part=link_crc16_extend((uint16_t)part,data+split,n-split);
        printf("%u %u\n",whole,part);
    }
    return 0;
}'''
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'crc.c'
            binary = Path(tmp) / 'crc.exe'
            source.write_text(program)
            subprocess.run([*compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-I', str(HOST), str(source), '-o', str(binary)], check=True)
            data = ''.join(f'{seed} {len(payload)} {split} ' + ' '.join(map(str, payload)) + '\n' for seed, payload, split in cases)
            result = subprocess.run([str(binary)], input=data, text=True, capture_output=True, check=True)
        self.assertEqual(len(result.stdout.splitlines()), len(cases))
        for line, (seed, payload, _) in zip(result.stdout.splitlines(), cases):
            expected = binascii.crc_hqx(payload, seed)
            self.assertEqual(list(map(int, line.split())), [expected, expected])


class SliceBy8Equivalence(unittest.TestCase):
    """The default eight-bytes-per-step CRC must equal the bytewise reference and Python's crc_hqx."""

    def test_every_length_alignment_and_seed(self):
        compiler = json.loads(os.environ['CARRIER_CC_JSON']) if os.environ.get('CARRIER_CC_JSON') else [shutil.which('cc') or shutil.which('gcc')]
        if not compiler[0]:
            self.skipTest('C compiler unavailable')
        rng = random.Random(20261104)
        program = r'''#include "link_protocol.h"
#include <stdio.h>
#include <string.h>
int main(void) {
    static unsigned char buffer[4200];
    unsigned seed,n,align,value; unsigned long long bad=0,cases=0;
    while(scanf("%u%u%u",&seed,&n,&align)==3) {
        if(align>7||n+align>sizeof(buffer)) return 1;
        for(unsigned i=0;i<n;i++){if(scanf("%u",&value)!=1)return 2;buffer[align+i]=(unsigned char)value;}
        unsigned fast=link_crc16_extend((uint16_t)seed,buffer+align,n);
        unsigned ref=link_crc16_extend_bytewise((uint16_t)seed,buffer+align,n);
        printf("%u %u\n",fast,ref);
        cases++; if(fast!=ref) bad++;
    }
    fprintf(stderr,"cases=%llu mismatches=%llu\n",cases,bad);
    return bad?3:0;
}'''
        cases = []
        for n in range(0, 601):
            cases.append((rng.randrange(65536), rng.randbytes(n), n % 8))
        for align in range(8):
            for n in (1, 7, 8, 9, 15, 16, 17, 63, 64, 65, 2048, 2058, 4000):
                cases.append((0xffff, rng.randbytes(n), align))
        for seed in (0, 0xffff, 0x1d0f, 0x8000, 0x0001):
            cases.append((seed, bytes(2058), 0))
            cases.append((seed, bytes([0xff]) * 2058, 3))
        for value in range(256):
            cases.append((0xffff, bytes([value]) * 17, value % 8))
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'slice8.c'
            binary = Path(tmp) / 'slice8.exe'
            source.write_text(program)
            subprocess.run([*compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-I', str(HOST), str(source), '-o', str(binary)], check=True)
            data = ''.join(f'{seed} {len(payload)} {align} ' + ' '.join(map(str, payload)) + chr(10) for seed, payload, align in cases)
            result = subprocess.run([str(binary)], input=data, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.splitlines()
        self.assertEqual(len(lines), len(cases))
        for line, (seed, payload, _) in zip(lines, cases):
            fast, ref = map(int, line.split())
            self.assertEqual(fast, ref)
            self.assertEqual(fast, binascii.crc_hqx(payload, seed))

    def test_generated_tables_are_current(self):
        script = HOST.parent / 'tools' / 'gen_crc16_tables.py'
        subprocess.run([shutil.which('python') or 'python', str(script), '--check'], check=True, capture_output=True)


class TileMetadataSplit(unittest.TestCase):
    def test_metadata_plus_payload_crc_equals_full_validation(self):
        compiler = json.loads(os.environ['CARRIER_CC_JSON']) if os.environ.get('CARRIER_CC_JSON') else [shutil.which('cc') or shutil.which('gcc')]
        if not compiler[0]:
            self.skipTest('C compiler unavailable')
        program = r'''#include "link_protocol.h"
#include <stdio.h>
#include <string.h>
static void build(uint8_t r[2058],const uint8_t q[8],unsigned seed) {
    memset(r,0,2058);r[0]=0x5a;r[1]=0;r[2]=q[2];r[3]=2;r[4]=0;r[5]=q[5];
    uint16_t c=link_crc16(r,6);r[6]=(uint8_t)c;r[7]=(uint8_t)(c>>8);
    for(unsigned i=0;i<2048;i++) r[8+i]=(uint8_t)(seed*131u+i*7u+(i>>3));
    c=link_crc16_extend(link_crc16(r,6),r+8,2048);r[2056]=(uint8_t)c;r[2057]=(uint8_t)(c>>8);
}
int main(void) {
    uint8_t q[8],r[2058];unsigned checked=0;
    for(unsigned seq=0;seq<256;seq+=5) for(unsigned plane=0;plane<2;plane++) {
        link_make_request(q,TRI_TILE_READ|0x80,(uint8_t)seq,0,(uint8_t)plane);
        build(r,q,seq);
        if(!link_validate_tile_response(r,q)||!link_validate_tile_metadata(r,q)) return 1;
        r[8+seq%2048]^=1;                /* payload damage: header stays valid */
        if(link_validate_tile_response(r,q)||!link_validate_tile_metadata(r,q)) return 2;
        build(r,q,seq);r[2]^=1;          /* wrong sequence: both reject */
        if(link_validate_tile_response(r,q)||link_validate_tile_metadata(r,q)) return 3;
        build(r,q,seq);r[6]^=1;          /* header CRC damage: both reject */
        if(link_validate_tile_response(r,q)||link_validate_tile_metadata(r,q)) return 4;
        link_make_request(q,TRI_ROW,(uint8_t)seq,0,0);build(r,q,seq);
        if(link_validate_tile_metadata(r,q)) return 5;   /* wrong op */
        checked++;
    }
    printf("%u\n",checked);return 0;
}'''
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'tilemeta.c'
            binary = Path(tmp) / 'tilemeta.exe'
            source.write_text(program)
            subprocess.run([*compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-I', str(HOST), str(source), '-o', str(binary)], check=True)
            result = subprocess.run([str(binary)], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
