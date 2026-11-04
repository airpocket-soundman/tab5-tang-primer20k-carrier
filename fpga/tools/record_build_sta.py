"""Record a Gowin build (FS/BIN SHA, USERCODE, full STA summary) WITHOUT asserting closure.

Violations are recorded as found. No hardware access. Example:
  python tools/record_build_sta.py --pnr <.../impl/pnr> --base phase_t3_f0 --name phase_t3_f0 \
      --source-commit <sha> --output validation/<dir>/phase_t3_f0.json
"""
import argparse,hashlib,json,re
from pathlib import Path
from bs4 import BeautifulSoup
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pnr',type=Path,required=True);p.add_argument('--base',required=True);p.add_argument('--name',required=True)
    p.add_argument('--source-commit',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--note',default='')
    a=p.parse_args()
    fs=(a.pnr/(a.base+'.fs')).read_bytes();binf=(a.pnr/(a.base+'.bin')).read_bytes()
    text=fs.decode('latin-1')
    usercode=re.search(r'//UserCode: (0x[0-9A-Fa-f]+)',text).group(1)
    checksum=re.search(r'//CheckSum: (0x[0-9A-Fa-f]+)',text).group(1)
    norm=re.sub(rb'//Created Time:[^\r\n]*',b'//Created Time: <stripped>',fs)
    tr=a.pnr/(a.base+'_tr_content.html')
    if not tr.exists():tr=a.pnr/(a.base+'.tr.html')
    soup=BeautifulSoup(tr.read_text(encoding='utf-8',errors='replace'),'html.parser');tables=soup.find_all('table')
    summary=tables[1].get_text(' ',strip=True)
    counts={}
    for k in ['Numbers of Paths Analyzed','Numbers of Endpoints Analyzed','Numbers of Setup Violated Endpoints','Numbers of Hold Violated Endpoints']:
        m=re.search(re.escape(k)+r'\s+(\d+)',summary);counts[k]=int(m.group(1)) if m else None
    clocks={}
    for row in tables[3].find_all('tr')[1:]:
        c=[x.get_text(' ',strip=True) for x in row.find_all('td')]
        if len(c)>=4:
            try:clocks[c[1]]={'target_mhz':float(re.search(r'[\d.]+',c[2]).group()),'fmax_mhz':float(re.search(r'[\d.]+',c[3]).group())}
            except AttributeError:clocks[c[1]]={'raw':c}
    minima={}
    for table in tables:
        heading=table.find_previous(['h2','h3']);label=heading.get_text(' ',strip=True) if heading else ''
        if label not in('Setup Paths Table','Hold Paths Table','Recovery Paths Table','Removal Paths Table'):continue
        for row in table.find_all('tr')[1:]:
            c=[x.get_text(' ',strip=True) for x in row.find_all('td')]
            if len(c)<6:continue
            try:s=float(c[1])
            except ValueError:continue
            if label not in minima or s<minima[label]:minima[label]=s
    d=dict(hardware_access=False,name=a.name,source_commit=a.source_commit,note=a.note,
        fs_sha256=sha(fs),fs_sha256_created_time_stripped=sha(norm),bin_sha256=sha(binf),usercode=usercode,checksum=checksum,
        sta_counts=counts,clock_domains=clocks,min_slack_ns=minima,
        sta_closed=(counts.get('Numbers of Setup Violated Endpoints')==0 and counts.get('Numbers of Hold Violated Endpoints')==0),
        report_files={f.name:sha(f.read_bytes()) for f in sorted(a.pnr.glob(a.base+'*')) if f.suffix in('.rpt','.txt','.html','.sdf','.vo','.fs','.bin') or f.name.endswith('.rpt.txt')},
        limitations=['Offline P&R/STA only; not programmed or tested on hardware','Violations are recorded, not hidden'])
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(d,indent=2)+'\n')
    print(json.dumps(dict(name=a.name,usercode=usercode,fs_sha256=d['fs_sha256'][:12],counts=counts,min_slack=minima,closed=d['sta_closed'])))
if __name__=='__main__':main()
