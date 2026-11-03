import tempfile
import unittest
from pathlib import Path
from analyze_output_sdf import analyze


class SdfPaths(unittest.TestCase):
    def test_sequential_boundary_and_route_sum(self):
        text='(TIMESCALE 1 ns)\n'
        text+='(CELL\n(CELLTYPE "DFF") (INSTANCE fast_ff) (IOPATH CLK Q (1:2:3)))\n'
        # A very slow signal at D must not leak through the FF boundary.
        text+='(CELL\n(CELLTYPE "DFF") (INSTANCE other_ff) (IOPATH CLK Q (100:200:300)))\n'
        text+='(INTERCONNECT other_ff/Q fast_ff/D (100:200:300))\n'
        for bit in range(8):
            text+=f'(CELL\n(CELLTYPE "IOBUF") (INSTANCE data_{bit}_iobuf) (IOPATH I IO (4:5:6)))\n'
            text+=f'(INTERCONNECT fast_ff/Q data_{bit}_iobuf/I (7:8:9))\n'
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'test.sdf'; p.write_text(text)
            result=analyze(p,'fast_ff')
        self.assertEqual(len(result['bits']),8)
        for row in result['bits']:
            self.assertEqual(row['min_ns'],12)
            self.assertEqual(row['max_ns'],18)
            self.assertEqual(row['max_path'][0],'fast_ff/CLK')
            self.assertNotIn('other_ff/Q',row['max_path'])

    def test_missing_selected_start_fails(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'test.sdf';p.write_text('(TIMESCALE 1 ns)')
            with self.assertRaises(AssertionError):
                analyze(p,'missing')


if __name__=='__main__':
    unittest.main()
