import unittest
import generate_requant_vectors as gen


class RequantVectorsTests(unittest.TestCase):
    def test_accepted_arithmetic_independent_formula(self):
        count = 0
        shifts = set()
        for v in gen.generate():
            ins, expected = v['inputs'], v['expected']
            if ins['reset'] or not ins['input_valid'] or not v['input_ready'] or expected['error']:
                continue
            count += 1
            shifts.add(ins['shift'])
            product = ins['accumulator'] * ins['multiplier']
            denominator = 2 ** ins['shift']
            quotient, remainder = divmod(abs(product), denominator)
            if 2 * remainder >= denominator:
                quotient += 1
            rounded = -quotient if product < 0 else quotient
            result = max(ins['lower'], min(ins['upper'], rounded + ins['zero_point']))
            self.assertEqual(expected['result'], result)
            self.assertEqual(expected['output_valid'], 1)
        self.assertGreater(count, 450)
        self.assertEqual(shifts, set(range(63)))

    def test_stalls_rejections_and_reset(self):
        vectors = gen.generate()
        errors = 0
        stalls = 0
        for i, v in enumerate(vectors):
            ins, state = v['inputs'], v['expected']
            if ins['reset']:
                self.assertEqual(state, dict(output_valid=0, result=0, error=0))
                continue
            previous = vectors[i-1]['expected']
            if previous['output_valid']:
                stalls += 1
                self.assertEqual(v['input_ready'], 0)
                self.assertEqual(state['result'], previous['result'])
                self.assertEqual(state['output_valid'], int(not ins['output_ready']))
            if state['error'] and not previous['error']:
                errors += 1
                self.assertEqual(state['result'], previous['result'])
                self.assertEqual(state['output_valid'], 0)
            if previous['error']:
                self.assertEqual(v['input_ready'], 0)
                self.assertEqual(state, previous)
        self.assertEqual(errors, 11)
        self.assertGreater(stalls, 500)

    def test_deterministic_complete_testbench(self):
        vectors = gen.generate()
        self.assertEqual(vectors, gen.generate())
        tb = gen.testbench(vectors)
        self.assertEqual(tb.count('@(posedge clk)'), len(vectors))
        self.assertEqual(tb.count('state result'), len(vectors))
        self.assertIn('$fatal', tb)
        self.assertIn('int8_requantize dut', tb)


if __name__ == '__main__':
    unittest.main()
