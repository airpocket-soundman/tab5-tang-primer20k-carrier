// RV32 native port -> MEMV1 with independent 1KiB I/D write-back caches.
// One inferred 512x32 single-port BSRAM, tags in distributed RAM, valid/dirty in registers.
// Blocking accelerator commands must complete barrier before borrowing staging.
module npu_rv32_ddr_cache #(
 parameter MEMORY_TIMEOUT=2700000,DRAIN_TIMEOUT=2700000
)(
 input wire clk,reset_n,memory_ready,permit,abort,clear,
 input wire mem_valid,mem_instr,input wire[31:0]mem_addr,mem_wdata,input wire[3:0]mem_wstrb,
 output wire mem_ready,output reg[31:0]mem_rdata,
 input wire barrier_valid,output wire barrier_done,
 output reg error,quarantined,output reg[3:0]error_code,
 output wire idle,
 output reg req_t,cancel_t,output reg[1:0]h_op,output reg[31:0]h_addr,h_arg,
 output reg[15:0]h_beats,output reg[23:0]h_tag,
 input wire done_t,input wire[23:0]r_tag,input wire[3:0]r_status,input wire[15:0]r_beats,
 output wire w_we,output wire[7:0]w_addr,output wire[127:0]w_data,
 output wire[7:0]r_addr,input wire[127:0]r_data
);
 localparam IDLE=0,LOOK=1,HIT=2,STORE=3,RESP=4,MISS=5,
  LINE_WAIT=6,LINE_GET=7,STAGE=8,WRITE_ISSUE=9,READ_ISSUE=10,WAIT_MEM=11,
  CAP_WAIT=12,CAP_GET=13,FILL=14,BSCAN=15,BDONE=16,FAULT=17,DRAIN=18;
 reg[4:0]state;reg[1:0]after_write;
 reg[31:0]address_q,wdata_q,store_word;reg[3:0]wstrb_q;
 reg instr_q,uncached_q;
 wire[6:0]line_index={!instr_q,address_q[9:4]};
 reg[6:0]victim,scan;reg[1:0]word;
 reg[127:0]line_data;
 reg[127:0]valid;reg[63:0]dirty;
 reg[16:0]tags[0:127] /* synthesis syn_ramstyle="distributed_ram" */;
 wire[6:0]tag_addr=state==WRITE_ISSUE?victim:line_index;
 wire[16:0]tag_read=tags[tag_addr];
 reg[31:0]ram[0:511];reg[31:0]ram_q;
 wire[31:0]ram_a_q=ram_q,ram_b_q=ram_q;
 wire line_read=state==LINE_WAIT||state==LINE_GET;
 wire[8:0]ram_addr=state==FILL?{line_index,word}:line_read?{victim,word}:{line_index,address_q[3:2]};
 wire ram_a_we=state==STORE&&!error&&!abort&&!clear&&memory_ready;
 wire ram_b_we=state==FILL&&!error&&!abort&&!clear&&memory_ready;
 always @(posedge clk)begin
  ram_q<=ram[ram_addr];
  if(ram_a_we||ram_b_we)ram[ram_addr]<=ram_b_we?line_data[word*32+:32]:store_word;
 end
 reg[1:0]done_sync;reg done_ref,outstanding;reg[23:0]next_tag;
 reg[31:0]timer;reg[1:0]settle;
 assign mem_ready=state==RESP&&mem_valid&&!error&&!abort&&!clear&&memory_ready;
 assign barrier_done=state==BDONE&&!error&&!abort&&!clear&&memory_ready;
 assign idle=(state==IDLE||state==BDONE||state==FAULT)&&!outstanding;
 assign w_we=state==STAGE&&!error&&!abort&&!clear&&memory_ready;
 assign w_addr=0;assign w_data=line_data;assign r_addr=0;
 wire completion=done_sync[1]!=done_ref;
 function[31:0]merged;
  input[31:0]old_value,new_value;input[3:0]strobes;integer k;
  begin merged=old_value;for(k=0;k<4;k=k+1)if(strobes[k])merged[k*8+:8]=new_value[k*8+:8];end
 endfunction
 task issue;
  input[1:0]op;input[31:0]a;
  begin h_op<=op;h_addr<=a;h_arg<=0;h_beats<=1;h_tag<=next_tag;next_tag<=next_tag+1'b1;
   req_t<=~req_t;outstanding<=1;timer<=0;state<=WAIT_MEM;end
 endtask
 task fail;
  input[3:0]code;input quarantine;
  begin error<=1;error_code<=code;quarantined<=quarantine;valid<=0;dirty<=0;
   if(outstanding)begin cancel_t<=~cancel_t;timer<=0;state<=DRAIN;end else state<=FAULT;
  end
 endtask
 integer i;
 always @(posedge clk)begin
  done_sync<={done_sync[0],done_t};
  if(!reset_n)begin
   state<=IDLE;after_write<=0;address_q<=0;wdata_q<=0;wstrb_q<=0;instr_q<=0;uncached_q<=0;
   store_word<=0;mem_rdata<=0;victim<=0;scan<=0;word<=0;line_data<=0;valid<=0;dirty<=0;
   req_t<=0;cancel_t<=0;h_op<=0;h_addr<=0;h_arg<=0;h_beats<=0;h_tag<=0;
   done_sync<={2{done_t}};done_ref<=done_t;outstanding<=0;next_tag<=1;timer<=0;settle<=2;
   error<=0;quarantined<=0;error_code<=0;
  end else if(settle!=0)begin settle<=settle-1'b1;done_ref<=done_sync[1];end
  else if(clear&&!outstanding&&!quarantined&&memory_ready)begin
   error<=0;error_code<=0;state<=IDLE;valid<=0;dirty<=0;done_ref<=done_sync[1];settle<=2;
  end else if(state==DRAIN)begin
   if(completion)begin
    done_ref<=done_sync[1];
    if(r_tag==h_tag)begin outstanding<=0;state<=FAULT;end
    else begin quarantined<=1;state<=FAULT;end
   end else if(timer>=DRAIN_TIMEOUT)begin quarantined<=1;state<=FAULT;end
   else timer<=timer+1'b1;
  end else if(error)begin
   if(completion)begin done_ref<=done_sync[1];quarantined<=1;end
   if(clear&&!outstanding&&!quarantined&&memory_ready)begin
    error<=0;error_code<=0;state<=IDLE;valid<=0;dirty<=0;done_ref<=done_sync[1];
   end
  end else if(abort)begin fail(6,0);end
  else if(!memory_ready)begin fail(7,1);end
  else if(completion&&state!=WAIT_MEM)begin done_ref<=done_sync[1];fail(4,1);end
  else case(state)
   IDLE:if(permit)begin
    if(barrier_valid)begin scan<=0;state<=BSCAN;end
    else if(mem_valid)begin
     if(mem_addr>=32'h08000000||mem_addr[1:0]!=0||(mem_instr&&mem_wstrb!=0))fail(1,0);
     else begin address_q<=mem_addr;wdata_q<=mem_wdata;wstrb_q<=mem_wstrb;instr_q<=mem_instr;
      uncached_q<=mem_addr>=32'h07ff0000;state<=LOOK;end
    end
   end
   LOOK:begin
    if(uncached_q)state<=READ_ISSUE;
    else if(valid[line_index]&&tag_read==address_q[26:10])state<=HIT;
    else state<=MISS;
   end
   HIT:if(wstrb_q!=0)begin store_word<=merged(ram_a_q,wdata_q,wstrb_q);state<=STORE;end
       else begin mem_rdata<=ram_a_q;state<=RESP;end
   STORE:begin dirty[line_index[5:0]]<=1;state<=RESP;end
   RESP:state<=IDLE;
   MISS:begin
    if(line_index[6]&&valid[line_index]&&dirty[line_index[5:0]])begin
     victim<=line_index;word<=0;after_write<=0;state<=LINE_WAIT;
    end else state<=READ_ISSUE;
   end
   LINE_WAIT:state<=LINE_GET;
   LINE_GET:begin
    line_data[word*32+:32]<=ram_b_q;
    if(word==3)state<=STAGE;else begin word<=word+1'b1;state<=LINE_WAIT;end
   end
   STAGE:state<=WRITE_ISSUE;
   WRITE_ISSUE:issue(1,after_write==2?{address_q[31:4],4'b0}:{5'd0,tag_read,victim[5:0],4'b0});
   READ_ISSUE:issue(0,{address_q[31:4],4'b0});
   WAIT_MEM:begin
    if(completion)begin
     done_ref<=done_sync[1];
     if(r_tag!=h_tag)fail(4,1);
     else begin
      outstanding<=0;
      if(r_status!=0||r_beats!=1)begin error<=1;error_code<=5;quarantined<=r_status==9;state<=FAULT;valid<=0;dirty<=0;end
      else if(h_op==0)state<=CAP_WAIT;
      else if(after_write==0)begin dirty[victim[5:0]]<=0;valid[victim]<=0;state<=READ_ISSUE;end
      else if(after_write==1)begin dirty[victim[5:0]]<=0;scan<=scan+1'b1;state<=BSCAN;end
      else state<=RESP;
     end
    end else if(timer>=MEMORY_TIMEOUT)fail(3,0);else timer<=timer+1'b1;
   end
   CAP_WAIT:state<=CAP_GET;
   CAP_GET:begin
    if(uncached_q)begin
     if(wstrb_q!=0)begin
      line_data<=r_data;line_data[address_q[3:2]*32+:32]<=merged(r_data[address_q[3:2]*32+:32],wdata_q,wstrb_q);
      after_write<=2;state<=STAGE;
     end else begin mem_rdata<=r_data[address_q[3:2]*32+:32];state<=RESP;end
    end else begin line_data<=r_data;word<=0;state<=FILL;end
   end
   FILL:begin
    if(word==3)begin tags[line_index]<=address_q[26:10];valid[line_index]<=1;
     if(line_index[6])dirty[line_index[5:0]]<=0;state<=LOOK;
    end else word<=word+1'b1;
   end
   BSCAN:begin
    if(scan==64)begin valid[127:64]<=0;dirty<=0;state<=BDONE;end
    else if(valid[64+scan]&&dirty[scan])begin victim<=64+scan;word<=0;after_write<=1;state<=LINE_WAIT;end
    else scan<=scan+1'b1;
   end
   BDONE:if(!barrier_valid)state<=IDLE;
   default:fail(8,1);
  endcase
 end
endmodule
