"""Mock-bridge RTL tests for the NPU held-toggle arbiter; no hardware access."""
from pathlib import Path
import argparse,hashlib,json,os,random,shutil,subprocess,sys

ROOT=Path(__file__).resolve().parents[2]

PREFIX=r'''
`timescale 1ns/1ps
module tb_npu_ddr_arbiter;
 reg clk=0,reset_n=0;
 always #5 clk=~clk;
 reg m0_req_t=0,m0_cancel_t=0,m1_req_t=0,m1_cancel_t=0;
 reg[1:0]m0_h_op=0,m1_h_op=0;
 reg[31:0]m0_h_addr=0,m1_h_addr=0,m0_h_arg=0,m1_h_arg=0;
 reg[15:0]m0_h_beats=0,m1_h_beats=0;
 reg[23:0]m0_h_tag=0,m1_h_tag=0;
 wire m0_done_t,m1_done_t,req_t,cancel_t,active,owner,fault;
 wire[23:0]m0_r_tag,m1_r_tag,h_tag;
 wire[3:0]m0_r_status,m1_r_status;
 wire[31:0]m0_r_crc,m1_r_crc,h_addr,h_arg;
 wire[15:0]m0_r_beats,m1_r_beats,h_beats;
 wire[1:0]h_op;
 reg done_t=0;reg[23:0]r_tag=0;reg[3:0]r_status=0;
 reg[31:0]r_crc=0;reg[15:0]r_beats=0;
 reg old_req,old_cancel,d0,d1;
 integer launches=0,acks0=0,acks1=0,expected_launches=0,expected0=0,expected1=0;
 reg monitor_req=0,monitor_d0=0,monitor_d1=0;
 reg[105:0]held_metadata=0;
 wire[105:0]metadata={h_op,h_addr,h_beats,h_arg,h_tag};
 npu_ddr_arbiter dut(
  .clk(clk),.reset_n(reset_n),
  .m0_req_t(m0_req_t),.m0_cancel_t(m0_cancel_t),.m0_h_op(m0_h_op),.m0_h_addr(m0_h_addr),
  .m0_h_beats(m0_h_beats),.m0_h_arg(m0_h_arg),.m0_h_tag(m0_h_tag),
  .m0_done_t(m0_done_t),.m0_r_tag(m0_r_tag),.m0_r_status(m0_r_status),.m0_r_crc(m0_r_crc),.m0_r_beats(m0_r_beats),
  .m1_req_t(m1_req_t),.m1_cancel_t(m1_cancel_t),.m1_h_op(m1_h_op),.m1_h_addr(m1_h_addr),
  .m1_h_beats(m1_h_beats),.m1_h_arg(m1_h_arg),.m1_h_tag(m1_h_tag),
  .m1_done_t(m1_done_t),.m1_r_tag(m1_r_tag),.m1_r_status(m1_r_status),.m1_r_crc(m1_r_crc),.m1_r_beats(m1_r_beats),
  .req_t(req_t),.cancel_t(cancel_t),.h_op(h_op),.h_addr(h_addr),.h_beats(h_beats),.h_arg(h_arg),.h_tag(h_tag),
  .done_t(done_t),.r_tag(r_tag),.r_status(r_status),.r_crc(r_crc),.r_beats(r_beats),
  .active(active),.owner(owner),.fault(fault));
 always @(negedge clk)begin #1;
  if(!reset_n)begin monitor_req=req_t;monitor_d0=m0_done_t;monitor_d1=m1_done_t;held_metadata=metadata;end
  else begin
   if(req_t!==monitor_req)begin launches=launches+1;monitor_req=req_t;held_metadata=metadata;end
   else if(metadata!==held_metadata)$fatal(1,"merged metadata changed without a request toggle");
   if(m0_done_t!==monitor_d0)begin acks0=acks0+1;monitor_d0=m0_done_t;end
   if(m1_done_t!==monitor_d1)begin acks1=acks1+1;monitor_d1=m1_done_t;end
  end
 end
 task tick;begin @(posedge clk);#1;end endtask
 task idle;input integer n;integer j;begin for(j=0;j<n;j=j+1)tick();end endtask
 task reset_all;input q0,q1,dp;begin
  @(negedge clk);reset_n=0;m0_req_t=q0;m1_req_t=q1;m0_cancel_t=1;m1_cancel_t=1;done_t=dp;
  idle(4);@(negedge clk);reset_n=1;idle(7);
  if(active||fault||req_t!==0||cancel_t!==0||m0_done_t!==0||m1_done_t!==0)$fatal(1,"reset failed to adopt phases without replay");
 end endtask
 task issue;input integer who;input[1:0]op;input[31:0]addr;input[15:0]beats;input[31:0]arg;input[23:0]tag;begin
  @(negedge clk);
  if(who)begin m1_h_op=op;m1_h_addr=addr;m1_h_beats=beats;m1_h_arg=arg;m1_h_tag=tag;m1_req_t=~m1_req_t;end
  else begin m0_h_op=op;m0_h_addr=addr;m0_h_beats=beats;m0_h_arg=arg;m0_h_tag=tag;m0_req_t=~m0_req_t;end
 end endtask
 task granted;input integer who;input old_phase;input[1:0]op;input[31:0]addr;input[15:0]beats;input[31:0]arg;input[23:0]tag;integer n;begin
  n=0;while(req_t===old_phase && n<20)begin tick();n=n+1;end
  if(req_t!==~old_phase||!active||owner!==who[0]||fault)$fatal(1,"request grant/owner missing");
  if({h_op,h_addr,h_beats,h_arg,h_tag}!=={op,addr,beats,arg,tag})$fatal(1,"request bundle not latched from selected master");
  expected_launches=expected_launches+1;
 end endtask
 task finish;input integer who;input[23:0]tag;input[3:0]status;input[31:0]crc;input[15:0]beats;
  reg selected_done,other_done;reg[75:0]other_reply;integer n;begin
  selected_done=who?m1_done_t:m0_done_t;other_done=who?m0_done_t:m1_done_t;
  other_reply=who?{m0_r_tag,m0_r_status,m0_r_crc,m0_r_beats}:{m1_r_tag,m1_r_status,m1_r_crc,m1_r_beats};
  @(negedge clk);r_tag=tag;r_status=status;r_crc=crc;r_beats=beats;done_t=~done_t;
  n=0;while((who?m1_done_t:m0_done_t)===selected_done && n<20)begin tick();n=n+1;end
  if((who?m1_done_t:m0_done_t)!==~selected_done||fault)$fatal(1,"matching completion not delivered exactly once");
  if((who?{m1_r_tag,m1_r_status,m1_r_crc,m1_r_beats}:{m0_r_tag,m0_r_status,m0_r_crc,m0_r_beats})!=={tag,status,crc,beats})$fatal(1,"response bundle differs");
  if((who?m0_done_t:m1_done_t)!==other_done || (who?{m0_r_tag,m0_r_status,m0_r_crc,m0_r_beats}:{m1_r_tag,m1_r_status,m1_r_crc,m1_r_beats})!==other_reply)$fatal(1,"completion leaked to non-owner");
  if(who)expected1=expected1+1;else expected0=expected0+1;
 end endtask
 task cancel_edge;input integer who;begin @(negedge clk);if(who)m1_cancel_t=~m1_cancel_t;else m0_cancel_t=~m0_cancel_t;tick();end endtask
 initial begin
  reset_all(1,1,1); // Nonzero toggle phases do not become phantom commands/completions.
  old_req=req_t;issue(0,2,32'h100,3,32'h12345678,24'h101);granted(0,old_req,2,32'h100,3,32'h12345678,24'h101);
  issue(1,1,32'h200,4,32'h87654321,24'h202);idle(4);
  if(owner!==0 || req_t!==~old_req)$fatal(1,"pending second master switched active owner");
  old_cancel=cancel_t;cancel_edge(1);if(cancel_t!==old_cancel)$fatal(1,"inactive cancel forwarded");
  cancel_edge(0);if(cancel_t!==~old_cancel)$fatal(1,"active cancel not forwarded");old_cancel=cancel_t;
  cancel_edge(0);if(cancel_t!==old_cancel)$fatal(1,"duplicate cancel forwarded twice");
  // Metadata is latched, not a live mux of the source bundle.
  @(negedge clk);m0_h_addr=32'hdeadbeef;m1_h_arg=32'h87654321;idle(3);
  if(h_addr!==32'h100)$fatal(1,"source metadata altered merged held bundle");
  old_req=req_t;finish(0,24'h101,4'h9,32'hcafe1234,3);
  granted(1,old_req,1,32'h200,4,32'h87654321,24'h202);
  if(cancel_t!==old_cancel)$fatal(1,"old inactive cancel poisoned next owner");
  finish(1,24'h202,0,32'hbabe4321,4);idle(5);if(active||fault)$fatal(1,"completion retired incorrectly");
  // Both pending at once: round-robin tie preference after the prior owner.
  old_req=req_t;@(negedge clk);
  m0_h_op=0;m0_h_addr=32'h300;m0_h_beats=1;m0_h_arg=11;m0_h_tag=24'h303;m0_req_t=~m0_req_t;
  m1_h_op=3;m1_h_addr=32'h400;m1_h_beats=256;m1_h_arg=22;m1_h_tag=24'h404;m1_req_t=~m1_req_t;
  granted(0,old_req,0,32'h300,1,11,24'h303);old_req=req_t;finish(0,24'h303,0,31,1);
  granted(1,old_req,3,32'h400,256,22,24'h404);finish(1,24'h404,4'hf,32,0);idle(4);
  // Make master0 the last grant, then simultaneous requests prefer master1.
  old_req=req_t;issue(0,1,32'h500,2,33,24'h505);granted(0,old_req,1,32'h500,2,33,24'h505);finish(0,24'h505,0,34,2);idle(3);
  old_req=req_t;@(negedge clk);
  m0_h_op=2;m0_h_addr=32'h600;m0_h_beats=3;m0_h_arg=35;m0_h_tag=24'h606;m0_req_t=~m0_req_t;
  m1_h_op=1;m1_h_addr=32'h700;m1_h_beats=4;m1_h_arg=36;m1_h_tag=24'h707;m1_req_t=~m1_req_t;
  granted(1,old_req,1,32'h700,4,36,24'h707);old_req=req_t;finish(1,24'h707,0,37,4);
  granted(0,old_req,2,32'h600,3,35,24'h606);finish(0,24'h606,0,38,3);idle(4);
  // A cancel arriving on the same SYS edge as synchronized completion is late.
  old_req=req_t;issue(0,1,32'h800,1,0,24'h808);granted(0,old_req,1,32'h800,1,0,24'h808);
  old_cancel=cancel_t;d0=m0_done_t;d1=m1_done_t;
  @(negedge clk);r_tag=24'h808;r_status=0;r_crc=39;r_beats=1;done_t=~done_t;tick();tick();
  @(negedge clk);m0_cancel_t=~m0_cancel_t;tick();
  if(m0_done_t!==~d0||m1_done_t!==d1||cancel_t!==old_cancel||fault||active)$fatal(1,"late cancel/completion priority");expected0=expected0+1;idle(4);
  // Reset while busy and while the other master is pending: nothing is replayed.
  old_req=req_t;issue(1,2,32'h900,9,0,24'h909);granted(1,old_req,2,32'h900,9,0,24'h909);
  issue(0,1,32'ha00,10,0,24'ha0a);cancel_edge(1);
  reset_all(m0_req_t,m1_req_t,done_t);idle(12);if(active||fault)$fatal(1,"stale reset job replayed");
  // Request and cancel toggle together; both merged edges belong to that job.
  old_req=req_t;old_cancel=cancel_t;@(negedge clk);
  m0_h_op=1;m0_h_addr=32'hb00;m0_h_beats=2;m0_h_arg=0;m0_h_tag=24'hb0b;m0_req_t=~m0_req_t;m0_cancel_t=~m0_cancel_t;
  granted(0,old_req,1,32'hb00,2,0,24'hb0b);if(cancel_t!==~old_cancel)$fatal(1,"grant-time cancel missing");finish(0,24'hb0b,9,0,0);idle(4);
'''

SUFFIX=r'''
  // One reset edge coincides with nonblocking phase resets in both masters
  // and the common bridge. Post-reset adoption must suppress stale replay.
  reset_all(0,0,0);
  old_req=req_t;issue(0,1,32'he00,1,0,24'he0e);granted(0,old_req,1,32'he00,1,0,24'he0e);
  @(negedge clk);reset_n=0;
  @(posedge clk);m0_req_t<=0;m1_req_t<=0;m0_cancel_t<=0;m1_cancel_t<=0;done_t<=1;#1;
  @(negedge clk);reset_n=1;idle(10);
  if(active||fault||req_t!==0||cancel_t!==0||m0_done_t!==0||m1_done_t!==0)$fatal(1,"one-edge synchronous reset replayed stale phase");
  old_req=req_t;issue(1,1,32'he10,2,0,24'he1e);granted(1,old_req,1,32'he10,2,0,24'he1e);finish(1,24'he1e,0,41,2);idle(4);
  // A bad tag is quarantined; no fabricated completion reaches either master.
  old_req=req_t;issue(1,1,32'hf00,1,0,24'hbad001);granted(1,old_req,1,32'hf00,1,0,24'hbad001);
  d0=m0_done_t;d1=m1_done_t;old_req=req_t;old_cancel=cancel_t;
  @(negedge clk);r_tag=24'hbad002;r_status=0;r_crc=0;r_beats=1;done_t=~done_t;idle(6);
  if(!fault||!active||m0_done_t!==d0||m1_done_t!==d1)$fatal(1,"mismatched tag published or not quarantined");
  issue(0,1,32'h1000,1,0,24'hbad003);cancel_edge(1);idle(6);
  if(req_t!==old_req||cancel_t!==old_cancel||m0_done_t!==d0||m1_done_t!==d1)$fatal(1,"quarantine allowed later activity");
  reset_all(m0_req_t,m1_req_t,done_t);idle(8);
  // An idle unsolicited done toggle is also a correlation fault, not a response.
  d0=m0_done_t;d1=m1_done_t;old_req=req_t;@(negedge clk);done_t=~done_t;idle(6);
  if(!fault||!active||req_t!==old_req||m0_done_t!==d0||m1_done_t!==d1)$fatal(1,"idle done mispublished or not quarantined");
  reset_all(m0_req_t,m1_req_t,done_t);idle(8);
  old_req=req_t;issue(0,1,32'h2000,1,32'hffffffff,24'hffffff);granted(0,old_req,1,32'h2000,1,32'hffffffff,24'hffffff);finish(0,24'hffffff,0,32'h12345678,1);idle(6);
  if(active||fault||launches!=expected_launches||acks0!=expected0||acks1!=expected1)$fatal(1,"phantom/duplicate request or completion counts launches=%0d/%0d acks=%0d/%0d,%0d/%0d",launches,expected_launches,acks0,expected0,acks1,expected1);
  $display("PASS npu_ddr_arbiter random=200 launches=%0d acks0=%0d acks1=%0d; queue/fairness/cancel/reset/tag/idle-done",launches,acks0,acks1);$finish;
 end
 initial begin #10000000;$fatal(1,"global timeout");end
endmodule
'''

def bench():
    rng=random.Random(20261107);lines=[]
    for i in range(200):
        who=rng.randrange(2);op=rng.randrange(4);addr=rng.randrange(1<<23)*16;beats=rng.randrange(1,257);arg=rng.getrandbits(32);tag=0x100000+i;status=rng.randrange(16);crc=rng.getrandbits(32)
        lines.append(f"old_req=req_t;issue({who},2'd{op},32'h{addr:08x},16'd{beats},32'h{arg:08x},24'h{tag:06x});granted({who},old_req,2'd{op},32'h{addr:08x},16'd{beats},32'h{arg:08x},24'h{tag:06x});")
        if rng.randrange(2):lines.append(f"old_cancel=cancel_t;cancel_edge({1-who});if(cancel_t!==old_cancel)$fatal(1,\"random inactive cancel leaked\");")
        if rng.randrange(3)==0:
            lines.append(f"old_cancel=cancel_t;cancel_edge({who});if(cancel_t!==~old_cancel)$fatal(1,\"random selected cancel missing\");")
            if rng.randrange(2):lines.append(f"old_cancel=cancel_t;cancel_edge({who});if(cancel_t!==old_cancel)$fatal(1,\"random duplicate cancel forwarded\");")
        lines.append(f"idle({rng.randrange(1,8)});finish({who},24'h{tag:06x},4'd{status},32'h{crc:08x},16'd{beats});idle({rng.randrange(1,6)});if(active||fault)$fatal(1,\"random transaction did not retire\");")
    return PREFIX+'\n'.join(lines)+'\n'+SUFFIX

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--iverilog',default='iverilog');p.add_argument('--vvp',default='vvp');p.add_argument('--output',type=Path,default=ROOT/'build/npu-ddr-arbiter-test');a=p.parse_args()
    compiler=shutil.which(a.iverilog);runtime=shutil.which(a.vvp)
    if not compiler or not runtime:p.error('Existing Icarus and vvp are required; no installation attempted')
    a.output.mkdir(parents=True,exist_ok=True);tb=a.output/'tb_npu_ddr_arbiter.v';tb.write_text(bench());binary=a.output/'arbiter.vvp';env=dict(os.environ);env['PATH']=str(Path(compiler).parent)+os.pathsep+env.get('PATH','')
    source=ROOT/'npu/rtl/npu_ddr_arbiter.v';report={'passed':False,'device_access':'none','random_transactions':200,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'test_sha256':hashlib.sha256(tb.read_bytes()).hexdigest(),'commands':[]};logs=[]
    try:
        for command in [[compiler,'-g2012','-Wall','-s','tb_npu_ddr_arbiter','-o',str(binary),str(source),str(tb)],[runtime,str(binary)]]:
            report['commands'].append(command);r=subprocess.run(command,capture_output=True,text=True,env=env,timeout=120);logs.append(r.stdout+r.stderr)
            if r.returncode:raise RuntimeError(f'Command exited {r.returncode}: '+logs[-1])
        report['passed']=True;report['output']=logs[-1];print(logs[-1],flush=True)
    except Exception as error:report['error']=str(error);print(str(error),file=sys.stderr)
    (a.output/'run.log').write_text('\n'.join(logs));(a.output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    if not report['passed']:raise SystemExit(1)

if __name__=='__main__':main()
