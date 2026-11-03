"""Validate and archive experimental official-clock-filter evidence; no hardware."""
import argparse,gzip,hashlib,json,re,subprocess
from pathlib import Path
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]
def digest(data):return hashlib.sha256(data).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--source-commit',required=True);a=p.parse_args()
    pnr=a.build/'filtered_reply/impl/pnr';sta=pnr/'filtered_reply_tr_content.html'
    soup=BeautifulSoup(sta.read_text(),'html.parser');tables=soup.find_all('table')
    summary=tables[1].get_text(' ',strip=True)
    values={key:int(re.search(re.escape(key)+r'\s+(\d+)',summary).group(1))for key in ['Numbers of Paths Analyzed','Numbers of Endpoints Analyzed','Numbers of Setup Violated Endpoints','Numbers of Hold Violated Endpoints']}
    if values['Numbers of Setup Violated Endpoints'] or values['Numbers of Hold Violated Endpoints']:raise ValueError('STA violations; no candidate readiness')
    clocks={}
    for row in tables[3].find_all('tr')[1:]:
        cells=[c.get_text(' ',strip=True)for c in row.find_all('td')]
        if len(cells)>=4:clocks[cells[1]]=dict(target_mhz=float(re.search(r'[\d.]+',cells[2]).group()),actual_fmax_mhz=float(re.search(r'[\d.]+',cells[3]).group()))
    for name,minimum in [('core54',54),('conditioned_reply54',54),('sampler216',216)]:
        if name not in clocks or abs(clocks[name]['target_mhz']-minimum)>.01 or clocks[name]['actual_fmax_mhz']<minimum:raise ValueError('Missing/failed actual domain:'+name)
    sampler_paths=[]
    for table in tables[:12]:
        heading=table.find_previous(['h2','h3']);label=heading.get_text(' ',strip=True)if heading else''
        if label not in ('Setup Paths Table','Hold Paths Table'):continue
        for row in table.find_all('tr')[1:]:
            c=[x.get_text(' ',strip=True)for x in row.find_all('td')]
            if len(c)>=6 and c[4]=='sampler216:[R]'and c[5]=='sampler216:[R]':sampler_paths.append(dict(analysis=label,slack_ns=float(c[1]),source=c[2],endpoint=c[3]))
    for analysis in ('Setup Paths Table','Hold Paths Table'):
        if not any(x['analysis']==analysis and '/meta_s0/Q'in x['source']and'/sampled_s0/D'in x['endpoint']for x in sampler_paths):raise ValueError('Sampler stage0→stage1 coverage missing')
    constraint=ROOT/'constraints/dock/triangle54filtered_official.sdc'
    if re.search(r'^\s*set_(false_path|multicycle_path|clock_groups)',constraint.read_text(),re.M):raise ValueError('No timing waivers permitted')
    files=['link/rtl/reply_clock_filter.v','link/rtl/link_reply_raw.v','link/rtl/link_bringup_filtered.v',
           'gfx/rtl/triangle_tile_vendor.v','gfx/rtl/tile_dpram_vendor.v','gfx/rtl/triangle_fragment.v',
           'gfx/rtl/triangle_coverage_pipeline.v','gfx/rtl/triangle_depth.v','platform/dock/dock_pll54.v',
           'platform/dock/dock_pll216.v','platform/dock/tab5_dock_triangle54_filtered_top.v',
           'constraints/dock/tab5_dock_link_v0.cst','constraints/dock/triangle54filtered_official.sdc',
           'builds/dock/build_clock_filter_reset216.tcl']
    models=[]
    for name in ['filtered-reply-final-reset216-2026-11-04.json','filtered-reply-final-low-rates-2026-11-04.json']:
        model=json.loads((ROOT/'validation'/name).read_text())
        for source,sha in model['source_sha256'].items():
            path=ROOT/source
            if path.exists()and digest(path.read_bytes())!=sha:raise ValueError('Model source drift:'+source)
        models.append(dict(path=name,sha256=digest((ROOT/'validation'/name).read_bytes()),cases=len(model['cases']),functional_passed=sum(x['full_body_exact']for x in model['cases']),conditional_2ns_setup_hold_passed=sum(x['conditional_setup_hold_passed']for x in model['cases'])))
    a.output.mkdir(parents=True,exist_ok=True)
    artifacts=[]
    for source in [sta,pnr/'filtered_reply.rpt.txt',pnr/'filtered_reply.pin.html',pnr/'filtered_reply.fs',ROOT/'build/clock-filter-reset216-run.log']:
        raw=source.read_bytes();compressed=gzip.compress(raw,mtime=0);name=source.name+'.gz';(a.output/name).write_bytes(compressed)
        artifacts.append(dict(source=str(source.resolve()),archived=name,sha256=digest(raw),bytes=len(raw),gzip_sha256=digest(compressed)))
    d=dict(schema=1,hardware_access=False,qualification='offline source/functional/STA gates passed; parent physical review/programming still required',
           implementation='combined sampled216 conditioning +explicitvendorDPB +4stagecoverage +local216resetrelease; not originalfastreplyimplementation',
           base_commit='9c314f3',source_commit=subprocess.check_output(['git','rev-parse',a.source_commit],cwd=ROOT.parent,text=True).strip(),sta_summary=values,actual_clock_domains=clocks,sampler_explicit_paths=sampler_paths,
           no_timing_waivers=True,models=models,native_ram_checks=2050,native_cpu_and_pipeline_coverage_vectors=3328,
           polygon_oracle_transactions=10334,fractal_oracle_transactions=991,fractal_color_depth_pixels=24576,
           source_sha256={f:digest((ROOT/f).read_bytes())for f in files},artifacts=artifacts,
           limitations=['No physical cable maximum/BER proof','Digital assumed wire0/2/5ns,Tco0/2ns,hostsetuphold2ns are not measured pads','Official sampler-only STA does not substitute full-image STA','Prior OSSmissingendpoint records retained; exacttoolbugcause not counterfactually proven'])
    (a.output/'manifest.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps(dict(output=str(a.output),clocks=clocks)))
if __name__=='__main__':main()
