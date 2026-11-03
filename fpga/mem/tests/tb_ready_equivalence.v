`timescale 1ns/1ps
module tb_ready_equivalence;
reg clk=0;always #5 clk=~clk;
reg reset=0,start=0;reg[31:0] seed=0,count=1;reg cr=0,wr=0,rv=0;reg[31:0] rng=32'h13579bdf;
wire bo,bn,do_,dn,fo,fn;wire[7:0] eo,en;wire[2:0] po,pn,co,cn;
wire ceo,cen,weo,wen,endo,endn;wire[26:0] ao,an;wire[127:0] wdo,wdn;wire[15:0] mo,mn;wire[175:0] dbg_o,dbg_n;
mem_bist_legacy #(.TIMEOUT_CYCLES(100),.TOTAL_TIMEOUT_CYCLES(10000)) old(
 .clk(clk),.reset_n(reset),.calibrated(1'b1),.start(start),.cancel(1'b0),.base_byte(32'b0),.beat_count(count),.seed(seed),.job_id(seed),
 .busy(bo),.done(do_),.faulted(fo),.error_code(eo),.phase(po),.app_cmd(co),.app_cmd_en(ceo),.app_addr(ao),.app_cmd_ready(cr),
 .app_write_data(wdo),.app_write_en(weo),.app_write_end(endo),.app_write_mask(mo),.app_write_ready(wr),.app_read_data(128'b0),.app_read_valid(rv),.app_read_end(1'b1),.debug_bundle(dbg_o));
mem_bist #(.TIMEOUT_CYCLES(100),.TOTAL_TIMEOUT_CYCLES(10000)) new_(
 .clk(clk),.reset_n(reset),.calibrated(1'b1),.start(start),.cancel(1'b0),.base_byte(32'b0),.beat_count(count),.seed(seed),.job_id(seed),
 .busy(bn),.done(dn),.faulted(fn),.error_code(en),.phase(pn),.app_cmd(cn),.app_cmd_en(cen),.app_addr(an),.app_cmd_ready(cr),
 .app_write_data(wdn),.app_write_en(wen),.app_write_end(endn),.app_write_mask(mn),.app_write_ready(wr),.app_read_data(128'b0),.app_read_valid(rv),.app_read_end(1'b1),.debug_bundle(dbg_n));
integer delay_=0,j,cycles=0,transactions=0;
always @(negedge clk)begin
 rng={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};cr=rng[0];wr=rng[9];rv=0;
 if(!reset)delay_=0;else if(delay_>0)begin delay_=delay_-1;if(delay_==0)rv=1;end
end
always @(posedge clk)if(reset)begin
 if((ceo&&cr)!==(cen&&cr)||(weo&&wr)!==(wen&&wr))$fatal(1,"accepted event changed");
 if(cen&&!cr||wen&&!wr)$fatal(1,"strict strobe not gated");
 if(cen)begin if(co!==cn||ao!==an)$fatal(1,"command payload changed");transactions=transactions+1;if(cn==1)delay_=3;end
 if(wen)begin if(wdo!==wdn||mo!==mn||endo!==endn)$fatal(1,"data payload changed");transactions=transactions+1;end
 #1;if({bo,do_,fo,eo,po}!={bn,dn,fn,en,pn}||dbg_o[175:16]!=dbg_n[175:16])$fatal(1,"accepted bookkeeping changed");
end
initial begin
 for(j=0;j<64;j=j+1)begin
  reset=0;repeat(3)@(negedge clk);seed=j*32'h31415927;count=1+(j%8);reset=1;start=1;@(negedge clk);start=0;
  cycles=0;while(!dn&&cycles<10000)begin @(negedge clk);cycles=cycles+1;end
  if(!dn||fn)$fatal(1,"randomized job failed");
 end
 $display("PASS ready equivalence64 randomized jobs %0d accepted events: same payload/order/bookkeeping",transactions);$finish;
end
endmodule
