"""Independent fixed-point fractal oracle against complete pin-level responses."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from reference.triangle_tile import TriangleTile, VIVID_PALETTE
from reference.link_protocol import request


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--iverilog',default='iverilog')
    p.add_argument('--vvp',default='vvp')
    p.add_argument('--vendor-primitive-lib',type=Path)
    p.add_argument('--pipeline-coverage',action='store_true')
    args=p.parse_args()
    if not shutil.which(args.iverilog) or not shutil.which(args.vvp): p.error('existing Icarus/vvp required')
    model,vectors=TriangleTile(),[]
    def exchange(op,a=0,b=0):
        q=request(op,len(vectors)&255,a,b)
        r=model.exchange(q); vectors.append((q,r)); return r
    exchange(0x30)
    exchange(0x39);exchange(0x3a) # no completed DRAW yet
    exchange(0x38) # missing configuration
    for limit,mode in [(0,0),(129,0),(128,4),(255,255)]: exchange(0x37,limit,mode)
    def configure(params):
        for i,value in enumerate(params): exchange(0x31+i,value&255,(value>>8)&255)
    # Main set, exterior, Julia, high iteration boundary, negative floor rounding,
    # and immediate-escape Julia exercise distinct iteration and palette ranges.
    views=[(-10035,-4096,280,264,-2949,819,64),
           (-4096,-2048,132,132,-2949,819,0x0140),
           (-3200,-1200,32,32,-2949,819,128),
           (-32768,-32768,1,1,32767,-32768,0x0180),
           (-1024,-1024,64,64,-2579,-693,0x0180),
           (0,0,1,1,0,0,128)]
    views += [(*v[:6],v[6]|0x0200) for v in views]
    pixel_count=0
    for params in views:
        configure(params); exchange(0x38)
        exchange(0x39);exchange(0x3a);exchange(0x39);exchange(0x3a)
        exchange(0x39,1,0);exchange(0x3a,0,1)
        for plane in (0,1):
            for row in range(32):
                exchange(0x2f,row,plane); pixel_count+=32
    # Invalid extent/step/config request must preserve the prior successful tile.
    for index,value in [(2,0),(2,32768),(2,32767),(0,32767)]:
        configure(views[0]); exchange(0x31+index,value&255,value>>8); exchange(0x38)
    configure(views[0]); exchange(0x38,1,0); exchange(0x38)
    exchange(0x2f,0,0)
    q=bytearray(request(0x38,0,0,0));q[6]^=1
    vectors.append((q,model.exchange(q)))
    with tempfile.TemporaryDirectory(prefix='fractal-tile-') as td:
        td=Path(td); vf=td/'vectors.txt';exe=td/'test.vvp';palette_file=td/'palette.hex'
        palette_file.write_text(''.join(f'{v:04x}\n' for v in VIVID_PALETTE),encoding='ascii')
        vf.write_text(''.join(str(len(r))+' '+' '.join(f'{b:02x}' for b in bytes(q)+r)+'\n' for q,r in vectors),encoding='ascii')
        sources=['link/rtl/triangle_batch.v','link/rtl/link_bringup.v','gfx/rtl/gfx_bench.v','gfx/rtl/triangle_tile.v','gfx/rtl/triangle_fragment.v',
                 'gfx/rtl/triangle_coverage.v','gfx/rtl/triangle_depth.v',
                 'platform/dock/tab5_dock_top.v','gfx/tests/tb_fractal_tile.v']
        paths=[str(ROOT/s)for s in sources]
        if args.pipeline_coverage:paths[sources.index('gfx/rtl/triangle_coverage.v')]=str(ROOT/'gfx/rtl/triangle_coverage_pipeline.v')
        if args.vendor_primitive_lib:
            paths[2]=str(ROOT/'gfx/rtl/triangle_tile_vendor.v')
            bench=td/'vendor_bench.v';text=(ROOT/sources[-1]).read_text();text=text.replace('    reg clk=0,',"    GSR GSR(1'b1);\n    reg clk=0,",1);bench.write_text(text)
            paths[-1]=str(bench);paths +=[str(ROOT/'gfx/rtl/tile_dpram_vendor.v'),str(args.vendor_primitive_lib)]
        paths +=[str(ROOT/'link/rtl/triangle_batch.v')]
        subprocess.run([args.iverilog,'-g2012','-Wall','-s','tb_fractal_tile','-o',str(exe),*paths],check=True)
        subprocess.run([args.vvp,str(exe),'+vectors='+str(vf),'+palette='+str(palette_file)],check=True,timeout=180)
    print(f'PASS fractal {len(vectors)} oracle transactions, {pixel_count} color/depth pixels, 12 legacy/vivid viewports with exact stable DRAW cycles; no hardware access')
if __name__=='__main__':main()
