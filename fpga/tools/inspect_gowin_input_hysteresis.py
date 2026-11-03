"""Read-only GW2A IBUF attribute/database inspection; never writes a bitstream."""
import argparse
import hashlib
import importlib.metadata
import importlib.resources
import json
from pathlib import Path
import re


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pnr',type=Path,required=True)
    p.add_argument('--baseline-fs',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    from apycula import attrids,chipdb,gowin_pack
    sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    if sha(a.baseline_fs)!='5b93ac88ffd9d45ad959e19da50e8af433dd8ca3fbc8ccb8f4e80ff1a1c391cb':
        raise ValueError('Expected frozen5b93 baseline; do not silently inspect a different image')
    netlist=json.loads(a.pnr.read_text())
    cells=netlist['modules']['top']['cells']
    matches=[(n,c)for n,c in cells.items()if 'bus_clk' in n and c['type']=='IBUF']
    if len(matches)!=1:raise ValueError('bus_clk IBUF not unique')
    name,cell=matches[0];bel=cell['attributes']['NEXTPNR_BEL']
    match=re.fullmatch(r'X(\d+)Y(\d+)/IOB([AB])',bel)
    if not match:raise ValueError('Unexpected IBUF BEL')
    col,row,index=int(match[1]),int(match[2]),match[3]
    db_path=Path(str(importlib.resources.files('apycula').joinpath('GW2A-18.msgpack.xz')))
    db=chipdb.load_chipdb(db_path);tile=db[row,col]
    attrs=gowin_pack._init_io_attrs['IBUF'].copy()
    for key in cell['attributes']:
        if key.startswith('&') and '=' in key:
            key,value=key[1:].split('=',1);attrs[gowin_pack.refine_io_attrs(key)]=value
    if attrs['IO_TYPE']!='LVCMOS33':raise ValueError('Expected3.3V LVCMOS33 baseline')
    attrs['BANK_VCCIO']='3.3';modes={};points=[]
    for mode in ('NONE','L2H','H2L','HIGH'):
        setting=dict(attrs,HYSTERESIS=mode);feature_ids=set()
        for key,value in setting.items():
            chipdb.add_attr_val(db,'IOB',feature_ids,attrids.iob_attrids[key],attrids.iob_attrvals[value])
        bits=set(chipdb.get_longval_fuses(db,tile.ttyp,feature_ids,'IOB'+index))
        modes[mode]=bits
        points.append({'mode':mode,'fuse_count':len(bits),
                       'xor_vs_none_tile_local':sorted(bits^modes['NONE'])})
    report={'scope':'Read-only installed packer helper/database evidence; no PNR, repack, source/CST modification or hardware operation.',
            'hardware_access':False,'generated_bitstream':False,'apycula_version':importlib.metadata.version('apycula'),
            'baseline_fs_sha256':sha(a.baseline_fs),'pnr_sha256':sha(a.pnr),'cell':name,'bel':bel,
            'db_row_col_zero_based':[row,col],'bank':chipdb.loc2bank(db,row,col),'tile_type':tile.ttyp,
            'baseline_ibuf_attrs':attrs,'modes':points,
            'sources_sha256':{str(path):sha(path)for path in [Path(gowin_pack.__file__),Path(attrids.__file__),Path(chipdb.__file__),db_path]},
            'cst_option_scope':'gowin_pack -s is OUTPUT CST (open w), not an input constraint file',
            'proposed_control':'Baseline repack must match5b93; copy routed JSON and alter exactly one bus_clk &HYSTERESIS attribute; preserve all cells/connectivity/placement/routing; verify target fuse-only delta plus format checksums before hardware.'}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'modes':points,'bank':report['bank'],'bel':bel,'output':str(a.output)}))


if __name__=='__main__':main()
