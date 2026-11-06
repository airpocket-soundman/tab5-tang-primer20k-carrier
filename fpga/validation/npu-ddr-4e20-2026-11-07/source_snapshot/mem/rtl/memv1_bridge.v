// USER-domain half of the SYS(27MHz) -> USER(~99.56MHz) held-bundle CDC for MEMV1.
// SYS holds {h_op,h_addr,h_beats,h_arg,h_tag} stable from the req_t toggle until it has seen done_t change.
// This side synchronizes the toggles (2 flops), launches the adapter one cycle after the synchronized toggle
// differs (bundle stable for >= 2 USER cycles), and publishes {r_*} before it toggles done_t. The result bundle
// is only changed again after the next launch. The bridge adopts the current toggle values whenever USER reset
// is asserted, so a request/cancel that was in flight across a reset is never replayed.
module memv1_bridge(
 input wire clk,user_reset_n,
 input wire req_t,cancel_t,
 input wire[1:0] h_op,input wire[31:0] h_addr,input wire[15:0] h_beats,input wire[31:0] h_arg,input wire[23:0] h_tag,
 output reg done_t,
 output reg[23:0] r_tag,output reg[3:0] r_status,output reg[31:0] r_crc,output reg[15:0] r_beats,
 output wire active,
 output wire cmd_valid,input wire cmd_ready,
 output wire[1:0] cmd_op,output wire[31:0] cmd_addr,output wire[15:0] cmd_beats,output wire[31:0] cmd_arg,output wire[23:0] cmd_tag,
 output wire cancel,
 input wire rsp_valid,input wire[23:0] rsp_tag,input wire[3:0] rsp_status,input wire[31:0] rsp_crc,input wire[15:0] rsp_beats
);
reg[1:0] rq_s,cn_s;reg req_ref,cn_ref,launch,running,cancel_lat;
initial done_t=0;
wire new_req=rq_s[1]!=req_ref&&!launch&&!running;
assign active=launch||running;
assign cmd_valid=launch;
assign cmd_op=h_op;assign cmd_addr=h_addr;assign cmd_beats=h_beats;assign cmd_arg=h_arg;assign cmd_tag=h_tag;
assign cancel=cancel_lat;
always @(posedge clk)begin
 rq_s<={rq_s[0],req_t};cn_s<={cn_s[0],cancel_t};
 if(!user_reset_n)begin
  req_ref<=rq_s[1];cn_ref<=cn_s[1];launch<=0;running<=0;cancel_lat<=0;
 end else begin
  if(new_req)begin launch<=1;req_ref<=rq_s[1];end
  if(launch&&cmd_ready)begin launch<=0;running<=1;end
  if(cn_s[1]!=cn_ref)begin cn_ref<=cn_s[1];if(launch||running||new_req)cancel_lat<=1;end
  if(rsp_valid)begin
   r_tag<=rsp_tag;r_status<=rsp_status;r_crc<=rsp_crc;r_beats<=rsp_beats;
   done_t<=~done_t;running<=0;cancel_lat<=0;
  end
 end
end
endmodule
