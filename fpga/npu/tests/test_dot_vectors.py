import unittest
import generate_dot_vectors as gen


class DotJobVectorsTests(unittest.TestCase):
    def test_complete_jobs_match_cpu_golden(self):
        data=gen.generate()
        outcomes={0:0,1:0,2:0}
        for job in data['jobs']:
            c=job['config']
            try:
                gen.validate(c)
            except ValueError:
                error,result=1,None
            else:
                try:
                    if job['pairs']:
                        a=[[p[0] for p in job['pairs']]]
                        b=[[p[1]] for p in job['pairs']]
                        acc=gen.gold.tiled_gemm(a,b,[c['bias']],c['input_zero_point'])[0][0]
                    else:
                        acc=c['bias']
                except OverflowError:
                    error,result=2,None
                else:
                    error=0
                    result=gen.gold.requantize(acc,c['multiplier'],c['shift'],c['output_zero_point'],c['lower'],c['upper'])
            self.assertEqual((job['error'],job['result']),(error,result))
            outcomes[error]+=1
        self.assertEqual(outcomes[1],8)
        self.assertEqual(outcomes[2],2)
        self.assertGreater(outcomes[0],70)

    def test_stream_count_latching_stall_and_reset(self):
        vectors=gen.generate()['vectors']
        active_config=None
        accepted=0
        for v in vectors:
            i,b,e=v['inputs'],v['before'],v['expected']
            if i['reset']:
                self.assertEqual(e,dict(begin_ready=1,sample_ready=0,result_valid=0,result=0,busy=0,error=0,error_code=0))
                active_config=None
                continue
            if i['begin_valid'] and b['begin_ready'] and not e['error']:
                active_config=i.copy()
                accepted=0
            if i['sample_valid'] and b['sample_ready']:
                accepted+=1
                self.assertIsNotNone(active_config)
                self.assertLessEqual(accepted,active_config['length'])
            if e['result_valid']:
                self.assertEqual(accepted,active_config['length'])
                self.assertEqual(e['sample_ready'],0)
                self.assertEqual(e['begin_ready'],0)
            if b['result_valid']:
                self.assertEqual(e['result'],b['result'])
                self.assertEqual(e['result_valid'],int(not i['result_ready']))
                self.assertEqual(b['begin_ready'],0)
            if b['error']:
                self.assertEqual(e,b)
                self.assertEqual(b['begin_ready'],0)
                self.assertEqual(b['sample_ready'],0)

    def test_deterministic_tb_has_each_cycle_asserted(self):
        data=gen.generate()
        self.assertEqual(data,gen.generate())
        tb=gen.testbench(data)
        count=len(data['vectors'])
        self.assertEqual(tb.count('@(posedge clk)'),count)
        self.assertEqual(tb.count('after result"'),count)
        self.assertIn('int8_dot_job dut',tb)
        self.assertIn('$fatal',tb)


if __name__=='__main__':
    unittest.main()
