// Native Gowin1:4/BL8 diagnostic: one128-bit application beat per command.
// Independent command/data acceptance; no fixed read latency assumption.
module mem_bist #(
    parameter TIMEOUT_CYCLES=8100000,
    parameter [63:0] TOTAL_TIMEOUT_CYCLES=64'd4860000000,
    // IPUG281 4.4.6: write data may sit at most one cycle before, in, or one
    // cycle after the command cycle. 1 issues command and data together, only
    // while BOTH ready inputs are high (the vendor DDR-test pattern). 0 keeps
    // the earlier independent-channel behavior for regression comparison.
    parameter PAIRED_WRITE=1,
    // The vendor DDR-test waits 256 clk_out cycles after init_calib_complete
    // before its first command.
    parameter CALIBRATION_SETTLE_CYCLES=256,
    // 1: place a zero row MSB between bank and row (IP with 14 row bits, e.g. the Sipeed sample IP:
    // app address {bank3,row14,col10}); the 1Gbit part has 13 row bits. 0: {rank0,bank3,row13,col10}.
    parameter APP_ROW_PAD=0
)(
    input wire clk,reset_n,calibrated,start,cancel,
    input wire [31:0] base_byte,beat_count,seed,job_id,
    output reg busy,done,faulted,
    output reg [7:0] error_code,
    output reg [2:0] phase,
    output reg [31:0] verified_beats,error_beats,first_bad_byte,accepted_job_id,
    output reg [127:0] first_expected,first_actual,
    output reg [63:0] elapsed_cycles,
    output wire [2:0] app_cmd,
    output wire app_cmd_en,
    output wire [26:0] app_addr,
    input wire app_cmd_ready,
    output wire [127:0] app_write_data,
    output wire app_write_en,app_write_end,
    output wire [15:0] app_write_mask,
    input wire app_write_ready,
    input wire [127:0] app_read_data,
    input wire app_read_valid,app_read_end,
    output wire [175:0] debug_bundle
);
    // phase1 fillA,2 verifyA,3 masked complementB,4 verifymerged,5 complete.
    reg [31:0] base_latched,count_latched,seed_latched,index,wait_cycles;
    reg command_sent,data_sent,read_pending,gap;
    wire writing=phase==1 || phase==3;
    wire reading=phase==2 || phase==4;
    reg [15:0] settle_count;
    wire settled=settle_count>=CALIBRATION_SETTLE_CYCLES;
    always @(posedge clk or negedge reset_n)begin
        if(!reset_n)settle_count<=0;
        else if(!calibrated)settle_count<=0;
        else if(!settled)settle_count<=settle_count+1'b1;
    end
    wire active=reset_n && calibrated && settled && busy && !faulted && !cancel && !gap;
    wire [31:0] byte_address=base_latched+(index<<4);
    wire [25:0] linear_word=byte_address[26:1];
    // Linear row-bank-column order converted to native rank-bank-row-column.
    assign app_addr=APP_ROW_PAD?{linear_word[12:10],1'b0,linear_word[25:13],linear_word[9:0]}:
        {1'b0,linear_word[12:10],linear_word[25:13],linear_word[9:0]};
    assign app_cmd=writing?3'b000:3'b001;
    assign app_cmd_en=app_cmd_ready && active &&
        ((writing&&!command_sent&&(!PAIRED_WRITE||app_write_ready))||(reading&&!read_pending));
    assign app_write_en=app_write_ready && active && writing && !data_sent &&
        (!PAIRED_WRITE||app_cmd_ready);
    assign app_write_end=app_write_en;
    assign app_write_mask=phase==3?16'haaaa:16'h0000;
    wire command_fire=app_cmd_en && app_cmd_ready;
    wire data_fire=app_write_en && app_write_ready;
    wire read_expected=reading && !gap && (read_pending || command_fire);
    wire progress=command_fire || data_fire || (app_read_valid && read_expected);
    reg [25:0] debug_commands,debug_data,debug_reads;
    reg [26:0] debug_last_address;
    reg [15:0] debug_fault_flags;
    reg debug_fault_valid;
    wire [15:0] debug_live_flags={4'b0,1'b0,calibrated,reset_n,app_read_valid,gap,
        read_pending,data_sent,command_sent,app_write_ready,app_write_en,app_cmd_ready,app_cmd_en};
    // Native counters/index stop with busy on transaction fault. Only flags need
    // explicit pre-clear capture; later cleanup CANCEL cannot replace them.
    assign debug_bundle={5'b0,debug_last_address,6'b0,debug_reads,6'b0,debug_data,
        6'b0,debug_commands,index,debug_fault_valid?debug_fault_flags:debug_live_flags};
    always @(posedge clk or negedge reset_n)begin
        if(!reset_n)begin debug_commands<=0;debug_data<=0;debug_reads<=0;debug_last_address<=0;end
        else if(start&&!busy&&!faulted)begin debug_commands<=0;debug_data<=0;debug_reads<=0;debug_last_address<=0;end
        else if(busy)begin
            if(command_fire)begin debug_commands<=debug_commands+1'b1;debug_last_address<=app_addr;end
            if(data_fire)debug_data<=debug_data+1'b1;
            if(app_read_valid)debug_reads<=debug_reads+1'b1;
        end
    end
    wire [63:0] requested_end={32'b0,base_byte}+({32'b0,beat_count}<<4);
    wire valid_range=base_byte[3:0]==0 && beat_count!=0 && beat_count<=32'd8388608 &&
                     requested_end<=64'd134217728;
    function [127:0] pattern;
        input [31:0] address,s;
        reg [31:0] p0,p1,p2,p3;
        begin
            p0=address^s^32'ha5a55a5a;
            p1=(~address)^s^32'h3c6ef372;
            p2={address[15:0],address[31:16]}^s^32'h9e3779b9;
            p3=address^(~s)^32'hc001d00d;
            pattern={p3,p2,p1,p0};
        end
    endfunction
    wire [127:0] base_pattern=pattern(byte_address,seed_latched);
    wire [127:0] expected=phase==4?
        base_pattern^128'h00ff00ff00ff00ff00ff00ff00ff00ff:base_pattern;
    assign app_write_data=phase==3?~base_pattern:base_pattern;
    task fail_job;
        input [7:0] code;
        begin
              if(!debug_fault_valid)begin debug_fault_valid<=1;
                  debug_fault_flags<={code[3:0],1'b1,debug_live_flags[10:0]};end
              busy<=0;done<=1;faulted<=1;error_code<=code;
              command_sent<=0;data_sent<=0;read_pending<=0;gap<=0;end
    endtask
    always @(posedge clk or negedge reset_n) begin
        if(!reset_n) begin
            busy<=0;done<=0;faulted<=0;phase<=0;error_code<=0;
            verified_beats<=0;error_beats<=0;first_bad_byte<=0;accepted_job_id<=0;
            first_expected<=0;first_actual<=0;elapsed_cycles<=0;
            debug_fault_valid<=0;debug_fault_flags<=0;
            base_latched<=0;count_latched<=0;seed_latched<=0;index<=0;wait_cycles<=0;
            command_sent<=0;data_sent<=0;read_pending<=0;gap<=0;
        end else if(cancel) fail_job(8'd7);
        else if(start && !busy && !faulted) begin
            done<=0;phase<=0;error_code<=0;verified_beats<=0;error_beats<=0;
            first_bad_byte<=0;first_expected<=0;first_actual<=0;elapsed_cycles<=0;
            debug_fault_valid<=0;debug_fault_flags<=0;
            accepted_job_id<=job_id;command_sent<=0;data_sent<=0;read_pending<=0;gap<=0;
            wait_cycles<=0;index<=0;
            if(!calibrated) begin done<=1;error_code<=1;end
            else if(!valid_range) begin done<=1;error_code<=2;end
            else begin busy<=1;phase<=1;base_latched<=base_byte;
                       count_latched<=beat_count;seed_latched<=seed;end
        end else if(busy) begin
            elapsed_cycles<=elapsed_cycles+1'b1;
            if(progress) wait_cycles<=0;else wait_cycles<=wait_cycles+1'b1;
            if(!calibrated) fail_job(8'd8);
            else if(elapsed_cycles>=TOTAL_TIMEOUT_CYCLES-1) fail_job(8'd9);
            else if(app_read_valid && (!read_expected || !app_read_end)) fail_job(8'd5);
            else if(wait_cycles>=TIMEOUT_CYCLES-1 && !progress)
                fail_job(reading&&read_pending?8'd4:8'd3);
            else if(gap) gap<=0;
            else if(writing) begin
                if(command_fire)command_sent<=1;
                if(data_fire)data_sent<=1;
                if((command_sent||command_fire)&&(data_sent||data_fire)) begin
                    command_sent<=0;data_sent<=0;
                    if(index==count_latched-1) begin index<=0;phase<=phase+1'b1;gap<=1;end
                    else index<=index+1'b1;
                end
            end else if(reading) begin
                if(command_fire)read_pending<=1;
                if(app_read_valid && read_expected) begin
                    read_pending<=0;gap<=1;verified_beats<=verified_beats+1'b1;
                    if(app_read_data!=expected) begin
                        if(error_beats!=32'hffffffff)error_beats<=error_beats+1'b1;
                        if(error_beats==0) begin first_bad_byte<=byte_address;
                            first_expected<=expected;first_actual<=app_read_data;end
                        error_code<=6;
                    end
                    if(index==count_latched-1) begin
                        index<=0;
                        if(phase==4) begin busy<=0;done<=1;phase<=5;gap<=0;end
                        else phase<=phase+1'b1;
                    end else index<=index+1'b1;
                end
            end
        end
    end
endmodule
