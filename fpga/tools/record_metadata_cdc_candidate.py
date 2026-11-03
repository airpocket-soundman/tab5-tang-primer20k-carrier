"""Fail-closed archive gate for the exact30-exception routing-closed candidate."""
import argparse,gzip,hashlib,json,re,subprocess,sys
from pathlib import Path
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--source-commit',required=True);a=p.parse_args()
 build=ROOT/'build/filtered-batch-cdc-qualified';pnr=build/'filtered_reply/impl/pnr'
 proofpath=ROOT/'validation/filtered-batch-cdc-proof-2026-11-04/structure.json'
 subprocess.run([sys.executable,str(ROOT/'tools/qualify_metadata_cdc.py'),'--sdf',str(pnr/'filtered_reply.sdf'),'--output',str(proofpath)],check=True)
 subprocess.run([sys.executable,str(ROOT/'tools/generate_metadata_cdc_constraints.py'),'--proof',str(proofpath),'--output',str(ROOT/'constraints/dock/triangle54filtered_batch_cdc.sdc'),'--verify'],check=True)
 proof=json.loads(proofpath.read_text());expected={(r['first_stage_D'][:-1]+'Q',r['only_Q_consumer'])for r in proof['first_stage_pins']};assert len(expected)==30
 soup=BeautifulSoup((pnr/'filtered_reply_tr_content.html').read_text(),'html.parser');tables=soup.find_all('table');summary=tables[1].get_text(' ',strip=True)
 counts={k:int(re.search(re.escape(k)+r'\s+(\d+)',summary).group(1))for k in ['Numbers of Paths Analyzed','Numbers of Endpoints Analyzed','Numbers of Setup Violated Endpoints','Numbers of Hold Violated Endpoints']}
 assert counts['Numbers of Setup Violated Endpoints']==counts['Numbers of Hold Violated Endpoints']==0
 clocks={}
 for row in tables[3].find_all('tr')[1:]:
  c=[x.get_text(' ',strip=True)for x in row.find_all('td')]
  if len(c)>=4:clocks[c[1]]={'target_mhz':float(re.search(r'[\d.]+',c[2]).group()),'fmax_mhz':float(re.search(r'[\d.]+',c[3]).group())}
 for name,hz in [('core54',54),('conditioned_reply54',54),('sampler216',216)]:assert clocks[name]['target_mhz']==hz and clocks[name]['fmax_mhz']>=hz
 minima={};reported={'Setup Paths Table':{},'Hold Paths Table':{}};sampler=[]
 for table in tables:
  heading=table.find_previous(['h2','h3']);label=heading.get_text(' ',strip=True)if heading else''
  if label not in ('Setup Paths Table','Hold Paths Table','Recovery Paths Table','Removal Paths Table'):continue
  for row in table.find_all('tr')[1:]:
   c=[x.get_text(' ',strip=True)for x in row.find_all('td')]
   if len(c)<6:continue
   try:slack=float(c[1])
   except ValueError:continue
   minima[label]=min(minima.get(label,float('inf')),slack)
   pair=(c[2],c[3])
   if pair in expected and label in reported:reported[label][pair]=slack;assert c[4]==c[5]=='conditioned_reply54:[R]'
   if c[4]==c[5]=='sampler216:[R]' and '/meta_s0/Q' in c[2] and '/sampled_s0/D' in c[3]:sampler.append(dict(analysis=label,slack_ns=slack,source=c[2],endpoint=c[3]))
 assert len(minima)==4 and all(v>=0 for v in minima.values()),minima
 for kind,paths in reported.items():assert set(paths)==expected,(kind,len(paths))
 for kind in reported:assert any(r['analysis']==kind for r in sampler)
 control=json.loads((ROOT/'build/batch-filtered-cdc-control.json').read_text());assert control['passed'] and control['metadata_cdc_assertions']
 for source,digest in control['source_snapshot_sha256'].items():
  if source.startswith(('link/rtl/','gfx/rtl/')):assert sha((ROOT/source).read_bytes())==digest,'control source drift:'+source
 for name,token in [('batch-fractal-regression.log','PASS fractal 991'),('batch-triangle-regression.log','PASS 10334'),('filtered-batch-regression.log','PASS batch'),('filtered-batch-cdc-qualified.log','FILTERED_BATCH_CDC_QUALIFIED_RETURNED')]:assert token in (ROOT/'build'/name).read_text()
 audit=json.loads((ROOT/'build/offer-identity-audit.json').read_text());assert audit['only_change_identity_on_serializer_offer'] and audit['original_immediate_oe_ready_and_metadata_lifecycle_unchanged']
 assert audit['source_sha256']==sha((ROOT/'link/rtl/link_bringup_filtered.v').read_bytes())
 tcl=(ROOT/'builds/dock/build_filtered_batch_cdc_qualified.tcl').read_text();sources=tcl.split('foreach source {',1)[1].split('} {add_file',1)[0].split()+['builds/dock/build_filtered_batch_cdc_qualified.tcl','host/triangle_batch.h','host/link_protocol.h']
 a.output.mkdir(parents=True,exist_ok=True);artifacts=[]
 files=[pnr/n for n in ['filtered_reply_tr_content.html','filtered_reply.rpt.txt','filtered_reply.pin.html','filtered_reply.fs','filtered_reply.sdf','filtered_reply.vo']]
 files +=[ROOT/'build'/n for n in ['batch-fractal-regression.log','batch-triangle-regression.log','filtered-batch-regression.log','filtered-batch-cdc-qualified.log','batch-filtered-cdc-control.json','offer-identity-audit.json']]
 for source in files:
  raw=source.read_bytes();name=source.name+'.gz';data=gzip.compress(raw,mtime=0);(a.output/name).write_bytes(data);artifacts.append(dict(source=str(source.resolve()),archived=name,sha256=sha(raw),gzip_sha256=sha(data),bytes=len(raw)))
 d=dict(hardware_access=False,source_commit=subprocess.check_output(['git','rev-parse',a.source_commit],cwd=ROOT.parent,text=True).strip(),qualification='Offline CDC-qualified and routing-closed ONLY; root peer review and physical trial still required',sta_counts=counts,actual_clock_domains=clocks,min_slack_ns=minima,cdc_exceptions=dict(count=30,exact_source_Q_to_stage0_D=proof['first_stage_pins'],no_stage1_or_clear_or_clock_group_exception=True,source_held_before_offer_through_done=True),all30_stage01_setup_and_hold_paths={k:[dict(source=q,endpoint=d,slack_ns=v)for(q,d),v in paths.items()]for k,paths in reported.items()},sampler_explicit_stage01_paths=sampler,identity_audit=audit,source_sha256={s:sha((ROOT/s).read_bytes())for s in sources},artifacts=artifacts,limitations=['Exact30 legitimate asynchronous first-stage exceptions explicitly present; NOT a no-exceptions design','Source identity and mapped regression, not full-netlist formal equivalence','No metastability MTBF, measured external IO timing or physical cable ceiling guarantee','Original6c5a negative8MHz CRC failure retained; SDK-positive physical tests use a different source/bitstream until root trials this candidate'])
 (a.output/'manifest.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps(dict(counts=counts,min_slack_ns=minima,stage01_each=30,output=str(a.output))))
if __name__=='__main__':main()
