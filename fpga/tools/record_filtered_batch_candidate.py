"""Archive offline filtered+BATCH gates; never programs hardware."""
import argparse,gzip,hashlib,json,re,subprocess
from pathlib import Path
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]
def sha(data):return hashlib.sha256(data).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path);p.add_argument('--source-commit',required=True);a=p.parse_args()
 b=ROOT/'build/filtered-batch-route1';pnr=b/'filtered_reply/impl/pnr'
 soup=BeautifulSoup((pnr/'filtered_reply_tr_content.html').read_text(),'html.parser')
 tables=soup.find_all('table');summary=tables[1].get_text(' ',strip=True)
 counts={k:int(re.search(re.escape(k)+r'\s+(\d+)',summary).group(1))for k in ['Numbers of Paths Analyzed','Numbers of Endpoints Analyzed','Numbers of Setup Violated Endpoints','Numbers of Hold Violated Endpoints']}
 timing_pass=counts['Numbers of Setup Violated Endpoints']==counts['Numbers of Hold Violated Endpoints']==0
 clocks={}
 for row in tables[3].find_all('tr')[1:]:
  c=[x.get_text(' ',strip=True)for x in row.find_all('td')]
  if len(c)>=4:clocks[c[1]]={'target_mhz':float(re.search(r'[\d.]+',c[2]).group()),'fmax_mhz':float(re.search(r'[\d.]+',c[3]).group())}
 for name,hz in [('core54',54),('conditioned_reply54',54),('sampler216',216)]:assert clocks[name]['target_mhz']==hz and clocks[name]['fmax_mhz']>=hz
 minima={};sampler=[]
 for table in tables:
  heading=table.find_previous(['h2','h3']);label=heading.get_text(' ',strip=True)if heading else''
  if label not in ('Setup Paths Table','Hold Paths Table','Recovery Paths Table','Removal Paths Table'):continue
  for row in table.find_all('tr')[1:]:
   c=[x.get_text(' ',strip=True)for x in row.find_all('td')]
   if len(c)<6:continue
   try:slack=float(c[1])
   except ValueError:continue
   minima[label]=min(minima.get(label,float('inf')),slack)
   if c[4]=='sampler216:[R]' and c[5]=='sampler216:[R]':sampler.append({'analysis':label,'slack_ns':slack,'source':c[2],'endpoint':c[3]})
 assert len(minima)==4,minima
 timing_pass=timing_pass and all(v>=0 for v in minima.values())
 for label in ('Setup Paths Table','Hold Paths Table'):assert any(x['analysis']==label and '/meta_s0/Q' in x['source'] and '/sampled_s0/D' in x['endpoint'] for x in sampler)
 sdc=(ROOT/'constraints/dock/triangle54filtered_official.sdc').read_text();assert not re.search(r'^\s*set_(false_path|multicycle_path|clock_groups)',sdc,re.M)
 tcl=(ROOT/'builds/dock/build_filtered_batch_route1.tcl').read_text()
 block=tcl.split('foreach source {',1)[1].split('} {add_file',1)[0]
 sources=block.split()+['builds/dock/build_filtered_batch_route1.tcl','host/triangle_batch.h','host/link_protocol.h']
 for name,token in [('batch-fractal-regression.log','PASS fractal 991'),('batch-triangle-regression.log','PASS 10334'),('filtered-batch-regression.log','PASS batch'),('filtered-batch-route1.log','FILTERED_BATCH_ROUTE1_FLOW_RETURNED')]:assert token in (ROOT/'build'/name).read_text()
 control=json.loads((ROOT/'build/batch-filtered-control.json').read_text());assert control['passed']
 a.output.mkdir(parents=True,exist_ok=True);artifacts=[]
 files=[pnr/'filtered_reply_tr_content.html',pnr/'filtered_reply.rpt.txt',pnr/'filtered_reply.pin.html',pnr/'filtered_reply.fs']
 files +=[ROOT/'build'/n for n in ['batch-fractal-regression.log','batch-triangle-regression.log','filtered-batch-regression.log','filtered-batch-route1.log','batch-filtered-control.json']]
 files +=[ROOT/'build/filtered-batch-official/filtered_reply/impl/pnr/filtered_reply_tr_content.html']
 for source in files:
  raw=source.read_bytes();name=('initial-failed-' if 'filtered-batch-official' in str(source) else '')+source.name+'.gz';data=gzip.compress(raw,mtime=0);(a.output/name).write_bytes(data)
  artifacts.append({'source':str(source.resolve()),'archived':name,'sha256':sha(raw),'gzip_sha256':sha(data),'bytes':len(raw)})
 d={'source_commit':subprocess.check_output(['git','rev-parse',a.source_commit],cwd=ROOT.parent,text=True).strip(),'hardware_access':False,'base_commit':'255e5da','batch_import':'9dee0af','timing_pass':timing_pass,'qualification':'offline functional passes; timing failure retained; NOT ready','limitations':['Base filter physical8MHz CRC failure remains; GPIO and1MHz passed','No measured pad timing/cable ceiling/BER claim','Structural STA does not cover external roundtrip capture aperture'],'sta_counts':counts,'actual_clock_domains':clocks,'min_slack_ns':minima,'sampler_paths':sampler,'no_timing_waivers':True,'source_sha256':{n:sha((ROOT/n).read_bytes())for n in sources},'artifacts':artifacts}
 (a.output/'manifest.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({'clocks':clocks,'min_slack_ns':minima,'output':str(a.output)}))
if __name__=='__main__':main()
