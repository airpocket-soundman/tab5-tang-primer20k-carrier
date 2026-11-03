"""Verify only an identity expression changes serializer offer input."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
INSERT='''        // Physical hold repair on this one serializer input only. The original
        // fast_offer still owns immediate OE/READY kill and SYS lifecycle.
        (* keep = "true" *) wire serializer_offer;
        (* keep = "true" *) LUT1 #(.INIT(2'h2)) offer_hold_buffer(.F(serializer_offer),.I0(fast_offer));
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--vo',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 path=ROOT/'link/rtl/link_bringup_filtered.v';current=path.read_text();baseline=subprocess.check_output(['git','show','43137e7:fpga/link/rtl/link_bringup_filtered.v'],cwd=ROOT.parent).decode().replace('\r\n','\n')
 assert current.count(INSERT)==1
 reduced=current.replace(INSERT,'').replace('serializer(clean_reply_clk,reset_n,arm,dir,serializer_offer,fast_metadata,','serializer(clean_reply_clk,reset_n,arm,dir,fast_offer,fast_metadata,')
 assert reduced==baseline,'additional behavioral change'
 # Official LUT1 INIT[0] at I0=0, INIT[1] at I0=1.
 assert [((2>>i)&1) for i in (0,1)]==[0,1]
 vo=a.vo.read_text();preserved=bool(re.search(r'LUT1\s+[^\s]+offer_hold_buffer',vo))
 d=dict(source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),baseline_commit='43137e7',only_change_identity_on_serializer_offer=True,truth_table=[[0,0],[1,1]],original_immediate_oe_ready_and_metadata_lifecycle_unchanged=True,mapped_independent_identity_lut=preserved,interpretation='Identity-equivalent source and routing-closed candidate; no claim that an independent buffer caused delay',vo_sha256=hashlib.sha256(a.vo.read_bytes()).hexdigest(),limitations=['Source identity plus compiler mapping and regression tests; not full-netlist formal equivalence','External capture phase and physical maximum remain independent'])
 a.output.write_text(json.dumps(d,indent=2)+'\n');print(json.dumps(d))
if __name__=='__main__':main()
