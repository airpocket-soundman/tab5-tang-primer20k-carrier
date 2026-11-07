// SYS-domain, one-outstanding arbiter for two held-toggle MEMV1 masters.
// This arbitrates commands only: the integrating top owns staging-RAM lifetime.
// Masters hold request metadata until their done toggle changes. Each accepted
// request gets a NEW merged toggle; owner changes never mux source toggle phases.
// reset_n is synchronous. Reset both masters and the downstream bridge together;
// hold reset long enough for the bridge's USER-domain toggle synchronizers.
// Reset adopts current source toggles/done phase and drops unfinished requests.
// An unsolicited completion or mismatched tag quarantines until coordinated reset.
module npu_ddr_arbiter(
 input wire clk,reset_n,
 input wire m0_req_t,m0_cancel_t,
 input wire [1:0] m0_h_op,input wire [31:0] m0_h_addr,
 input wire [15:0] m0_h_beats,input wire [31:0] m0_h_arg,input wire [23:0] m0_h_tag,
 output reg m0_done_t,output reg [23:0] m0_r_tag,output reg [3:0] m0_r_status,
 output reg [31:0] m0_r_crc,output reg [15:0] m0_r_beats,
 input wire m1_req_t,m1_cancel_t,
 input wire [1:0] m1_h_op,input wire [31:0] m1_h_addr,
 input wire [15:0] m1_h_beats,input wire [31:0] m1_h_arg,input wire [23:0] m1_h_tag,
 output reg m1_done_t,output reg [23:0] m1_r_tag,output reg [3:0] m1_r_status,
 output reg [31:0] m1_r_crc,output reg [15:0] m1_r_beats,
 output reg req_t,cancel_t,
 output reg [1:0] h_op,output reg [31:0] h_addr,
 output reg [15:0] h_beats,output reg [31:0] h_arg,output reg [23:0] h_tag,
 input wire done_t,input wire [23:0] r_tag,input wire [3:0] r_status,
 input wire [31:0] r_crc,input wire [15:0] r_beats,
 output reg active,owner,fault
);
 reg req_ref0,req_ref1,cancel_ref0,cancel_ref1;
 (* ASYNC_REG="TRUE" *) reg done_meta,done_sync;
 reg done_ref,prefer,cancel_sent,settle;
 wire pending0=m0_req_t!=req_ref0,pending1=m1_req_t!=req_ref1;
 wire cancel0=m0_cancel_t!=cancel_ref0,cancel1=m1_cancel_t!=cancel_ref1;
 wire grant_owner=pending0 && pending1 ? prefer : !pending0;
 wire completion=done_sync!=done_ref;
 always @(posedge clk) begin
  if(!reset_n) begin
   req_ref0<=m0_req_t;req_ref1<=m1_req_t;
   cancel_ref0<=m0_cancel_t;cancel_ref1<=m1_cancel_t;
   done_meta<=done_t;done_sync<=done_t;done_ref<=done_t;
   req_t<=0;cancel_t<=0;h_op<=0;h_addr<=0;h_beats<=0;h_arg<=0;h_tag<=0;
   m0_done_t<=0;m0_r_tag<=0;m0_r_status<=0;m0_r_crc<=0;m0_r_beats<=0;
   m1_done_t<=0;m1_r_tag<=0;m1_r_status<=0;m1_r_crc<=0;m1_r_beats<=0;
   active<=0;owner<=0;fault<=0;prefer<=0;cancel_sent<=0;settle<=1;
  end else begin
   done_meta<=done_t;done_sync<=done_meta;
   // Adopt all cancel edges even when idle or owned by the other master.
   // Such edges cannot be replayed as a cancellation of a later transaction.
   cancel_ref0<=m0_cancel_t;cancel_ref1<=m1_cancel_t;
   // Synchronous masters may reset their output toggles by nonblocking updates
   // on the same reset edge. Re-adopt once after reset so those new phases do
   // not look like requests (or unsolicited completions) on reset release.
   if(settle) begin
    settle<=0;req_ref0<=m0_req_t;req_ref1<=m1_req_t;
    done_meta<=done_t;done_sync<=done_t;done_ref<=done_t;
   end else if(!fault) begin
    if(completion) begin
     done_ref<=done_sync;
     if(active && r_tag==h_tag) begin
      if(owner) begin
       m1_r_tag<=r_tag;m1_r_status<=r_status;m1_r_crc<=r_crc;m1_r_beats<=r_beats;
       m1_done_t<=~m1_done_t;
      end else begin
       m0_r_tag<=r_tag;m0_r_status<=r_status;m0_r_crc<=r_crc;m0_r_beats<=r_beats;
       m0_done_t<=~m0_done_t;
      end
      active<=0;cancel_sent<=0;
     end else begin
      // No success/error response is fabricated for an uncorrelated completion.
      // Hold ownership/metadata and block every further launch until reset.
      fault<=1;active<=1;
     end
    end else if(!active) begin
     if(pending0 || pending1) begin
      owner<=grant_owner;active<=1;prefer<=~grant_owner;
      req_t<=~req_t;
      if(grant_owner) begin
       req_ref1<=m1_req_t;h_op<=m1_h_op;h_addr<=m1_h_addr;
       h_beats<=m1_h_beats;h_arg<=m1_h_arg;h_tag<=m1_h_tag;
       cancel_sent<=cancel1;
       if(cancel1)cancel_t<=~cancel_t;
      end else begin
       req_ref0<=m0_req_t;h_op<=m0_h_op;h_addr<=m0_h_addr;
       h_beats<=m0_h_beats;h_arg<=m0_h_arg;h_tag<=m0_h_tag;
       cancel_sent<=cancel0;
       if(cancel0)cancel_t<=~cancel_t;
      end
     end
    end else if(!cancel_sent && (owner?cancel1:cancel0)) begin
     cancel_t<=~cancel_t;cancel_sent<=1;
    end
   end
  end
 end
endmodule
