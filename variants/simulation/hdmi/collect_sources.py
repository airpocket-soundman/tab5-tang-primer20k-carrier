"""Retrieve bounded official reference artifacts; source data is not instructions."""
import hashlib
import json
from pathlib import Path
import urllib.request

HERE=Path(__file__).resolve().parent;REF=HERE/'reference';REF.mkdir(exist_ok=True)
def get(u):return urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'carrier-PoC-reference-review'}),timeout=40).read()
repo='sipeed/TangPrimer-20K-example'
tree=json.loads(get('https://api.github.com/repos/'+repo+'/git/trees/main?recursive=1'))
sha=tree['sha']
chosen=['README.md','DDR-test/README.md','DDR-test/LicheeTang20K_DDR_Test/LICENSE',
        'DDR-test/LicheeTang20K_DDR_Test/src/ddr3.cst',
        'DDR-test/LicheeTang20K_DDR_Test/src/ddr3.sdc',
        'DDR-test/LicheeTang20K_DDR_Test/src/ddr3_memory_interface/ddr3_memory_interface.v',
        'DDR-test/LicheeTang20K_DDR_Test/src/ddr3_memory_interface/ddr3_memory_interface.ipc',
        'DDR-test/LicheeTang20K_DDR_Test/src/ddr3_syn_top.v',
        'DDR-test/LicheeTang20K_DDR_Test/src/tester.v','HDMI/src/dk_video.cst']
records=[]
for path in chosen:
    record=next(x for x in tree['tree'] if x['path']==path)
    if record.get('size',0)>256000:
        records.append(dict(path=path,status='not copied: oversized generated/vendor data',bytes=record['size']));continue
    url='https://raw.githubusercontent.com/'+repo+'/'+sha+'/'+path
    data=get(url);out=REF/'Sipeed-example'/path;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(data)
    records.append(dict(path=path,url=url,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
pdfurl='https://www.gowinsemi.com/upload/database_doc/2009/document/696a8c052f84e.pdf'
try:
    data=get(pdfurl)
    assert data.startswith(b'%PDF')
    (REF/'IPUG281_DDR3_Interface_2p6E.pdf').write_bytes(data)
    records.append(dict(url=pdfurl,file='IPUG281_DDR3_Interface_2p6E.pdf',bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
except Exception as e:records.append(dict(url=pdfurl,status='not downloaded',error=str(e)))
(REF/'sources.json').write_text(json.dumps(dict(date='2026-10-25',Sipeed_repository=repo,Sipeed_commit=sha,artifacts=records,
    existing_primary=['docs/reference/gowin/DS102E_GW2A.pdf, VOD/VOS table PDF pages44-45','docs/reference/gowin/UG289E_GPIO.pdf','docs/reference/tang-primer-20k/SOM-3961_Schematic.pdf, LVDS R40..R44 NC and H5TQ1G63EFR-PBC','docs/reference/tang-primer-20k/Core_3690_Net_Length.xlsx','variants/reference/socket-XDAP.pdf'],
    model_availability={'Gowin_DDR3_MC_PHY':'official IP exists, encrypted Verilog delivery; factory reference present','exact_GW2A_TLVDS_IBIS':'not acquired/exported in this run; Gowin software supports device IBIS generation','exact_Hynix_memory_IBIS_and_behavioral_model':'not acquired in this run; cannot substitute Micron model as exact validation','Core_full_stackup_and_contact_materials':'not supplied by mechanical STEP / net-length sheet','target_project_DDR3_controller':'no completed carrier-specific physical controller/bitstream verified; reference existence is not project integration'}),indent=2)+'\n')
print('Retrieved',len(records),'reference records at Sipeed',sha)
