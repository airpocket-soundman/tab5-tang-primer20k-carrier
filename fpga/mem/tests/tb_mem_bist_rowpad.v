// Address placement of APP_ROW_PAD=1 (14-row IP layout {bank3,row14,col10}) against the default
// {rank0,bank3,row13,col10}. The first command of a write job must carry the expected address.
`timescale 1ns/1ps
module tb_mem_bist_rowpad;
parameter PIPE=0;
reg clk=0,reset_n=0;
always #5 clk=~clk;
reg start=0;
reg [31:0] base=0;
wire [26:0] addr_pad,addr_def;
wire en_pad,en_def;
reg ready=1;
reg [127:0] rd=0;
wire busy_p,busy_d,done_p,done_d,fault_p,fault_d;
wire [7:0] err_p,err_d;
wire [2:0] ph_p,ph_d;
wire [31:0] v_p,e_p,f_p,a_p,v_d,e_d,f_d,a_d;
wire [127:0] fe_p,fa_p,fe_d,fa_d;
wire [63:0] cy_p,cy_d;
wire [2:0] cmd_p,cmd_d;
wire [127:0] wd_p,wd_d;
wire we_p,wend_p,we_d,wend_d;
wire [15:0] wm_p,wm_d;
wire [175:0] dbg_p,dbg_d;
mem_bist #(.APP_ROW_PAD(1),.PIPELINE(PIPE),.CALIBRATION_SETTLE_CYCLES(0)) pad(clk,reset_n,1'b1,start,1'b0,base,32'd1,32'd7,32'd1,
 busy_p,done_p,fault_p,err_p,ph_p,v_p,e_p,f_p,a_p,fe_p,fa_p,cy_p,cmd_p,en_pad,addr_pad,ready,wd_p,we_p,wend_p,wm_p,ready,rd,1'b0,1'b0,dbg_p);
mem_bist #(.APP_ROW_PAD(0),.PIPELINE(PIPE),.CALIBRATION_SETTLE_CYCLES(0)) def(clk,reset_n,1'b1,start,1'b0,base,32'd1,32'd7,32'd1,
 busy_d,done_d,fault_d,err_d,ph_d,v_d,e_d,f_d,a_d,fe_d,fa_d,cy_d,cmd_d,en_def,addr_def,ready,wd_d,we_d,wend_d,wm_d,ready,rd,1'b0,1'b0,dbg_d);
integer checks=0;
// expected: byte address -> word = byte[26:1]; col=word[9:0], bank=word[12:10], row=word[25:13]
task check(input [31:0] byte_addr);
    reg [25:0] w; reg [26:0] exp_pad,exp_def; integer t;
    begin
        w=byte_addr[26:1];
        exp_pad={w[12:10],1'b0,w[25:13],w[9:0]};
        exp_def={1'b0,w[12:10],w[25:13],w[9:0]};
        base=byte_addr;
        @(posedge clk); start<=1; @(posedge clk); start<=0;
        t=0;
        while(!(en_pad&&en_def)&&t<50) begin @(posedge clk); t=t+1; end
        if(!(en_pad&&en_def)) begin $display("FATAL: no command for base %h",byte_addr); $fatal(1); end
        if(addr_pad!==exp_pad || addr_def!==exp_def) begin
            $display("FATAL: base %h pad %h (exp %h) def %h (exp %h)",byte_addr,addr_pad,exp_pad,addr_def,exp_def); $fatal(1);
        end
        checks=checks+1;
        // finish job: pulse reset to return to idle
        reset_n=0; repeat(3) @(posedge clk); reset_n=1; repeat(3) @(posedge clk);
    end
endtask
initial begin
    repeat(4) @(posedge clk); reset_n=1; repeat(3) @(posedge clk);
    check(32'h0000_0000);
    check(32'h0000_1ff0);        // column boundary region
    check(32'h0000_3ff0);        // row 1
    check(32'h0000_4000);
    check(32'h0001_0000);
    check(32'h0100_0000);
    check(32'h0400_0000);        // high row bits
    check(32'h0800_0000-32'h10); // last beat
    $display("PASS mem_bist row-pad address placement %0d bases", checks);
    $finish;
end
endmodule
