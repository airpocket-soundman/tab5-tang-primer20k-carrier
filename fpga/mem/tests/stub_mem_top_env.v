`timescale 1ns/1ps
// Simulation-only environment for mem_top: stand-ins for the Gowin rPLL primitive and for the DDR3 controller IP
// (MemDDR3 regenerated IP, DDR3_Memory_Interface_Top Sipeed sample IP). They model ONLY the native user interface
// (ideal ready, fixed read latency: command edge -> data-valid edge = LAT+1 = 6 cycles, byte-masked writes, app_burst_number bursts); no DRAM timing, no calibration behaviour.
// Evidence from this environment is RTL-integration evidence, never DDR3 performance evidence.
module rPLL(input CLKIN,RESET,RESET_P,CLKFB,input [5:0] FBDSEL,IDSEL,ODSEL,input [3:0] PSDA,DUTYDA,FDLY,
    output CLKOUT,output reg LOCK,output CLKOUTP,CLKOUTD,CLKOUTD3);
    parameter FCLKIN="27",DYN_IDIV_SEL="false",IDIV_SEL=0,DYN_FBDIV_SEL="false",FBDIV_SEL=0,DYN_ODIV_SEL="false",ODIV_SEL=2,
        PSDA_SEL="0000",DYN_DA_EN="true",DUTYDA_SEL="1000",CLKOUT_FT_DIR=1'b1,CLKOUTP_FT_DIR=1'b1,CLKOUT_DLY_STEP=0,CLKOUTP_DLY_STEP=0,
        CLKFB_SEL="internal",CLKOUT_BYPASS="false",CLKOUTP_BYPASS="false",CLKOUTD_BYPASS="false",DYN_SDIV_SEL=2,CLKOUTD_SRC="CLKOUT",
        CLKOUTD3_SRC="CLKOUT",DEVICE="GW2A-18C";
    assign CLKOUT=CLKIN; assign CLKOUTP=CLKIN; assign CLKOUTD=CLKIN; assign CLKOUTD3=CLKIN;
    initial LOCK=0;
    always @(posedge CLKIN or posedge RESET) if(RESET) LOCK<=0; else LOCK<=1;
endmodule

// byte_addr = {row,bank,col,1'b0} of the native address (already decoded by the wrapper).
module ddr_native_model #(parameter LAT=5,parameter CALIB_CYCLES=300)(
    input wire rst_n,
    output reg clk_out,output reg ddr_rst,output reg calib,
    input wire [2:0] cmd,input wire cmd_en,input wire [26:0] byte_addr,input wire [5:0] burst_num,
    input wire [127:0] wr_data,input wire wr_en,input wire [15:0] wr_mask,
    output wire cmd_ready,wr_rdy,
    output reg [127:0] rd_data,output reg rd_valid,rd_end);
    initial begin clk_out=0; ddr_rst=1; calib=0; end
    always #5 clk_out=~clk_out;
    assign cmd_ready=1'b1; assign wr_rdy=1'b1;
    reg [127:0] mem [0:262143];
    integer ii; initial for(ii=0;ii<262144;ii=ii+1) mem[ii]=128'hdeadbeef_deadbeef_deadbeef_deadbeef;
    integer cal_cnt=0,cyc=0;
    reg [26:0] wq_addr [0:15]; reg [6:0] wq_len [0:15]; integer wq_h=0,wq_t=0,wbeat=0;
    reg [26:0] rq_addr [0:4095]; integer rq_due [0:4095]; reg rq_last [0:4095]; integer rq_h=0,rq_t=0;
    integer k,b; reg [127:0] cur; reg [26:0] a; reg [26:0] ca; integer hit;
    always @(posedge clk_out) begin
        cyc=cyc+1;
        rd_valid<=0; rd_end<=0;
        if(!rst_n) begin ddr_rst<=1; calib<=0; cal_cnt=0; wq_h=0; wq_t=0; wbeat=0; rq_h=0; rq_t=0; end
        else begin
            ddr_rst<=0;
            if(cal_cnt<CALIB_CYCLES) cal_cnt=cal_cnt+1; else calib<=1;
            if(calib) begin
                if(cmd_en && cmd==3'd0) begin wq_addr[wq_t%16]=byte_addr; wq_len[wq_t%16]=burst_num+7'd1; wq_t=wq_t+1; end
                if(cmd_en && cmd==3'd1) begin
                    for(k=0;k<=burst_num;k=k+1) begin
                        rq_addr[rq_t%4096]=byte_addr+16*k; rq_due[rq_t%4096]=cyc+LAT+k; rq_last[rq_t%4096]=(k==burst_num); rq_t=rq_t+1;
                    end
                end
                if(wr_en) begin
                    if(wq_h==wq_t) $display("MODEL ERROR: write data without command");
                    else begin
                        ca=wq_addr[wq_h%16]+16*wbeat; cur=mem[(ca>>4)&262143];
                        for(b=0;b<16;b=b+1) if(!wr_mask[b]) cur[8*b+:8]=wr_data[8*b+:8];
                        mem[(ca>>4)&262143]=cur; wbeat=wbeat+1;
                        if(wbeat==wq_len[wq_h%16]) begin wq_h=wq_h+1; wbeat=0; end
                    end
                end
                if(rq_h!=rq_t && rq_due[rq_h%4096]<=cyc) begin
                    rd_data<=mem[(rq_addr[rq_h%4096]>>4)&262143]; rd_valid<=1; rd_end<=rq_last[rq_h%4096]; rq_h=rq_h+1;
                end
            end
        end
    end
endmodule

module MemDDR3(input wire [63:0] deep_taps,input wire clk,memory_clk,pll_lock,rst_n,
    input wire [2:0] cmd,input wire cmd_en,input wire [26:0] addr,output wire cmd_ready,
    input wire [127:0] wr_data,input wire wr_data_en,wr_data_end,input wire [15:0] wr_data_mask,output wire wr_data_rdy,
    output wire [127:0] rd_data,output wire rd_data_valid,rd_data_end,
    input wire sr_req,ref_req,burst,output wire clk_out,ddr_rst,init_calib_complete,sr_ack,ref_ack,
    output wire [12:0] O_ddr_addr,output wire [2:0] O_ddr_ba,output wire O_ddr_cs_n,O_ddr_ras_n,O_ddr_cas_n,O_ddr_we_n,
    output wire O_ddr_clk,O_ddr_clk_n,O_ddr_cke,O_ddr_odt,O_ddr_reset_n,output wire [1:0] O_ddr_dqm,
    inout wire [15:0] IO_ddr_dq,inout wire [1:0] IO_ddr_dqs,IO_ddr_dqs_n);
    wire [25:0] lw={addr[22:10],addr[25:23],addr[9:0]};      // {rank0,bank3,row13,col10} -> linear word
    reg cr; wire clk_o,dr,cal; reg [127:0] rd; reg v,e;
    wire [127:0] rdw; wire vw,ew;
    ddr_native_model m(.rst_n(rst_n&&pll_lock),.clk_out(clk_o),.ddr_rst(dr),.calib(cal),.cmd(cmd),.cmd_en(cmd_en),.byte_addr({lw,1'b0}),
        .burst_num(6'd0),.wr_data(wr_data),.wr_en(wr_data_en),.wr_mask(wr_data_mask),.cmd_ready(cmd_ready),.wr_rdy(wr_data_rdy),
        .rd_data(rdw),.rd_valid(vw),.rd_end(ew));
    assign clk_out=clk_o; assign ddr_rst=dr; assign init_calib_complete=cal;
    assign rd_data=rdw; assign rd_data_valid=vw; assign rd_data_end=ew; assign sr_ack=0; assign ref_ack=0;
    assign {O_ddr_addr,O_ddr_ba,O_ddr_cs_n,O_ddr_ras_n,O_ddr_cas_n,O_ddr_we_n,O_ddr_clk,O_ddr_clk_n,O_ddr_cke,O_ddr_odt,O_ddr_reset_n,O_ddr_dqm}=0;
endmodule

module DDR3_Memory_Interface_Top(input wire clk,memory_clk,pll_lock,rst_n,input wire [5:0] app_burst_number,
    input wire [2:0] cmd,input wire cmd_en,input wire [27:0] addr,output wire cmd_ready,
    input wire [127:0] wr_data,input wire wr_data_en,wr_data_end,input wire [15:0] wr_data_mask,output wire wr_data_rdy,
    output wire [127:0] rd_data,output wire rd_data_valid,rd_data_end,
    input wire sr_req,ref_req,burst,output wire clk_out,ddr_rst,init_calib_complete,sr_ack,ref_ack,
    output wire [13:0] O_ddr_addr,output wire [2:0] O_ddr_ba,output wire O_ddr_cs_n,O_ddr_ras_n,O_ddr_cas_n,O_ddr_we_n,
    output wire O_ddr_clk,O_ddr_clk_n,O_ddr_cke,O_ddr_odt,O_ddr_reset_n,output wire [1:0] O_ddr_dqm,
    inout wire [15:0] IO_ddr_dq,inout wire [1:0] IO_ddr_dqs,IO_ddr_dqs_n);
    wire [25:0] lw={addr[22:10],addr[26:24],addr[9:0]};      // {bank3,pad0,row13,col10} (row14 layout, MSB zero) -> linear word
    ddr_native_model m(.rst_n(rst_n&&pll_lock),.clk_out(clk_out),.ddr_rst(ddr_rst),.calib(init_calib_complete),.cmd(cmd),.cmd_en(cmd_en),
        .byte_addr({lw,1'b0}),.burst_num(app_burst_number),.wr_data(wr_data),.wr_en(wr_data_en),.wr_mask(wr_data_mask),
        .cmd_ready(cmd_ready),.wr_rdy(wr_data_rdy),.rd_data(rd_data),.rd_valid(rd_data_valid),.rd_end(rd_data_end));
    assign sr_ack=0; assign ref_ack=0;
    assign {O_ddr_addr,O_ddr_ba,O_ddr_cs_n,O_ddr_ras_n,O_ddr_cas_n,O_ddr_we_n,O_ddr_clk,O_ddr_clk_n,O_ddr_cke,O_ddr_odt,O_ddr_reset_n,O_ddr_dqm}=0;
endmodule
