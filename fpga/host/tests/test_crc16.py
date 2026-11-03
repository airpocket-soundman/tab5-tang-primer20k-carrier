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


if __name__ == '__main__':
    unittest.main()
