import unittest
from reference.gfx_bench import GfxBench, INFO, COLOR, CLEAR, PIXEL, READ, ORIGIN, RECT
from reference.link_protocol import request, seal
from tools.dock_gfx_demo import exercise, ppm


class BenchProtocolTests(unittest.TestCase):
    def send(self, bench, op, a=0, b=0):
        return bench.exchange(request(op, 17, a, b))

    def test_demo_complete_image(self):
        bench = GfxBench()
        calls = []
        def exchange(frame):
            calls.append(frame)
            return bench.exchange(frame)
        pixels, sequence = exercise(exchange)
        self.assertEqual(len(pixels), 1024)
        self.assertEqual(sum(f[1] == READ for f in calls), 1024)
        self.assertEqual(sequence, len(calls) % 256)
        self.assertEqual(pixels[2*32+1], 0xf800)
        self.assertEqual(pixels[4*32+12], 0x07e0)
        self.assertEqual(pixels[20*32+4], 0x001f)
        self.assertEqual(pixels[31*32+31], 0xffe0)

    def test_bad_crc_and_range_do_not_mutate(self):
        b = GfxBench()
        self.send(b, COLOR, 0x34, 0x12)
        self.send(b, CLEAR)
        self.send(b, ORIGIN, 31, 31)
        for op, a, c in [(COLOR,1,2), (CLEAR,0,0), (PIXEL,1,1), (ORIGIN,1,1), (RECT,1,1)]:
            before = (b.color, b.origin, b.pixels.copy())
            q = bytearray(request(op, 1, a, c)); q[6] ^= 1
            self.assertEqual(b.exchange(q)[1], 1)
            self.assertEqual((b.color, b.origin, b.pixels), before)
        for op, a, c in [(PIXEL,32,0), (READ,0,32), (ORIGIN,32,0), (RECT,2,1), (RECT,0,1)]:
            before = (b.color, b.origin, b.pixels.copy())
            self.assertEqual(self.send(b, op, a, c)[1], 3)
            self.assertEqual((b.color, b.origin, b.pixels), before)

    def test_fresh_and_clear_semantics(self):
        b = GfxBench()
        self.assertEqual((b.color, b.origin, b.pixels), (0xffff, (0,0), None))
        self.assertEqual(self.send(b, READ, 0, 0)[1], 5)
        self.assertEqual(self.send(b, PIXEL, 0, 0)[1], 5)
        self.assertEqual(self.send(b, RECT, 1, 1)[1], 5)
        self.send(b, ORIGIN, 4, 5)
        self.send(b, COLOR, 0x34, 0x12)
        self.send(b, CLEAR)
        self.assertEqual(b.origin, (0,0))
        self.assertEqual(b.pixels, [0x1234]*1024)
        self.assertEqual(GfxBench().pixels, None)

    def test_rgb565(self):
        data = ppm([0xf800, 0x07e0, 0x001f, 0xffff, 0, 0x8410])
        self.assertEqual(data, b'P6\n32 32\n255\n' + bytes([255,0,0, 0,255,0, 0,0,255, 255,255,255, 0,0,0, 131,129,131]))

    def test_demo_rejects_bad_responses(self):
        for kind in ('sequence', 'status', 'crc', 'short'):
            with self.subTest(kind=kind):
                b = GfxBench()
                def exchange(q):
                    r = b.exchange(q)
                    if kind == 'sequence': return seal(r[:2] + bytes([(r[2]+1)&255]) + r[3:6])
                    if kind == 'status': return seal(r[:1] + b'\x03' + r[2:6])
                    if kind == 'short': return r[:-1]
                    return r[:-1] + bytes([r[-1]^1])
                with self.assertRaises(RuntimeError): exercise(exchange)
