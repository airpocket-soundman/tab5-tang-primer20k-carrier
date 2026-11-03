"""Controlled pack-only bus_clk HYSTERESIS=HIGH experiment. Never programs hardware."""
import argparse
import hashlib
import importlib.metadata
import importlib.resources
import json
from pathlib import Path
import re
import subprocess
import sys

BASE_SHA='5b93ac88ffd9d45ad959e19da50e8af433dd8ca3fbc8ccb8f4e80ff1a1c391cb'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def qualify(pnr,reference,baseline,candidate,modified):
    from apycula import bslib,chipdb,bitmatrix,attrids,gowin_pack
    if sys.flags.optimize:raise ValueError('Run without -O: bslib frame CRC assertions must execute')
    if sha(reference)!=BASE_SHA or baseline.read_bytes()!=reference.read_bytes():
        raise ValueError('Baseline repack does not match frozen5b93 bytes')
    original=json.loads(pnr.read_text());changed=json.loads(modified.read_text())
    name='platform.bus_clk_IBUF_O';cell=changed['modules']['top']['cells'][name]
    attribute='&HYSTERESIS=HIGH'
    if cell['attributes'].pop(attribute,None)!='00000000000000000000000000000001':raise ValueError('Missing exact HIGH attribute')
    if changed!=original:raise ValueError('Unexpected placement/routing/net/parameter/attribute changes')
    c=original['modules']['top']['cells'][name]
    if c['type']!='IBUF':raise ValueError('Expected ordinary IBUF')
    bel=c['attributes']['NEXTPNR_BEL'];m=re.fullmatch(r'X(\d+)Y(\d+)/IOB([AB])',bel)
    col,row,index=int(m[1]),int(m[2]),m[3]
    db_path=Path(str(importlib.resources.files('apycula').joinpath('GW2A-18.msgpack.xz')))
    db=chipdb.load_chipdb(db_path);tile=db[row,col]
    attrs=gowin_pack._init_io_attrs['IBUF'].copy()
    for key in c['attributes']:
        if key.startswith('&') and '=' in key:
            k,v=key[1:].split('=',1);attrs[gowin_pack.refine_io_attrs(k)]=v
    if attrs.get('IO_TYPE')!='LVCMOS33':raise ValueError('Expected3.3V input')
    attrs['BANK_VCCIO']='3.3';sets={}
    for mode in ('NONE','HIGH'):
        features=set()
        for k,v in dict(attrs,HYSTERESIS=mode).items():
            chipdb.add_attr_val(db,'IOB',features,attrids.iob_attrids[k],attrids.iob_attrvals[v])
        sets[mode]=set(chipdb.get_longval_fuses(db,tile.ttyp,features,'IOB'+index))
    local=sorted(sets['NONE']^sets['HIGH'])
    y=sum(db[r,0].height for r in range(row));x=sum(db[row,i].width for i in range(col))
    expected=sorted((y+r,x+c)for r,c in local)
    a,ha,fa,ea=bslib.read_bitstream(str(baseline));b,hb,fb,eb=bslib.read_bitstream(str(candidate))
    if len(a)!=len(b) or any(len(x)!=len(y)for x,y in zip(a,b)):raise ValueError('Config shape changed')
    diff=[(r,c,int(a[r][c]),int(b[r][c]))for r in range(len(a))for c in range(len(a[r]))if a[r][c]!=b[r][c]]
    if len(local)!=2 or [(r,c)for r,c,_,_ in diff]!=expected or any(old!=0 or new!=1 for _,_,old,new in diff):
        raise ValueError('Configuration changes exceed the two target input-pad fuses')
    if ha!=hb or ea!=eb or len(fa)!=len(fb):raise ValueError('Unexpected header/extra-slot change')
    checks=[]
    for grid,footer in ((a,fa),(b,fb)):
        packed=bitmatrix.packbits(bitmatrix.fliplr(grid[:db.height]))
        checksum=int(bitmatrix.bsum(packed[0::2])*256+bitmatrix.bsum(packed[1::2]))&65535
        if footer[1]!=bytes.fromhex(f'{0x0a<<56|checksum:016x}'):raise ValueError('Unexpected configuration checksum footer')
        checks.append(checksum)
    if any(v!=w for i,(v,w)in enumerate(zip(fa,fb))if i!=1):raise ValueError('Unexpected footer change')
    sources=[Path(gowin_pack.__file__),Path(bslib.__file__),Path(chipdb.__file__),Path(attrids.__file__),db_path]
    return {'qualified':True,'baseline_repack_byte_equal':True,'hardware_access':False,
        'scope':'Pack only; exactly one copied IBUF attribute, no synthesis/place/route/RTL/CST/pin/command changes.',
        'cell':name,'bel':bel,'bank':chipdb.loc2bank(db,row,col),'tile_type':tile.ttyp,
        'attribute':attribute,'tile_origin_global':[y,x],'fuses_local':local,'configuration_diff_global':diff,
        'all_frame_crcs_verified_by_bslib':True,'headers_and_extra_slots_equal':True,
        'only_footer_change':'0x0A checksum independently recomputed from regular grid; format frame CRCs validated',
        'configuration_checksums_hex':[f'{v:04X}'for v in checks],
        'apycula_version':importlib.metadata.version('apycula'),
        'files':{str(path):{'sha256':sha(path),'bytes':path.stat().st_size}for path in [pnr,reference,baseline,modified,candidate]},
        'packer_source_sha256':{str(path):sha(path)for path in sources}}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pnr',type=Path,required=True)
    p.add_argument('--reference-fs',type=Path,required=True)
    p.add_argument('--pack',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--verify-existing',action='store_true',help='Validate already packed files; normal mode performs both packs')
    a=p.parse_args();out=a.output_dir.resolve();out.mkdir(parents=True,exist_ok=True)
    baseline=out/'baseline-repack.fs';modified=out/'high.pnr.json';candidate=out/'hysteresis-high.fs'
    commands=[]
    def pack(source,destination,label):
        command=[str(a.pack),'-d','GW2A-18','--sspi_as_gpio',str(source),'-o',str(destination)]
        if not a.verify_existing:
            r=subprocess.run(command,capture_output=True,text=True,timeout=180)
            (out/(label+'.log')).write_text(r.stdout+r.stderr,encoding='utf-8')
            if r.returncode:raise RuntimeError(label+' pack failed: '+r.stderr)
        commands.append({'command':command,'execution':'validated_existing' if a.verify_existing else 'executed','exit_code':None if a.verify_existing else 0})
    pack(a.pnr,baseline,'baseline')
    if baseline.read_bytes()!=a.reference_fs.read_bytes() or sha(a.reference_fs)!=BASE_SHA:
        raise ValueError('Baseline mismatch; stop before experimental pack')
    if not a.verify_existing:
        data=json.loads(a.pnr.read_text());cell=data['modules']['top']['cells']['platform.bus_clk_IBUF_O']
        if any(k.startswith('&HYSTERESIS=')for k in cell['attributes']):raise ValueError('Baseline already has a hysteresis override')
        cell['attributes']['&HYSTERESIS=HIGH']='00000000000000000000000000000001'
        modified.write_text(json.dumps(data,separators=(',',':')),encoding='utf-8')
    pack(modified,candidate,'high')
    report=qualify(a.pnr,a.reference_fs,baseline,candidate,modified)
    report.update(commands=commands,tool_sha256=sha(Path(__file__)),physical_validation='Not performed by this tool')
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'qualified':True,'candidate_sha256':sha(candidate),'candidate':str(candidate),'manifest':str(out/'manifest.json')}))


if __name__=='__main__':main()
