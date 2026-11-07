"""Healthy idle vs in-flight timeout with real SYS endpoints and idle loaders."""
from pathlib import Path
import argparse,subprocess,os,json,hashlib,shutil,sys
ROOT=Path(__file__).resolve().parents[2]
TB=r'''
`timescale 1ns/1ps
module tb;
reg clk=0;always #5 clk=~clk;
reg reset_n=0,arm=1,bus_clk=0,dir=0;reg[7:0]data_i=0;
wire baseline_abort,guard_abort,baseline_busy,guard_busy,baseline_error,guard_error;
wire[3:0]baseline_code,guard_code;reg fake_busy=0,fake_arbiter=0;
wire boe,goe,br,gr;wire[7:0]bd,gd;wire bc,gc;
reg [7:0] bytes[0:7];integer ba=0,ga=0,i,t;reg[15:0]crc;
npu_ddr_sys #(.TIMEOUT(32),.REQUEST_DATA_PIPELINE(1)) baseline(
 .clk(clk),.reset_n(reset_n),.arm(arm),.bus_clk(bus_clk),.dir(dir),.data_i(data_i),.data_o(bd),.data_oe(boe),.ready(br),
 .memory_ready(1'b1),.generation(16'd0),.arbiter_fault(1'b0),.arbiter_active(fake_arbiter),.conv_abort(baseline_abort),
 .conv_start_ready(1'b1),.conv_busy(baseline_busy|fake_busy),.conv_done(1'b0),.conv_error(baseline_error),.conv_quarantined(1'b0),.conv_error_code(baseline_code),
 .kernel_cycles(32'd0),.ddr_wait_cycles(32'd0),.total_cycles(32'd0),.cancel_t(bc),.done_t(1'b0),.r_tag(24'd0),.r_status(4'd0),.r_beats(16'd0),.r_data(128'd0));
npu_ddr_sys_idle_guard #(.TIMEOUT(32),.REQUEST_DATA_PIPELINE(1)) guard(
 .clk(clk),.reset_n(reset_n),.arm(arm),.bus_clk(bus_clk),.dir(dir),.data_i(data_i),.data_o(gd),.data_oe(goe),.ready(gr),
 .memory_ready(1'b1),.generation(16'd0),.arbiter_fault(1'b0),.arbiter_active(fake_arbiter),.conv_abort(guard_abort),
 .conv_start_ready(1'b1),.conv_busy(guard_busy|fake_busy),.conv_done(1'b0),.conv_error(guard_error),.conv_quarantined(1'b0),.conv_error_code(guard_code),
 .kernel_cycles(32'd0),.ddr_wait_cycles(32'd0),.total_cycles(32'd0),.cancel_t(gc),.done_t(1'b0),.r_tag(24'd0),.r_status(4'd0),.r_beats(16'd0),.r_data(128'd0));
npu_ddr_tile_loader_8oc base_loader(.clk(clk),.reset_n(reset_n),.memory_ready(1'b1),.start(1'b0),.abort(baseline_abort),.clear(1'b0),.busy(baseline_busy),.error(baseline_error),.error_code(baseline_code),.done_t(1'b0));
npu_ddr_tile_loader_8oc guard_loader(.clk(clk),.reset_n(reset_n),.memory_ready(1'b1),.start(1'b0),.abort(guard_abort),.clear(1'b0),.busy(guard_busy),.error(guard_error),.error_code(guard_code),.done_t(1'b0));
always @(posedge clk)begin if(reset_n)begin if(baseline_abort)ba=ba+1;if(guard_abort)ga=ga+1;end end
task cycle;begin @(posedge clk);#1;end endtask
task reset_all;begin @(negedge clk);reset_n=0;fake_busy=0;fake_arbiter=0;bus_clk=0;dir=0;repeat(3)cycle;@(negedge clk);reset_n=1;ba=0;ga=0;end endtask
task send;input[7:0]b;begin @(negedge clk);data_i=b;repeat(3)cycle;@(negedge clk);bus_clk=1;repeat(4)cycle;@(negedge clk);bus_clk=0;repeat(3)cycle;end endtask
function[15:0]crcbyte;input[15:0]c;input[7:0]b;reg[15:0]v;integer j;begin v=c^{b,8'd0};for(j=0;j<8;j=j+1)v=v[15]?(v<<1)^16'h1021:v<<1;crcbyte=v;end endfunction
initial begin
 reset_all;repeat(160)cycle;
 if(ba<3||!baseline_error||baseline_code!=8)$fatal(1,"baseline idle abort not reproduced");
 if(ga||guard_error||guard_loader.state!=0)$fatal(1,"healthy idle corrupted");
 // Timeout counter already expired + incoming first byte must still be parsed.
 reset_all;force guard.idle=31;fork send(8'ha5);begin wait(guard.index==1);#1;release guard.idle;guard.idle=0;end join cycle;
 if(guard.index!=1||ga)$fatal(1,"first byte lost at expiry");
 repeat(48)cycle;if(ga!=1||guard.index!=0||!guard_error||guard_code!=8)$fatal(1,"partial RX timeout absent");
 reset_all;send(8'ha5);send(8'h71);send(8'h03);repeat(48)cycle;if(ga!=1||guard.index!=0)$fatal(1,"partial packet guard");
 reset_all;fake_busy=1;repeat(48)cycle;if(!ga||!guard_error)$fatal(1,"active conv timeout disabled");
 reset_all;fake_arbiter=1;repeat(48)cycle;if(!ga||gc==0)$fatal(1,"active arbiter cancel disabled");
 reset_all;@(negedge clk);guard.state=6;repeat(48)cycle;if(!ga||gc==0)$fatal(1,"MEMWAIT timeout disabled");
 reset_all;@(negedge clk);guard.state=11;repeat(48)cycle;if(!ga)$fatal(1,"CONVWAIT timeout disabled");
 // Valid CAPS response left unread must expire, not become healthy idle.
 reset_all;bytes[0]=8'ha5;bytes[1]=8'h50;bytes[2]=7;bytes[3]=2;bytes[4]=0;bytes[5]=0;crc=16'hffff;
 for(i=0;i<6;i=i+1)crc=crcbyte(crc,bytes[i]);bytes[6]=crc[7:0];bytes[7]=crc[15:8];
 for(i=0;i<8;i=i+1)send(bytes[i]);if(!gr)$fatal(1,"CAPS missing response");repeat(48)cycle;if(ga!=1||gr||goe)$fatal(1,"response timeout absent");
 // ARM drops OE and both endpoint/loader are reset by integration, not retried.
 reset_all;repeat(96)cycle;@(negedge clk);arm=0;cycle;if(goe||gr)$fatal(1,"ARM OE");
 $display("PASS idle guard: legacyfault8 reproduced;160cyclehealthyidle survives;expiredfirstbyte parsed;partial/CONV/arbiter/RESPtimeouts preserved;ARM OE");$finish;
end
endmodule
'''
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ROOT/'build/npu-ddr-idle-guard');a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True);(out/'tb.v').write_text(TB)
 names=['npu/rtl/npu_ddr_sys.v','npu/rtl/npu_ddr_sys_idle_guard.v','npu/rtl/npu_ddr_tile_loader_8oc.v','npu/rtl/conv_tile_engine_8oc.v'];tool=Path('D:/GitHub/tab5-tang-primer20k-carrier/fpga/build/windows-tools/oss-cad-suite/bin');env=os.environ.copy();env['PATH']=str(tool)+os.pathsep+env['PATH'];commands=[]
 for cmd in [[str(tool/'iverilog.exe'),'-g2012','-s','tb','-o',str(out/'test.vvp'),*[str(ROOT/n) for n in names],str(out/'tb.v')],[str(tool/'vvp.exe'),str(out/'test.vvp')]]:
  r=subprocess.run(cmd,capture_output=True,text=True,env=env);commands.append({'command':cmd,'returncode':r.returncode,'output':r.stdout+r.stderr});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print(r.stdout+r.stderr);assert r.returncode==0
 (out/'result.json').write_text(json.dumps({'passed':True,'hardware_access':False,'source_sha256':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}},indent=2)+'\n')
if __name__=='__main__':main()
