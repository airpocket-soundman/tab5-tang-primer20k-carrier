import json
import unittest
from unittest.mock import patch

from tools import dock_gfx_demo as demo


class FakePort:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.writes = []
        self.closed = False
        self.resets = 0
    def reset_input_buffer(self): self.resets += 1
    def write(self, data): self.writes.append(data)
    def flush(self): pass
    def readline(self): return next(self.replies, b'')
    def close(self): self.closed = True


def line(value):
    return (json.dumps(value) + '\n').encode()


def bridge(port):
    b = demo.SerialBridge.__new__(demo.SerialBridge)
    b.port = port
    b.arm_attempted = False
    return b


class SerialBridgeTests(unittest.TestCase):
    def test_matching_xfer_and_status(self):
        p = FakePort([line({'service':'boot'}), line({'armed':False}),
                      line({'armed':False, 'profile':'dock-jumper-v0', 'verified':True}),
                      line({'armed':False, 'profile':'dock-jumper-v0', 'verified':True}),
                      line({'ok':False, 'error':'stale', 'op':1, 'seq':6}),
                      line({'op':2, 'seq':7, 'frame':'00'}),
                      line({'op':1, 'seq':8, 'frame':'00'}),
                      line({'op':1, 'seq':7, 'frame':'5a00070254500000'})])
        b = bridge(p)
        self.assertTrue(b.command('status')['verified'])
        self.assertEqual(b.exchange(bytes([0xa5,1,7,2,0,0,0,0])), bytes.fromhex('5a00070254500000'))
        self.assertEqual(p.resets, 2)
        self.assertEqual(p.writes, [b'status\n', b'xfer 1 7 0 0\n'])

    def test_close_after_arm_failure_and_without_arm(self):
        p = FakePort([line({'error':'failed'}), line({'error':'disarm_failed'})])
        b = bridge(p)
        with self.assertRaises(RuntimeError): b.command('arm dock-jumper-v0')
        with self.assertRaises(RuntimeError): b.close()
        self.assertTrue(p.closed)
        self.assertEqual(p.writes[-1], b'disarm\n')
        p = FakePort([]); b = bridge(p); b.close()
        self.assertTrue(p.closed)
        self.assertEqual(p.writes, [])

    def test_main_preserves_original_error(self):
        p = FakePort([line({'armed':False, 'profile':'dock-jumper-v0', 'verified':True}),
                      line({'armed':True}), line({'error':'disarm_failed'})])
        b = bridge(p)
        with patch.object(demo, 'SerialBridge', return_value=b), \
             patch.object(demo, 'exercise', side_effect=ValueError('original')), \
             patch('sys.argv', ['demo', '--port', 'fake', '--arm']):
            with self.assertRaisesRegex(ValueError, 'original'): demo.main()
        self.assertTrue(p.closed)
