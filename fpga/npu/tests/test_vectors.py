import unittest
import generate_vectors as gen


class VectorTests(unittest.TestCase):
    def test_reference_extrema_and_mac_priority(self):
        v = gen.generate()
        self.assertEqual(v[2]['expected']['accumulator'], -32633)
        self.assertEqual(v[4]['expected']['accumulator'], 7)
        self.assertEqual(v[4]['ready']['end_ready'], 0)
        self.assertEqual(v[5]['expected']['result'], 7)
        self.assertEqual(v[11]['expected']['result'], -23)

    def test_backpressure_and_overflow(self):
        v = gen.generate()
        for i in (6, 7, 8, 9):
            self.assertEqual(v[i]['ready']['begin_ready'], 0)
            self.assertEqual(v[i]['expected']['result'], 7)
        failures = [i for i, r in enumerate(v) if r['expected']['error'] and not v[i-1]['expected']['error']]
        self.assertEqual(len(failures), 2)
        for i in failures:
            self.assertEqual(v[i]['expected']['accumulator'], v[i-1]['expected']['accumulator'])
            self.assertEqual(v[i]['expected']['result_valid'], 0)
            self.assertEqual(v[i+1]['ready'], dict(begin_ready=0, mac_ready=0, end_ready=0))
            self.assertEqual(v[i+2]['expected']['error'], 0)

    def test_generated_tb_deterministic_and_complete(self):
        a, b = gen.generate(), gen.generate()
        self.assertEqual(a, b)
        tb = gen.testbench(a)
        self.assertEqual(tb.count('@(posedge clk)'), len(a))
        self.assertEqual(tb.count('state accumulator'), len(a))
        self.assertIn('$fatal', tb)
        self.assertEqual(a[-1]['expected'], dict(accumulator=0, result=0, result_valid=0, error=0, active=0))


if __name__ == '__main__':
    unittest.main()
