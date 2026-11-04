"""Attest the DDR3 isolation variant builds (offline). Usage: record_variant.py base cs0 rst refwait
Saves gz'd FS/report/timing/console under validation/mem-variant-<id>-2026-11-04/ and one summary JSON.
Timing/pin facts come from the tool reports; nothing here implies hardware function."""
import sys,re,json,gzip,hashlib,os
from html.parser import HTMLParser
from pathlib import Path
root=Path(__file__).resolve().parents[2]
DATE=os.environ.get('MEM_REC_DATE','2026-11-04')  # newip2 batch: MEM_REC_DATE=2026-11-05 MEM_REC_SUMMARY=mem-variants-newip2-2026-11-05.json
SUMMARY=os.environ.get('MEM_REC_SUMMARY','mem-variants-prehardware-2026-11-04.json')
ids=sys.argv[1:] or ['base','cs0','rst','refwait']
def sha(b):return hashlib.sha256(b).hexdigest()
class Text(HTMLParser):
    def __init__(s):super().__init__();s.items=[]
    def handle_data(s,d):
        if d.strip():s.items.append(d.strip())
def cst_audit(report):
    cst=(root/'mem/config/mem_bist.cst').read_text(encoding='utf-8-sig')
    exp=dict(re.findall(r'^IO_LOC\s+"([^"]+)"\s+([A-Z]\d+(?:,[A-Z]\d+)?)',cst,re.M))
    types=dict(re.findall(r'^IO_PORT\s+"([^"]+)"\s+IO_TYPE=(\w+)',cst,re.M))
    act={}
    for line in report.splitlines():
        f=[v.strip() for v in line.split('|')]
        if len(f)>10 and re.fullmatch(r'[a-zA-Z_]\w*(?:\[\d+\])?',f[0]):act[f[0]]=f
    bad=[]
    for n,b in exp.items():
        r=act.get(n)
        if not r or r[2].split('/')[0]!=b or r[7]!=types[n] or r[-1]!=('1.5' if '15' in types[n] else '3.3'):bad.append(n)
    return {'constrained_ports':len(exp),'mismatches':bad,'passed':not bad}
summary={'scope':'offline builds only; no programmer/UART/DRAM access; physical DDR behaviour unverified; STA is internal-constrained, not external DDR timing',
 'tool':'Gowin V1.9.11.03 Education (81398), gw_sh, no programming','part':'GW2A-LV18PG256C8/I7','device_version':'C',
 'memdd3_vo_sha256':sha((root/'build/mem-bist-ip/generated/MemDDR3/MemDDR3.vo').read_bytes()) if (root/'build/mem-bist-ip/generated/MemDDR3/MemDDR3.vo').exists() else None,
 'memdd3_vo_note':'differs from frozen 4d37c875...; MemDDR3.ipc and gwmc_param.v hashes equal the recorded ones; only the Created Time header is believed to differ (base FS reproduces be42c604 apart from its Created Time comment).',
 'reference_be42c604':'be42c604aeb3217cbcf7743f46c49a585dbfe414b1900bace6bf703f197ebeea','variants':{}}
base_body=None
for vid in ids:
    d=root/f'build/mem-variant-{vid}'
    pnr=d/'out/mem_bist/impl/pnr'
    console=root/f'build/mem-variant-{vid}-console.log'
    if not (pnr/'mem_bist.fs').exists():
        summary['variants'][vid]={'built':False,'console':console.name,'note':'no .fs produced'};continue
    raw_log=console.read_bytes()
    log=raw_log.decode('utf-16') if raw_log[:2] in (bytes([255,254]),bytes([254,255])) else raw_log.decode('utf-8',errors='replace')
    assert 'MEM_BUILD_FLOW_RETURNED' in log and not re.search(r'ERROR\s*\(',log),vid
    fs=(pnr/'mem_bist.fs').read_bytes()
    body=b'\n'.join(l for l in fs.split(b'\n') if not l.startswith(b'//'))
    t=Text();t.feed((pnr/'mem_bist_tr_content.html').read_text());I=t.items
    def fol(l):return I[I.index(l)+1]
    def worst(tab):
        it=I[I.index(tab):]
        if 'Data Delay' not in it[:16]:return None
        i=it.index('Data Delay')+1
        return {'slack_ns':float(it[i+1]),'from':it[i+2],'to':it[i+3]} if it[i]=='1' else None
    def neg(tab):
        s=I.index(tab)
        if 'Data Delay' not in I[s:s+16]:return 0
        i=I.index('Data Delay',s)+1;n=0
        while I[i].isdigit():
            n+=I[i+1].startswith('-');i+=9
        return n
    fm=I[I.index('Max Frequency Summary:'):]
    def fmax(n):return float(fm[fm.index(n)+2].replace('(MHz)',''))
    rep=(pnr/'mem_bist.rpt.txt').read_text()
    uc=re.search(r'//UserCode: (0x\w+)',fs.decode()).group(1)
    out=root/f'validation/mem-variant-{vid}-{DATE}';out.mkdir(parents=True,exist_ok=True)
    for src,name in [(pnr/'mem_bist.fs','mem_bist.fs.gz'),(pnr/'mem_bist.rpt.txt','mem_bist.rpt.txt.gz'),(pnr/'mem_bist_tr_content.html','mem_bist_tr_content.html.gz'),(console,'build-console.log.gz')]:
        with gzip.GzipFile(out/name,'wb',mtime=0) as g:g.write(src.read_bytes())
    if vid=='base':base_body=body
    rv=json.loads((d/'variant.json').read_text())
    if rv.get('ip_tag'):
        ipd=root/f"build/mem-bist-ip-{rv['ip_tag']}/generated/MemDDR3"
        summary['variants'].setdefault('_ip',{})[vid]={'tag':rv['ip_tag'],'memddr3_vo_sha256':sha((ipd/'MemDDR3.vo').read_bytes()),'gwmc_param_sha256':sha((ipd/'temp/DDR3/gwmc_param.v').read_bytes()),'ipc_sha256':sha((ipd/'MemDDR3.ipc').read_bytes()),'gwmc_param_selected':dict(re.findall(r'parameter (tCK|ADDR_CMD_MODE|OUTPUT_DRV|CL|CWL) = "?(\w+)"?;',(ipd/'temp/DDR3/gwmc_param.v').read_text()))}
    summary['variants'][vid]={'built':True,'description':rv['description'],
     'fs_sha256':sha(fs),'fs_sha256_without_comment_lines':sha(body),'usercode':uc,
     'fs_bytes':len(fs),'usercode_equals_reference_be42c604':uc=='0x0000B317',
     'fs_body_identical_to_base':None if base_body is None else body==base_body,
     'sta':{'setup_violated_endpoints':int(fol('Numbers of Setup Violated Endpoints')),'hold_violated_endpoints':int(fol('Numbers of Hold Violated Endpoints')),
       'worst_setup':worst('Setup Paths Table'),'worst_hold':worst('Hold Paths Table'),'worst_recovery':worst('Recovery Paths Table'),'worst_removal':worst('Removal Paths Table'),
       'negative_paths':{k:neg(k+' Paths Table') for k in ['Setup','Hold','Recovery','Removal']},
       'fmax_mhz':{n:fmax(n) for n in (['sys27','memory398','user100'] if vid.startswith('clk400x_') or vid in ('clk400','clk400_notap','sampleip','clk400_asyncsdc','clk400dp','sampleip_map','sampleip_map_t1','sampleip_map_t2','sampleip_map_t3','sampleip_map_t4') else re.findall(r'(sys27|memory\d+|user\d+)',' '.join(fm[:40])) if vid.startswith('nip_') else ['sys27','memory324','user81'])}},
     'logic':re.search(r'Logic\s+\|\s+(\d+/\d+)',rep).group(1),'registers':re.search(r'Register\s+\|\s+(\d+/\d+)',rep).group(1),
     'pin_audit':cst_audit(rep),'rtl_sha256':rv['files'],
     'sdc_lines_dropped':[l[:160] for l in rv.get('sdc_lines_dropped',[])],
     'archive':out.relative_to(root).as_posix()}
(root/'validation'/SUMMARY).write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({k:{kk:v.get(kk) for kk in ('fs_sha256','usercode','sta')} for k,v in summary['variants'].items() if k!='_ip'},indent=1)[:3000])
