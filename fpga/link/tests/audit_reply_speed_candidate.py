"""Audit actual routed reply clocks, narrow CDC exceptions and four STA analyses."""
import argparse
import hashlib
import json
from pathlib import Path
import re
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[3]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build', type=Path, required=True)
    p.add_argument('--project', required=True)
    p.add_argument('--stem', required=True)
    p.add_argument('--sdc', type=Path, required=True)
    p.add_argument('--metadata-proof', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    pn = a.build/a.project/'impl/pnr'
    fs,sdf,report = [pn/(a.stem+suffix) for suffix in ['.fs','.sdf','_tr_content.html']]
    soup = BeautifulSoup(report.read_text(), 'html.parser')
    tables = soup.find_all('table')
    summary = tables[1].get_text(' ',strip=True)
    fields = ['Numbers of Paths Analyzed','Numbers of Endpoints Analyzed',
              'Numbers of Setup Violated Endpoints','Numbers of Hold Violated Endpoints']
    counts = {f:int(re.search(re.escape(f)+r'\s+(\d+)',summary).group(1)) for f in fields}
    clocks = {}
    for row in tables[3].find_all('tr')[1:]:
        c = [td.get_text(' ',strip=True) for td in row.find_all('td')]
        if len(c)>=4:
            clocks[c[1]] = dict(target_mhz=float(re.search(r'[\d.]+',c[2]).group()),
                               fmax_mhz=float(re.search(r'[\d.]+',c[3]).group()))
    minima = {}
    for table in tables:
        heading = table.find_previous(['h2','h3'])
        label = heading.get_text(' ',strip=True) if heading else ''
        if label not in ['Setup Paths Table','Hold Paths Table','Recovery Paths Table','Removal Paths Table']:
            continue
        for tr in table.find_all('tr')[1:]:
            c = [td.get_text(' ',strip=True) for td in tr.find_all('td')]
            if len(c)<6:
                continue
            try:
                v = float(c[1])
            except ValueError:
                continue
            if label not in minima or v<minima[label]['slack_ns']:
                minima[label] = dict(slack_ns=v,source=c[2],endpoint=c[3],from_clock=c[4],to_clock=c[5])
    normal = lambda s:s.replace('\\/','/').replace('\\.','.')
    edges = [(normal(x),normal(y),d) for x,y,d in re.findall(r'\(INTERCONNECT\s+(\S+)\s+(\S+)\s+\(([\d.:+-]+)\)',sdf.read_text())]
    clock_rows = [dict(source=x,endpoint=y,delay_ns=d) for x,y,d in edges if
                  ('fast_serializer.serializer/' in y and y.endswith('/CLK')) or
                  ('/color_memory/' in y and y.endswith('/CLKB')) or
                  ('/depth_memory/' in y and y.endswith('/CLKB'))]
    common = {r['source'] for r in clock_rows}
    ram = [r for r in clock_rows if r['endpoint'].endswith('/CLKB')]
    common_clock = len(common)==1 and len(ram)==2 and len(clock_rows)>100
    sdc = a.sdc.read_text()
    exception_lines = re.findall(r'^\s*set_false_path.*$',sdc,re.M)
    base = re.findall(r'^\s*set_false_path.*$',(ROOT/'fpga/constraints/dock/all_scenes.sdc').read_text(),re.M)
    exact_exceptions = len(exception_lines)==30 and exception_lines==base
    no_extra_waivers = not re.search(r'^\s*set_(clock_groups|multicycle_path)',sdc,re.M)
    proof = json.loads(a.metadata_proof.read_text())
    cdc_pass = proof['mapped_first_stage_count']==30 and proof['no_stage0_functional_fanout'] and exact_exceptions and no_extra_waivers
    timing_pass = (counts[fields[2]]==counts[fields[3]]==0 and len(minima)==4 and
                   all(x['slack_ns']>=0 for x in minima.values()) and
                   all(x['fmax_mhz']>=x['target_mhz'] for x in clocks.values()))
    snapshot = a.build/'source_snapshot'
    sources = {str(x.relative_to(snapshot)):sha(x) for x in snapshot.rglob('*') if x.is_file()} if snapshot.exists() else {}
    matches = {n:sha(ROOT/'fpga'/n)==v if (ROOT/'fpga'/n).exists() else False for n,v in sources.items()}
    result = dict(hardware_access=False,qualification='offline gates only, not P4/jumper/BER qualification',
                  sta_pass=timing_pass,sta_counts=counts,clocks=clocks,minima=minima,
                  metadata_first_stage_count=30,cdc_pair_and_fanout_pass=cdc_pass,
                  exception_count=len(exception_lines),no_extra_waivers=no_extra_waivers,
                  serializer_and_dpb_shared_clock=common_clock,mapped_reply_clock_sources=sorted(common),
                  reply_clock_endpoint_count=len(clock_rows),ram_clock_endpoints=ram,
                  fs_sha256=sha(fs),usercode=re.search(r'//UserCode:\s*(0x[0-9a-fA-F]+)',fs.read_text()).group(1),
                  sdf_sha256=sha(sdf),timing_report_sha256=sha(report),sdc_sha256=sha(a.sdc),
                  source_snapshot_sha256=sources,current_sources_match_snapshot=matches)
    a.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['sta_pass','cdc_pair_and_fanout_pass','serializer_and_dpb_shared_clock','fs_sha256','usercode']}))
    return 0 if timing_pass and cdc_pass and common_clock else 1


if __name__ == '__main__':
    raise SystemExit(main())
