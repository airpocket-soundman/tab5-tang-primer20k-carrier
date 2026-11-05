// Offline request-only candidate. Not connected to a product LINK/top.
// Byte stream:216MHz aligned CLK/DATA sampling -> Gray FIFO ->54MHz ready/valid.
// Consumer MUST reject the whole transaction on overflow; FIFO is not a parser.
// Synthesis/placement is deliberately unqualified: mapped CLK/DATA sampling
// cells (including possible shift-register RAM inference) must be inspected
// before integration. RTL register syntax alone does not prove DFF mapping.
module request_capture_fifo #(parameter ADDR_BITS=4,parameter PHYSICAL_FF=0,parameter PIPELINED_READ=0)(
 input wire sample_clk,sys_clk,reset_n,arm,dir,raw_clk,
 input wire [7:0] data_i,input wire byte_ready,
 output wire byte_valid,output reg [7:0] byte_data,output wire overflow
);
 localparam DEPTH=1<<ADDR_BITS;
 initial if(ADDR_BITS<2)$fatal(1,"ADDR_BITS must be at least2");
 wire global_reset_n=reset_n && arm;
 wire session_reset_n=global_reset_n && !dir;
 // DIR/ARM assert reset immediately; local release is clock-synchronized.
 (* ASYNC_REG="TRUE" *) reg [2:0] sample_release;
 (* ASYNC_REG="TRUE" *) reg [1:0] sys_release;
 always @(posedge sample_clk or negedge session_reset_n)
  if(!session_reset_n)sample_release<=0;
  else sample_release<={sample_release[1:0],1'b1};
 always @(posedge sys_clk or negedge session_reset_n)
  if(!session_reset_n)sys_release<=0;
  else sys_release<={sys_release[0],1'b1};
 wire sample_reset_n=sample_release[2];
 wire sys_reset_n=sys_release[1];

 // Keep observing CLK even in DIR1/ARM0, so an already-HIGH clock does not
 // become a fake first request edge at a direction/rearm boundary. Initial
 // reset release is primed for3sample ticks before edges can be accepted.
 wire [2:0] clock_samples;
 wire [7:0] data_sampled;
 generate if(PHYSICAL_FF) begin: physical_capture
  wire [7:0] data_meta;
  genvar i;
  for(i=0;i<8;i=i+1) begin: lane
   DFFC meta_ff(.Q(data_meta[i]),.D(data_i[i]),.CLK(sample_clk),.CLEAR(!reset_n));
   DFFC sampled_ff(.Q(data_sampled[i]),.D(data_meta[i]),.CLK(sample_clk),.CLEAR(!reset_n));
  end
  DFFC clock0(.Q(clock_samples[0]),.D(raw_clk),.CLK(sample_clk),.CLEAR(!reset_n));
  DFFC clock1(.Q(clock_samples[1]),.D(clock_samples[0]),.CLK(sample_clk),.CLEAR(!reset_n));
  DFFC clock2(.Q(clock_samples[2]),.D(clock_samples[1]),.CLK(sample_clk),.CLEAR(!reset_n));
 end else begin: portable_capture
  reg [2:0] clocks;
  reg [7:0] meta,sampled;
  always @(posedge sample_clk or negedge reset_n)begin
   if(!reset_n)begin clocks<=0;meta<=0;sampled<=0;end
   else begin clocks<={clocks[1:0],raw_clk};meta<=data_i;sampled<=meta;end
  end
  assign clock_samples=clocks;assign data_sampled=sampled;
 end endgenerate
 wire request_rise=clock_samples[1] && !clock_samples[2];
 reg [ADDR_BITS:0] write_binary,write_gray,read_binary,read_gray;
 (* ASYNC_REG="TRUE" *) reg [ADDR_BITS:0] read_gray_meta,read_gray_sampled;
 (* ASYNC_REG="TRUE" *) reg [ADDR_BITS:0] write_gray_meta,write_gray_sampled;
 reg [7:0] memory[0:DEPTH-1];
 reg source_overflow;
 (* ASYNC_REG="TRUE" *) reg [1:0] overflow_sync;
 reg holding;
 wire full=write_gray=={~read_gray_sampled[ADDR_BITS:ADDR_BITS-1],read_gray_sampled[ADDR_BITS-2:0]};
 wire empty=read_gray==write_gray_sampled;
 wire write_event=sample_reset_n && request_rise && !source_overflow;
 wire write_accept=write_event && !full;
 wire [ADDR_BITS:0] next_write_binary=write_binary+1'b1;
 wire [ADDR_BITS:0] next_read_binary=read_binary+1'b1;
 wire [ADDR_BITS:0] next_read_gray=(next_read_binary>>1)^next_read_binary;
 wire next_available=next_read_gray!=write_gray_sampled;
 assign overflow=overflow_sync[1];
 assign byte_valid=holding && session_reset_n && sys_reset_n && !overflow;

 always @(posedge sample_clk or negedge sample_reset_n)begin
  if(!sample_reset_n)begin
   write_binary<=0;write_gray<=0;read_gray_meta<=0;read_gray_sampled<=0;
  end else begin
   read_gray_meta<=read_gray;read_gray_sampled<=read_gray_meta;
   if(write_accept)begin write_binary<=next_write_binary;write_gray<=(next_write_binary>>1)^next_write_binary;end
  end
 end
 // No asynchronous reset of the storage array; stale words are unreachable
 // after a session reset because both pointers and output valid reset.
 always @(posedge sample_clk)if(write_accept)memory[write_binary[ADDR_BITS-1:0]]<=data_sampled;
 // Sticky across DIR changes; explicit ARM low or global reset is required.
 always @(posedge sample_clk or negedge global_reset_n)
  if(!global_reset_n)source_overflow<=0;
  else if(write_event && full)source_overflow<=1;
 always @(posedge sys_clk or negedge global_reset_n)
  if(!global_reset_n)overflow_sync<=0;
  else overflow_sync<={overflow_sync[0],source_overflow};

 always @(posedge sys_clk or negedge sys_reset_n)begin
  if(!sys_reset_n)begin
   read_binary<=0;read_gray<=0;write_gray_meta<=0;write_gray_sampled<=0;
   holding<=0;byte_data<=0;
  end else begin
   write_gray_meta<=write_gray;write_gray_sampled<=write_gray_meta;
   if(overflow)holding<=0;
   else if(holding)begin
    if(byte_ready)begin
     // Release only the byte actually consumed. Prefetch does not publish
     // an extra slot; stalled holding/data and the read pointer stay fixed.
     read_binary<=next_read_binary;read_gray<=next_read_gray;
     if(PIPELINED_READ && next_available)begin
      byte_data<=memory[next_read_binary[ADDR_BITS-1:0]];holding<=1;
     end else holding<=0;
    end
   end else if(!empty)begin
    // Registered RAM read. One fetch clock plus one consume clock gives a
    // peak27MB/s at54MHz; stalls hold both data and valid until acceptance.
    byte_data<=memory[read_binary[ADDR_BITS-1:0]];holding<=1;
   end
  end
 end
endmodule
