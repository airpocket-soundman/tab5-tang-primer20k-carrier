`timescale 1ns/1ps
module tb_mem_bist;
parameter PAIRED=0;
parameter PIPE=0;
reg clk=0; always #5 clk=~clk;
reg rst=0,cal=1,start=0,cancel=0;
reg [31:0] base=0,count=17,seed=32'h1234abcd,job=1;
wire[175:0] debug;wire busy,done,fault;wire[7:0] error;wire[2:0] phase,cmd;
wire[31:0] verified,errors,first,accepted;wire[127:0] expected,actual,wd;
wire[63:0] cycles;wire ce,we,wend;wire[26:0] addr;wire[15:0] mask;
reg cr=0,wr=0,rv=0,re=1;reg[127:0] rd=0;
mem_bist #(.TIMEOUT_CYCLES(60),.TOTAL_TIMEOUT_CYCLES(50000),.PAIRED_WRITE(PAIRED),.CALIBRATION_SETTLE_CYCLES(4),.PIPELINE(PIPE)) dut(
clk,rst,cal,start,cancel,base,count,seed,job,busy,done,fault,error,phase,
verified,errors,first,accepted,expected,actual,cycles,cmd,ce,addr,cr,wd,we,wend,mask,wr,rd,rv,re,debug);
reg deadline_start=0;wire deadline_done;wire[7:0] deadline_error;
mem_bist #(.TIMEOUT_CYCLES(100),.TOTAL_TIMEOUT_CYCLES(5),.CALIBRATION_SETTLE_CYCLES(0),.PIPELINE(PIPE)) deadline_dut(
.clk(clk),.reset_n(rst),.calibrated(1'b1),.start(deadline_start),.cancel(1'b0),
.base_byte(32'b0),.beat_count(32'd1),.seed(32'b0),.job_id(32'd9),
.app_cmd_ready(1'b0),.app_write_ready(1'b0),.app_read_data(128'b0),.app_read_valid(1'b0),.app_read_end(1'b0),
.done(deadline_done),.error_code(deadline_error));
reg [127:0] memory[0:63];
reg pending_cmd=0,pending_data=0,pending_read=0;
reg[26:0] saved_addr;reg[127:0] saved_data;reg[15:0] saved_mask;
integer tick=0,delay_read=0,writes=0,reads=0,b,slot;
integer mode=0,checks=0;
reg corrupt=0;
integer cal_run=0;wire settled_seen=cal_run>=4;
// Independent count of clocks since calibration rose (reset by rst/cal low).
always @(posedge clk)begin if(!rst||!cal)cal_run<=0;else if(cal_run<4)cal_run<=cal_run+1;end
reg[175:0] saved_debug;
reg[127:0] golden;reg[31:0] ga,g0,g1,g2,g3;integer gi;
// Independent controller shim: command and data channels stall differently.
// Addresses are decoded from rank/bank/row/column, never DUT index/phase.
function integer decode;input[26:0] a;reg[25:0] linear;
begin linear={a[22:10],a[25:23],a[9:0]};decode=(linear*2-base)/16;end endfunction
always @(negedge clk) begin
 tick=tick+1;rv=0;cr=mode!=1 && tick%5!=0;wr=mode!=1 && tick%7<3;
 if(mode==5)begin cr=1;wr=0;end
 if(mode==6)begin cr=0;wr=1;end
 if(mode==7)begin cr=writes<8;wr=writes<8;end
 if(mode==4&&busy&&phase==1)rv=1;
 if(!rst)begin pending_cmd=0;pending_data=0;pending_read=0;writes=0;reads=0;end
 else begin
 if(pending_read)begin
 if(delay_read==0 && mode!=2)begin
 slot=decode(saved_addr);if(mode==3)slot=slot%8;rd=memory[slot];if(corrupt && slot==3)rd=rd^128'h1;
 rv=1;pending_read=0;reads=reads+1;
 end else if(delay_read>0)delay_read=delay_read-1;
 end
 end
end
always @(posedge clk) if(rst) begin
 if((ce&&!cr)||(we&&!wr))$fatal(1,"enable without native ready");
 if(PAIRED&&((ce&&cmd==0&&!we)||(we&&!(ce&&cmd==0))))$fatal(1,"write command and data not in the same cycle");
 if(!settled_seen&&(ce||we))$fatal(1,"native enable before calibration settle");
 if(ce&&cr)begin
 if(cmd==0&&base==32'h3ff0&&writes==0&&addr!=27'h38003f8)$fatal(1,"row-boundary first native address");
 if(cmd==0&&base==32'h3ff0&&writes==1&&addr!=27'h400)$fatal(1,"row-boundary next native address");
 if(cmd==0)begin if(pending_cmd)$fatal(1,"duplicate write command");pending_cmd=1;saved_addr=addr;end
 else begin if(pending_read)$fatal(1,"multiple outstanding reads");saved_addr=addr;pending_read=1;delay_read=4;end
 end
 if(we&&wr)begin if(pending_data||!wend)$fatal(1,"duplicate/end data");pending_data=1;saved_data=wd;saved_mask=mask;end
 if(pending_cmd&&pending_data)begin
 slot=decode(saved_addr);if(mode==3)slot=slot%8;if(slot<0||slot>=64)$fatal(1,"address decode");
 for(b=0;b<16;b=b+1)if(!saved_mask[b])memory[slot][b*8+:8]=saved_data[b*8+:8];
 pending_cmd=0;pending_data=0;writes=writes+1;
 end
end
task reset;begin @(negedge clk);rst=0;start=0;cancel=0;repeat(3)@(negedge clk);rst=1;end endtask
task launch;begin @(negedge clk);start=1;@(negedge clk);start=0;end endtask
task finish;integer n;begin n=0;while(!done&&n<40000)begin @(negedge clk);n=n+1;end
if(!done)$fatal(1,"test deadline");checks=checks+1;end endtask
initial begin
 reset;launch;finish;
 if(fault||error||verified!=34||writes!=34||reads!=34||accepted!=1)$fatal(1,"normal result %d %d %d",error,writes,reads);
 if(debug[79:48]!=68||debug[111:80]!=34||debug[143:112]!=34||debug[11])$fatal(1,"normal native diagnostic counts");
 // Separately compute specification golden values, including byte-mask polarity.
 for(gi=0;gi<17;gi=gi+1)begin
 ga=gi*16;g0=ga^seed^32'ha5a55a5a;g1=(~ga)^seed^32'h3c6ef372;
 g2=((ga<<16)|(ga>>16))^seed^32'h9e3779b9;g3=ga^(~seed)^32'hc001d00d;
 golden={g3,g2,g1,g0}^128'h00ff00ff00ff00ff00ff00ff00ff00ff;
 if(memory[gi]!==golden)$fatal(1,"golden pattern/mask byte order %d",gi);
 end
 // Nonzero region crossing column/bank boundary verifies native remapping.
 reset;base=32'h1ff0;count=33;job=2;launch;finish;
 if(fault||error||verified!=66||writes!=66)$fatal(1,"boundary result");
 reset;base=32'h3ff0;launch;finish;if(fault||error||verified!=66)$fatal(1,"row transition result");
 reset;count=17;corrupt=1;launch;finish;
 if(fault||error!=6||errors!=2||first!=base+48||expected==actual)$fatal(1,"first mismatch accounting");corrupt=0;
 reset;base=1;launch;finish;if(error!=2||busy||writes)$fatal(1,"alignment");
 reset;base=32'h7fffff0;count=2;launch;finish;if(error!=2||writes)$fatal(1,"end bound");
 reset;count=1;launch;finish;if(error||verified!=2)$fatal(1,"last aligned beat");
 reset;base=0;count=32'hffffffff;launch;finish;if(error!=2)$fatal(1,"overflow bound");
 reset;count=0;launch;finish;if(error!=2)$fatal(1,"zero count");
 reset;count=1;cal=0;launch;finish;if(error!=1||writes)$fatal(1,"uncalibrated");cal=1;
 reset;mode=1;launch;finish;if(error!=3||!fault)$fatal(1,"write timeout");
 launch;repeat(5)@(negedge clk);if(busy)$fatal(1,"fault rearmed without reset");
 reset;base=0;count=17;mode=5;launch;finish;
 if(!PAIRED&&(error!=3||debug[15:12]!=3||!debug[11]||!debug[4]||debug[5]||debug[0]||debug[2]||debug[79:48]!=1||debug[111:80]!=0||debug[47:16]!=0))$fatal(1,"command-only stall evidence");
 if(PAIRED&&(error!=3||debug[15:12]!=3||!debug[11]||debug[4]||debug[5]||debug[0]||debug[2]||debug[79:48]!=0||debug[111:80]!=0||debug[47:16]!=0))$fatal(1,"paired: command-ready-only must issue nothing");
 saved_debug=debug;cancel=1;@(negedge clk);cancel=0;@(negedge clk);
 if(error!=7||debug!==saved_debug)$fatal(1,"cleanup CANCEL overwrote first fault");
 reset;mode=6;launch;finish;
 if(!PAIRED&&(error!=3||debug[15:12]!=3||debug[4]||!debug[5]||debug[0]||debug[2]||debug[79:48]!=0||debug[111:80]!=1))$fatal(1,"data-only stall evidence");
 if(PAIRED&&(error!=3||debug[15:12]!=3||debug[4]||debug[5]||debug[0]||debug[2]||debug[79:48]!=0||debug[111:80]!=0))$fatal(1,"paired: data-ready-only must issue nothing");
 reset;mode=7;launch;finish;
 if(error!=3||debug[47:16]!=8||debug[79:48]!=8||debug[111:80]!=8||debug[175:144]!=56)$fatal(1,"eight-beat stall evidence");
 reset;mode=2;launch;finish;if(error!=4||!fault)$fatal(1,"read timeout");
 reset;mode=3;count=17;launch;finish;if(error!=6||errors==0||fault)$fatal(1,"alias fault not detected");
 reset;mode=0;re=0;count=1;launch;finish;if(error!=5||!fault)$fatal(1,"read end ordering");re=1;
 reset;mode=4;launch;finish;if(error!=5||!fault)$fatal(1,"unsolicited read");
 reset;mode=0;count=17;launch;repeat(10)@(negedge clk);cancel=1;@(negedge clk);cancel=0;
 finish;if(error!=7||!fault||ce||we)$fatal(1,"cancel");
 reset;launch;repeat(10)@(negedge clk);cal=0;finish;if(error!=8||!fault)$fatal(1,"calibration loss");cal=1;
 reset;launch;repeat(5)@(negedge clk);rst=0;#1;if(ce||we)$fatal(1,"reset outputs");
 reset;mode=0;@(negedge clk);deadline_start=1;@(negedge clk);deadline_start=0;
 repeat(8)@(negedge clk);if(!deadline_done||deadline_error!=9)$fatal(1,"total deadline classification");checks=checks+1;
 $display("PASS mem_bist%s%s %0d scenarios: independent backpressure, native mapping, masks, mismatch, range, timeout, cancel/reset",PAIRED?" paired":"",(PIPE==2)?" pipelined2":(PIPE?" pipelined":""),checks);$finish;
end
endmodule
