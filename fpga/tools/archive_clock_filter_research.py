"""Archive timing-coverage reproductions without programming a device."""
import gzip,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    output=ROOT/'validation/clock-filter-coverage-research-2026-11-04';output.mkdir(exist_ok=True)
    files={
      'oss-sampler-coverage.json':ROOT/'build/sampler-only-oss-repro/coverage.json',
      'oss-sampler-pnr.log':ROOT/'build/sampler-only-oss-repro/pnr.log',
      'oss-sampler-timing.json':ROOT/'build/sampler-only-oss-repro/timing.json',
      'oss-sampler-routed.json':ROOT/'build/sampler-only-oss-repro/routed.json',
      'oss-full-pnr.log':ROOT/'build/clock-filter-anchors/pnr.log',
      'oss-full-detailed-timing.json':ROOT/'build/clock-filter-anchors/detailed-report.json',
      'official-sampler-sta.html':ROOT/'build/filter-timing-only-official/filter_timing/impl/pnr/filter_timing_tr_content.html',
      'official-inferred-ram-failure.log':ROOT/'build/clock-filter-official-run.log',
      'official-vendor-core-failure-sta.html':ROOT/'build/clock-filter-official-vendor/filtered_reply/impl/pnr/filtered_reply_tr_content.html',
      'official-pipeline-reset-failure-sta.html':ROOT/'build/clock-filter-official-pipeline/filtered_reply/impl/pnr/filtered_reply_tr_content.html',
      'native-vendor-fractal.log':ROOT/'build/vendor-fractal-regression.log',
      'native-vendor-polygon.log':ROOT/'build/vendor-polygon-regression.log',
      'pipeline-vendor-fractal.log':ROOT/'build/pipeline-fractal-regression.log',
      'pipeline-vendor-polygon.log':ROOT/'build/pipeline-polygon-regression.log'}
    digest=lambda b:hashlib.sha256(b).hexdigest();artifacts=[]
    for name,path in files.items():
        raw=path.read_bytes();compressed=gzip.compress(raw,mtime=0);(output/(name+'.gz')).write_bytes(compressed)
        artifacts.append(dict(source=str(path.resolve()),archived=name+'.gz',sha256=digest(raw),gzip_sha256=digest(compressed)))
    package=Path('D:/GitHub/tab5-tang-primer20k-carrier/fpga/build/oss-env/Lib/site-packages/yowasp_nextpnr_himbaechel_gowin')
    tools=[package/'nextpnr-himbaechel-gowin.wasm',package/'share/himbaechel/gowin/chipdb-GW2A-18.bin',
           Path('D:/Gowin/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe'),
           Path('D:/Gowin/Gowin_V1.9.11.03_Education_x64/IDE/simlib/gw2a/prim_sim.v')]
    report=dict(hardware_access=False,scope='immutable offline evidence; no electrical/cable or counterfactual tool-patch proof',
      oss_version='nextpnr0.11.1 / yowasp0.11.1.0.post826',official_version='Education1.9.11.03',
      tools=[dict(path=str(p),sha256=digest(p.read_bytes()))for p in tools],artifacts=artifacts)
    (output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(output)
if __name__=='__main__':main()
