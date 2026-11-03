"""Conditioned-clock control regression, optional public vendor RAM model."""
import argparse,hashlib,json,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--iverilog',required=True);p.add_argument('--vvp',required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--vendor-primitive-lib',type=Path);p.add_argument('--pipeline-coverage',action='store_true');p.add_argument('--metadata-cdc-assertions',action='store_true');a=p.parse_args()
    files=['link/rtl/reply_clock_filter.v','link/rtl/link_reply_raw.v','link/rtl/link_bringup_filtered.v','gfx/rtl/gfx_bench.v','gfx/rtl/triangle_tile.v','gfx/rtl/triangle_fragment.v','gfx/rtl/triangle_coverage.v','gfx/rtl/triangle_depth.v','link/tests/tb_filteredreply_control.v']
    if a.pipeline_coverage:files[files.index('gfx/rtl/triangle_coverage.v')]='gfx/rtl/triangle_coverage_pipeline.v'
    if a.vendor_primitive_lib:files[files.index('gfx/rtl/triangle_tile.v')]='gfx/rtl/triangle_tile_vendor.v';files+=['gfx/rtl/tile_dpram_vendor.v']
    files +=['link/rtl/triangle_batch.v']
    frozen={f:(ROOT/f).read_bytes()for f in files}
    if a.metadata_cdc_assertions:
        key='link/tests/tb_filteredreply_control.v';text=frozen[key].decode()
        extra=r'''
    time metadata_changed_at=0;
    integer cdc_prefix_edges=0,cdc_functional_edges=0;
    always @(dut.fast_metadata) metadata_changed_at=$time;
    always @(posedge dut.fast_offer) begin
        if(reset_n && arm && $time-metadata_changed_at<18000)
            $fatal(1,"metadata not committed one SYS cycle before offer");
    end
    always @(posedge dut.clean_reply_clk) begin
        if(reset_n && arm && dut.fast_offer && dir && !dut.raw_done) begin
            if(dut.fast_serializer.serializer.index<8) begin
                if(data_o!==8'hc3)$fatal(1,"prefix functionally depends on unsettled metadata");
                cdc_prefix_edges=cdc_prefix_edges+1;
            end
            if(dut.fast_serializer.serializer.index<16) begin
                if(dut.fast_serializer.serializer.payload || dut.fast_serializer.serializer.last_index<15)
                    $fatal(1,"metadata altered early prefix control");
            end
            if(dut.fast_serializer.serializer.index>=2) begin
                if(dut.fast_serializer.serializer.metadata_bus!==dut.fast_metadata)
                    $fatal(1,"stage1 not coherent before first metadata-dependent RAM latch");
                cdc_functional_edges=cdc_functional_edges+1;
            end
        end
    end
    final begin
        if(cdc_prefix_edges<100 || cdc_functional_edges<1000)$fatal(1,"CDC assertions vacuous");
        $display("PASS CDC prefix_edges=%0d settled_stage1_edges=%0d",cdc_prefix_edges,cdc_functional_edges);
    end
'''
        frozen[key]=text.replace('    initial begin #10000000000;',extra+'\n    initial begin #10000000000;').encode()
    if a.vendor_primitive_lib:
        key='link/tests/tb_filteredreply_control.v';text=frozen[key].decode();text=text.replace('    reg filter_clk=0;',"    GSR GSR(1'b1);\n    reg filter_clk=0;",1);frozen[key]=text.encode();frozen['installed_prim_sim.v']=a.vendor_primitive_lib.read_bytes()
    with tempfile.TemporaryDirectory(prefix='filter-control-')as td:
        paths=[]
        for name,data in frozen.items():
            path=Path(td)/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data);paths.append(path)
        exe=Path(td)/'test.vvp';subprocess.run([a.iverilog,'-g2012','-s','tb_fastreply_control','-o',str(exe),*map(str,paths)],check=True)
        r=subprocess.run([a.vvp,str(exe)],check=True,text=True,capture_output=True,timeout=180)
    d=dict(hardware_access=False,passed=True,vendor_memory=bool(a.vendor_primitive_lib),coverage_pipeline=a.pipeline_coverage,metadata_cdc_assertions=a.metadata_cdc_assertions,
           observed_stdout=r.stdout,source_snapshot_sha256={f:hashlib.sha256(data).hexdigest()for f,data in frozen.items()})
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(d,indent=2)+'\n');print(r.stdout)
if __name__=='__main__':main()
