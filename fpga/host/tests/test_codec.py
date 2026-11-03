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
from reference.triangle_tile import TriangleTile


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
    def assert_c_cases(self, cases):
        cc = compiler_command()
        if not cc:
            self.skipTest('C compiler unavailable')
        source = Path(__file__).with_name('codec_harness.c')
        with tempfile.TemporaryDirectory() as tmp:
            binary = str(Path(tmp)/('codec.exe' if os.name == 'nt' else 'codec'))
            subprocess.run([*cc, '-std=c99', '-Wall', '-Wextra', '-Werror', str(source), '-o', binary], check=True)
            data = ''.join(' '.join(f'{v:02x}' for v in q+r) + '\n' for q,r,_ in cases)
            result = subprocess.run([binary], input=data, text=True, capture_output=True, check=True)
        lines = result.stdout.splitlines()
        self.assertEqual(len(lines), len(cases))
        for (q, r, accepted), line in zip(cases, lines):
            with self.subTest(op=q[1], seq=q[2], response=r.hex()):
                made, valid = line.split()
                self.assertEqual(made, q.hex())
                self.assertEqual(int(valid), accepted)

    def test_optional_request_capture_codec(self):
        cases=[]
        def add(op,a,b,value,ok=True):
            q=request(op,255,a,b);r=seal(bytes([0x5a,0,255,2,value&255,value>>8]));cases.append((q,r,ok))
        for tag in (0,128):
            add(0x42|tag,0,0,0x103)
            add(0x42|tag,1,0,0x103,False)
            add(0x42|tag,0,0,0x104,False)
            for word in range(4):add(0x43|tag,word,0,0xd927)
            add(0x43|tag,4,0,0xd927,False);add(0x43|tag,0,1,0xd927,False)
            for selector in (0,2):add(0x44|tag,selector,0,0xffff)
            for flags in (1,3,5,7):add(0x44|tag,1,0,0x800|flags)
            for v in (0x800,0x809,0x705,0x905):add(0x44|tag,1,0,v,False)
            add(0x44|tag,3,0,0,False);add(0x44|tag,0,1,0,False)
        self.assert_c_cases(cases)

    def test_optional_clock_v2_codec(self):
        cases=[]
        old=TriangleTile()
        new=TriangleTile(core_clock_mhz=54,clock_query_enable=True)
        for model in (old,new):
            for op,a,b in [(0x30,0,0),(0x3d,0,0),(0x3d,1,0),(0x3d,0,1)]:
                q=request(op,len(cases),a,b);r=model.exchange(q)
                cases.append((q,r,r[1]==0))
        q=request(0x30,71,0,0)
        for value,accepted in [(0x0103,True),(0x0107,True),(0x020f,True),(0x0117,True),(0x021f,True),
                               (0x010f,False),(0x0207,False),(0x030f,False)]:
            r=seal(bytes([0x5a,0,q[2],2,value&255,value>>8]))
            cases.append((q,r,accepted))
        for tag in (0,128):
            q=request(0x3d|tag,72,0,0)
            for mhz in (0,1,27,54,200,201,256):
                r=seal(bytes([0x5a,0,q[2],2,mhz&255,mhz>>8]))
                cases.append((q,r,1<=mhz<=200))
                badseq=seal(r[:2]+bytes([q[2]^1])+r[3:6])
                cases.append((q,badseq,False))
        self.assert_c_cases(cases)

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
        self.assert_c_cases(cases)

    def test_triangle_codec_against_independent_oracle(self):
        bench = TriangleTile()
        cases = []
        def exchange(op, a=0, b=0):
            q = request(op, len(cases) & 255, a, b)
            r = bench.exchange(q)
            cases.append((q, r, r[1] == 0))
            return q, r

        # Error replies from uninitialized/read-range/unknown-command checks.
        for op, a, b in [(0x20,0,0), (0x2c,0,0), (0x2d,0,0), (0x2e,0,0),
                         (0x2d,32,0), (0x2e,0,32), (0x2c,1,0), (0xff,0,0)]:
            exchange(op,a,b)
        # Negative fractional coordinates and nonconstant Z exercise the wire
        # representation used by the signed G0 oracle; all 10 setters are used.
        values = [-8,-8, 488,8, 24,488, 1,32768,65535,0x5a3c]
        for i, value in enumerate(values):
            word = value & 65535
            q, r = exchange(0x21+i, word & 255, word >> 8)
            cases.append((q, seal(r[:4]+bytes([r[4]^1,r[5]])), False))
        exchange(0x2b,0x34,0x12)
        q, r = exchange(0x2c)
        self.assertGreater(r[4] | r[5] << 8, 0)
        # Every pixel's color/depth comes from the independent CPU rasterizer.
        # The codec checks framing; numerical equality remains a host check.
        for y in range(32):
            for x in range(32):
                exchange(0x2d,x,y)
                exchange(0x2e,x,y)
        q, r = exchange(0x2c)  # Strict equal-Z makes the repeated draw write zero.
        self.assertEqual(r[4:6], b'\0\0')
        q, r = exchange(0x2b,0xff,0xff)
        self.assertEqual(r[4:6], b'\0\0')
        cases.append((q,seal(r[:4]+b'\1\0'),False))

        draw_q = request(0x2c,0x61,0,0)
        for value, accepted in [(0,True),(1,True),(1024,True),(1025,False),(65535,False)]:
            cases.append((draw_q,seal(bytes([0x5a,0,0x61,2,value&255,value>>8])),accepted))
        # CRC-valid malformed envelopes must still be rejected.
        q = request(0x20,0x62,0,0)
        good = bench.exchange(q)
        for offset, replacement in [(0,0xa5),(1,2),(1,3),(1,5),(2,0x63),(3,1)]:
            damaged = bytearray(good[:6]); damaged[offset] = replacement
            cases.append((q,seal(damaged),False))
        for offset in range(8):
            damaged = bytearray(good); damaged[offset] ^= 1
            cases.append((q,bytes(damaged),False))
        unknown_q = request(0xff,0x63,0,0)
        cases.append((unknown_q,seal(bytes([0x5a,0,0x63,2,0,0])),False))
        # A bad incoming CRC yields an error response from the oracle, which the
        # success-only C validator must reject even though its reply CRC is valid.
        bad_q = bytearray(q); bad_q[7] ^= 1
        cases.append((q,bench.exchange(bad_q),False))
        self.assert_c_cases(cases)
