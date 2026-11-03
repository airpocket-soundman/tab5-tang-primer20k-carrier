import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('run_synth_bench', Path(__file__).with_name('run_synth_bench.py'))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

class ModelChecks(unittest.TestCase):
    def test_overlay_replaces_only_selected_modules(self):
        base = 'module KEEP; endmodule\nmodule SPX9; endmodule\nmodule IOBUF; endmodule'
        overlay = 'module SPX9; initial $display("ram"); endmodule\nmodule IOBUF; assign O=IO; endmodule'
        result = runner.overlay_models(base, overlay)
        self.assertTrue(result.startswith('module KEEP; endmodule'))
        self.assertEqual(result.count('module SPX9;'), 1)
        self.assertIn('initial $display("ram")', result)
        self.assertEqual(runner.model_defects(result), [])
    def test_overlay_rejects_missing_or_duplicate_modules(self):
        valid = 'module SPX9; endmodule\nmodule IOBUF; endmodule'
        for base, overlay in [(valid, ''), ('', valid), (valid+valid, valid), (valid, valid+valid)]:
            with self.assertRaises(ValueError):
                runner.overlay_models(base, overlay)
    def test_known_bad_models(self):
        model = '''module SPX9(DO); parameter INIT=0; output DO; endmodule
                    module IOBUF(O, IO, I); input I; output O; inout IO;
                    assign I = IO; endmodule'''
        issues = runner.model_defects(model)
        self.assertEqual(len(issues), 2)
        self.assertIn('SPX9', issues[0])
        self.assertIn('IOBUF', issues[1])
    def test_missing_and_comments_do_not_count(self):
        self.assertEqual(len(runner.model_defects('module SPX9; // always\n endmodule')), 2)
    def test_behavioral_fixture_passes_screen_only(self):
        model = '''module SPX9; always @(posedge CLK) DO <= mem[AD]; endmodule
                   module IOBUF; assign O = IO; assign IO = I; endmodule'''
        self.assertEqual(runner.model_defects(model), [])
