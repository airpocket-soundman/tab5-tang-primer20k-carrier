"""Hash manifest tying together design inputs, extracted data, model code, results and figures of one report (system python).

  python -X utf8 kicad/sim/make_manifest.py

SHA-256 of every file after normalising CRLF -> LF (so the hashes do not depend on git autocrlf). Written to kicad/sim/manifest_r3.json.
`baseline_commit` is the commit the change was made on; the final commit that contains these files is the one that carries the manifest
(a file cannot contain the hash of the commit that contains it) - a third party verifies by recomputing these hashes on a checkout.
"""
import hashlib
import json
import os
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
GROUPS = {
    "purpose_review": ["docs/PoC目的適合性_独立評価とD1修正_2026-10-24.md", "kicad/sim/review_poc_purpose.py",
                       "kicad/sim/poc_purpose_review.json", "kicad/sim/check_d1_bias.py", "kicad/sim/test_d1_bias_check.py",
                       "kicad/sim/d1_bias_check.json", "kicad/sim/regression_d1_bias.json", "kicad/sim/make_poc_review_page.py",
                       "site/poc-purpose-review.html", "kicad/sim/d1_finalizer_reproduction.json",
                       "docs/reference/openems/sources.json"],
    "handover": ["docs/HDMI_R3_監査引継ぎ確認_2026-10-24.md", "kicad/sim/audit_handover.py",
                 "kicad/sim/make_handover_page.py", "kicad/sim/handover_851adf4_2026-10-24.json",
                 "site/hdmi-audit-handover.html", "site/audit-data/handover_851adf4_2026-10-24.json"],
    "design": ["kicad/gen/design.py", "kicad/gen/route_pcb.py", "kicad/gen/make_pcb.py", "kicad/gen/finish_pcb.py",
               "kicad/gen/shorten_d1_bias.py", "kicad/gen/make_bom.py",
               "kicad/lib/carrier.pretty/DFN2510-10L_RCLAMP0524P.kicad_mod", "kicad/tab5-fpga-carrier.kicad_pcb",
               "kicad/tab5-fpga-carrier.kicad_pro",
               "kicad/tab5-fpga-carrier.kicad_sch", "kicad/bom.csv", "kicad/core_pin_assignment.csv"],
    "extracted": ["kicad/sim/tmds_roles.json", "kicad/sim/tmds_geom.json", "kicad/sim/pair_lengths.json", "kicad/sim/zdiff_cache.json", "kicad/sim/tmds_via_policy.json"],
    "model": ["kicad/sim/microstrip2d.py", "kicad/sim/tmds_channel.py", "kicad/sim/tmds_sparam.py", "kicad/sim/make_report_figs.py",
              "kicad/sim/make_report_page.py"],
    "checks": ["kicad/sim/check_continuity.py", "kicad/sim/check_negative.py", "kicad/sim/check_classification.py",
               "kicad/sim/check_esd_footprint.py", "kicad/sim/regression_common.py", "kicad/sim/test_esd_check.py",
               "kicad/sim/test_classification_check.py", "kicad/sim/make_audit_checks_page.py", "kicad/sim/make_manifest.py"],
    "results": ["kicad/sim/continuity_report.json", "kicad/sim/negative_report.json", "kicad/sim/classification_report.json",
                "kicad/sim/esd_footprint_check.json", "kicad/sim/drc_r3.json", "kicad/sim/tmds_summary.json", "kicad/sim/tmds_sparam.json",
                "kicad/sim/report_sparam.json", "kicad/sim/report_variants.json", "kicad/sim/report_matrix.json",
                "kicad/sim/report_sensitivity.json", "kicad/sim/report_stub_effect.json", "kicad/sim/baseline_r2_report_sparam.json",
                "kicad/sim/regression_esd.json", "kicad/sim/regression_classification.json"],
    # The R3 report embeds this manifest, so its HTML is deliberately excluded
    # to avoid a self-referential hash cycle. The addendum only links to it.
    "publication": ["site/index.html", "site/hdmi-audit-checks.html", "docs/HDMI_R3_検査修正_2026-10-24.md",
                    "docs/FPGA_HDMI要求_D2反転とピン.md"],
    "figures": ["site/img/sim_zdiff_r3.png", "site/img/sim_compare_r3.png", "site/img/sim_route_r3.png", "site/img/sim_sparam_r3.png",
                "site/img/sim_variants_r3.png", "site/img/sim_matrix_r3.png", "site/img/sim_sensitivity_r3.png", "site/img/render_top_r3.png"],
}


GROUPS['fabrication_revision'] = [str(p.relative_to(ROOT)).replace('\\','/') for base in ['manufacturing/poc-2026-10-24','docs/reference/openems/calibration-2026-10-24'] for p in Path(ROOT,base).rglob('*') if p.is_file()]
GROUPS['fabrication_revision'] += ['docs/PoC発注準備_パラレル通信と電源_2026-10-24.md','docs/3D均一直線のポート校正_2026-10-24.md','docs/reference/poc-power-sources-2026-10-24.json','kicad/gen/order_parts.json','kicad/gen/export_poc_package.py','kicad/gen/prepare_manufacturing.py','kicad/gen/make_sch.py','kicad/gen/place_pcb.py','kicad/lib/carrier.kicad_sym','kicad/sim/calibrate_uniform_msl.py','kicad/sim/check_ground_reference.py','kicad/sim/ground_reference_check.json','kicad/sim/check_parallel_power.py','kicad/sim/parallel_power_check.json','kicad/sim/test_parallel_power_check.py','kicad/sim/regression_parallel_power.json','kicad/sim/check_power_dc.py','kicad/sim/power_dc_check.json','kicad/sim/review_poc_fabrication.py','kicad/sim/poc_fabrication_review.json','kicad/sim/erc_poc.json','kicad/sim/make_poc_fabrication_page.py','site/poc-fabrication.html','site/uniform-line-calibration.html','site/audit-data/poc-manufacturing-candidate.zip','site/audit-data/uniform-line-calibration.zip','site/audit-data/poc-assembly-top.svg','site/audit-data/poc-assembly-bottom.svg','kicad/sim/check_mbus_revision.py','kicad/sim/mbus_revision_check.json','.gitattributes','kicad/lib/carrier.pretty/PinHeader_2x15_Tab5_Bottom.kicad_mod','docs/reference/tab5/mbus_orientation_confirmation_2026-10-24.json']
GROUPS['fabrication_revision'] += ['docs/reference/'+item['path'] for item in json.load(open(Path(ROOT,'docs/reference/poc-power-sources-2026-10-24.json'),encoding='utf8'))['sources']]


def sha(path):
    data = open(path, "rb").read()
    if os.path.basename(path) == ".gitattributes" or path.endswith((".kicad_sym", ".py", ".json", ".csv", ".kicad_pcb", ".kicad_pro", ".kicad_sch", ".kicad_mod", ".md", ".html")):
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def main():
    base = os.environ.get("BASELINE_COMMIT", "f47f28fa714dfb23843b7516e887ca90acdd0f14")
    out = {"baseline_commit": base, "checker_baseline_commit": "91dc3b4", "files": {}}
    for g, lst in GROUPS.items():
        for rel in lst:
            p = os.path.join(ROOT, rel)
            out["files"][rel] = dict(group=g, sha256=sha(p) if os.path.exists(p) else None)
    json.dump(out, open(os.path.join(HERE, "manifest_r3.json"), "w"), indent=1)
    missing = [k for k, v in out["files"].items() if v["sha256"] is None]
    print("manifest: %d files, missing %s" % (len(out["files"]), missing))


if __name__ == "__main__":
    main()
