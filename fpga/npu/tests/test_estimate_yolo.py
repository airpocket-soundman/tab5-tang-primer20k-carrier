import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import estimate_yolo_ddr3 as e


class YoloEstimateTest(unittest.TestCase):
    def test_params_close_to_published(self):
        for sc, (pp, _) in e.PUBLISHED.items():
            net = e.Net(sc, 640)
            self.assertLess(abs(net.params / 1e6 / pp - 1), 0.12, sc)

    def test_macs_close_to_published(self):
        for sc, (_, fl) in e.PUBLISHED.items():
            net = e.Net(sc, 640)
            self.assertLess(abs(net.macs / 1e9 / (fl / 2) - 1), 0.15, sc)

    def test_resolution_scaling(self):
        for sc in e.SCALES:
            self.assertAlmostEqual(e.Net(sc, 640).macs / e.Net(sc, 320).macs, 4.0, delta=0.3)
            self.assertEqual(e.Net(sc, 640).params, e.Net(sc, 320).params)

    def test_monotonic_in_size(self):
        ms = [e.Net(s, 640).macs for s in "nsmlx"]
        self.assertEqual(ms, sorted(ms))

    def test_peak_act_order(self):
        for sc in e.SCALES:
            lo, hi = e.Net(sc, 640).peak_act()
            self.assertLessEqual(lo, hi)

    def test_ddr_numbers(self):
        self.assertAlmostEqual(e.DDR_THEORY_BW / 1e9, 1.593, places=3)
        self.assertLess(e.DDR_BIST_BW_HIGH, 0.1 * e.DDR_THEORY_BW)

    def test_capacity_claims(self):
        # P4 PSRAM 32MiBに載らず、DDR3 128MiBに載るモデルが存在する(l, x @640)
        for sc in "lx":
            net = e.Net(sc, 640)
            self.assertEqual(e.p4_latency(net)[2], "載らない")
            self.assertLessEqual(net.weight_bytes + net.peak_act()[1], e.DDR3_BYTES)
        self.assertEqual(e.p4_latency(e.Net("n", 320))[2], "載る")

    def test_traffic_ge_weights_and_bad_ge_good(self):
        net = e.Net("m", 640)
        wg, ag = net.ddr_traffic(*e.BUF_GOOD)
        wb, ab = net.ddr_traffic(*e.BUF_BAD)
        self.assertGreaterEqual(wg, net.weight_bytes)
        self.assertGreaterEqual(wb + ab, wg + ag)

    def test_bist_slower_than_theory(self):
        net = e.Net("s", 320)
        best = e.fpga_latency(net, e.SCEN[0], e.BUF_GOOD)["total_s"]
        worst = e.fpga_latency(net, e.SCEN[-1], e.BUF_BAD)["total_s"]
        self.assertGreater(worst, 5 * best)


if __name__ == "__main__":
    unittest.main()
