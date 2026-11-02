import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('feature_runner', Path(__file__).parents[1]/'test_features.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class FeatureReportTests(unittest.TestCase):
    def feature(self, readiness='partial'):
        return {'features':[{'id':'npu.dot', 'name':'dot', 'readiness':readiness,
                             'checks':['rtl.dot', 'hardware.npu_dot'], 'missing':['transport']}]}

    def test_rtl_pass_does_not_prove_hardware(self):
        report = runner.feature_results(self.feature(), {'rtl.dot':{'status':'passed'}})[0]
        self.assertEqual(report['verification'], 'partial')
        self.assertEqual(report['checks']['hardware.npu_dot'], 'not_run')

    def test_planned_function_never_inherits_component_pass(self):
        checks = {name:{'status':'passed'} for name in ('rtl.dot', 'hardware.npu_dot')}
        self.assertEqual(runner.feature_results(self.feature('planned'), checks)[0]['verification'], 'not_ready')

    def test_failure_is_visible_on_planned_features(self):
        report = runner.feature_results(self.feature('planned'), {'rtl.dot':{'status':'failed'}})[0]
        self.assertEqual(report['verification'], 'failed')

    def test_ready_requires_all_checks(self):
        checks = {name:{'status':'passed'} for name in ('rtl.dot', 'hardware.npu_dot')}
        self.assertEqual(runner.feature_results(self.feature('ready'), checks)[0]['verification'], 'passed')
