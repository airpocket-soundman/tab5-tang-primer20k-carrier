import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reference.gfx_bench import GfxBench, INFO, COLOR, CLEAR, PIXEL, READ, ORIGIN, RECT
from reference.link_protocol import request, seal


def compiler_command():
    value = os.environ.get('CARRIER_CC_JSON')
    if value is not None:
        try:
            args = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError('CARRIER_CC_JSON must be a JSON array of nonempty argument strings') from exc
        if not isinstance(args, list) or not args or any(not isinstance(arg, str) or not arg.strip() for arg in args):
            raise ValueError('CARRIER_CC_JSON must be a JSON array of nonempty argument strings')
        return args
    compiler = shutil.which('cc') or shutil.which('gcc')
    return [compiler] if compiler else None


class CodecTests(unittest.TestCase):
    def test_compiler_command_configuration(self):
        with patch.dict(os.environ, {'CARRIER_CC_JSON': '["path with spaces/zig.exe", "cc"]'}):
            self.assertEqual(compiler_command(), ['path with spaces/zig.exe', 'cc'])
        for invalid in ('', 'not json', '[]', '["cc", ""]', '["cc", 1]', '"cc"'):
            with self.subTest(value=invalid), patch.dict(os.environ, {'CARRIER_CC_JSON': invalid}):
                with self.assertRaises(ValueError):
                    compiler_command()

    def test_c_codec_against_oracle(self):
        cc = compiler_command()
        if not cc:
            self.skipTest('C compiler unavailable')
        bench = GfxBench()
        cases = []
        for seq, (op, a, b) in enumerate([(1,0,0), (2,0x55,0xaa), (3,0x55,0xaa),
                (INFO,0,0), (COLOR,0x34,0x12), (CLEAR,0,0), (PIXEL,31,31),
                (READ,31,31), (ORIGIN,2,3), (RECT,4,5), (PIXEL,32,0), (0xff,0,0)]):
            q = request(op, seq, a, b)
            r = bench.exchange(q)
            cases.append((q, r, r[1] == 0))
            for offset in (0, 1, 2, 3, 4, 6):
                damaged = bytearray(r)
                damaged[offset] ^= 1
                cases.append((q, bytes(damaged), False))
            wrong_sequence = seal(r[:2] + bytes([(r[2]+1)&255]) + r[3:6])
            cases.append((q, wrong_sequence, False))
            wrong_status = seal(r[:1] + b'\x03' + r[2:6])
            cases.append((q, wrong_status, False))
            if r[1] == 0 and op != READ:
                wrong_data = seal(r[:4] + bytes([r[4]^1, r[5]]))
                cases.append((q, wrong_data, False))
        source = Path(__file__).with_name('codec_harness.c')
        with tempfile.TemporaryDirectory() as tmp:
            binary = str(Path(tmp)/('codec.exe' if os.name == 'nt' else 'codec'))
            subprocess.run([*cc, '-std=c99', '-Wall', '-Wextra', '-Werror', str(source), '-o', binary], check=True)
            data = ''.join(' '.join(f'{v:02x}' for v in q+r) + '\n' for q,r,_ in cases)
            result = subprocess.run([binary], input=data, text=True, capture_output=True, check=True)
        lines = result.stdout.splitlines()
        self.assertEqual(len(lines), len(cases))
        for (q, _, accepted), line in zip(cases, lines):
            made, valid = line.split()
            self.assertEqual(made, q.hex())
            self.assertEqual(int(valid), accepted)
