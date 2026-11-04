// LINK-visible control/result port of the DDR3 bandwidth engine mem_bw (opcodes 0x60..0x6F, new; the MEM diagnostic ABI 0x50..0x5C is untouched).
// Instantiated by mem_top only when BW_ENABLE=1. Documentation: fpga/mem/BW_ENGINE.md. STATUS: simulation only, no hardware result.
//
// SYS side (27 MHz LINK domain) <-> USER side (DDR3 user clock). Only START/CANCEL cross as a request toggle with the held
// configuration (config registers stay constant from the request until its acknowledge, like mem_mailbox). Results are NOT copied:
// a job that has finished leaves every counter of mem_bw constant until the next START, and the SYS side reads them word by word
// only while done && !busy (synchronised flags) and a SNAPSHOT command has validated that state. No DDR-native signal is used
// directly in the SYS domain.
//
//   0x60..0x66  CFG word write {b,a}: 0 base[15:0], 1 base[31:16], 2 beat_count[15:0], 3 beat_count[31:16], 4 seed[15:0], 5 seed[31:16],
//               6 ctl = {burst_log2[2:0] (bits 12:10), region_log2[4:0] (9:5), pattern[2:0] (4:2), mode[1:0] (1:0)}   (bits 15:13 must be 0)
//   0x67        CFG mix: a = mix_w, b = mix_r            (default 1/1)
//   0x68        CFG run_len (pattern 5, default 1)
//   0x69        CFG stride[15:0] (pattern 5, default 1)  /  0x6A  CFG stride[23:16] in a (b must be 0)
//   0x6B        START   ({b,a}=0). status 5 if not calibrated, a job/BIST runs, the engine is faulted, cfg words 0..6 were not all written
//               since the last RECAL, or the port has timed out. result = job id[15:0].
//   0x6C        CANCEL  ({b,a}=0). Faults the running job (error 7); like every engine fault it needs RECAL (0x5B) afterwards.
//   0x6D        SNAPSHOT ({b,a}=0): status 5 unless a job has finished (done && !busy); validates READ. result = generation.
//   0x6E        READ word a (0..61), b=0: 16 bit of the snapshot bus (layout below). status 5 without a valid snapshot or after a new START.
//   0x6F        QUERY a: 0 signature 0x0150, 1 live flags, 2 generation, 3 snapshot word count (62), 4 ABI version (1), 5 USER_MHZ
//               flags: bit0 calibrated, 1 USER alive, 2 busy, 3 done, 4 faulted, 5 port timeout, 6 snapshot valid, 7 BIST busy, 15:8 cfg words written
// Snapshot word map (16 bit words, word 0 first): 0 flags{rd_match(4) wr_match(3) faulted(2) done(1) busy(0)}, 1 error_code, 2..3 job id,
//   4..7 cnt_cycles, 8..11 cnt_cmds, 12..15 cnt_wbeats, 16..19 cnt_rbeats, 20..23 cnt_cmd_stall, 24..27 cnt_wd_stall,
//   28..31 lat_sum, 32..35 lat_samples, 36..37 lat_max, 38..45 ck_wr, 46..53 ck_rd, 54..61 ck_exp (little endian, word 0 = least significant).
module mem_bw_port #(
    parameter DEADLINE=2700000,
    parameter ROW_PAD=0,
    parameter CAL_GUARD_CYCLES=256,
    parameter [15:0] USER_MHZ=16'd100
)(
    input wire sys_clk,sys_reset_n,user_clk,user_reset_n,
    input wire command_start,input wire [7:0] opcode,a,b,
    output reg command_done,output reg [7:0] status,output reg [15:0] result,
    input wire calibrated,bist_busy,                 // USER domain
    output wire bw_busy,                             // USER domain: engine busy or about to start (bus owner select, BIST START gate)
    output wire [2:0] app_cmd,
    output wire app_cmd_en,
    output wire [26:0] app_addr,
    output wire [5:0] app_burst_number,
    output wire [127:0] app_write_data,
    output wire app_write_en,app_write_end,
    output wire [15:0] app_write_mask,
    input wire app_cmd_ready,app_write_ready,
    input wire [127:0] app_read_data,
    input wire app_read_valid,app_read_end
);
    // ---------------- USER side ----------------
    reg [1:0] request_sync; reg ack_toggle,pending_user,u_ready,u_start,u_cancel; reg [4:0] boot;
    reg request_toggle;
    reg [7:0] held_op;
    reg [31:0] next_job_h;   // job id of the request in flight (held with the config)
    reg [31:0] cfg_base,cfg_count,cfg_seed,next_job;
    reg [15:0] cfg_ctl; reg [7:0] cfg_mw,cfg_mr; reg [15:0] cfg_run; reg [23:0] cfg_stride;
    reg [31:0] u_base,u_count,u_seed,u_job; reg [15:0] u_ctl; reg [7:0] u_mw,u_mr; reg [15:0] u_run; reg [23:0] u_stride;
    wire e_busy,e_done,e_fault; wire [7:0] e_err; wire [31:0] e_jobid,e_latmax;
    wire [63:0] c_cyc,c_cmd,c_wb,c_rb,c_cs,c_ws,l_sum,l_n; wire [127:0] ck_wr,ck_rd,ck_exp; wire wr_ok,rd_ok;
    assign bw_busy=e_busy||u_start||pending_user;
    always @(posedge user_clk or negedge user_reset_n) begin
        if(!user_reset_n) begin request_sync<=0;ack_toggle<=0;pending_user<=0;u_start<=0;u_cancel<=0;u_ready<=0;boot<=0;
            u_base<=0;u_count<=0;u_seed<=0;u_job<=0;u_ctl<=0;u_mw<=0;u_mr<=0;u_run<=0;u_stride<=0; end
        else begin
            request_sync<={request_sync[0],request_toggle};u_start<=0;u_cancel<=0;
            if(!u_ready) begin if(boot<5'd16) boot<=boot+1'b1; else u_ready<=1; end
            else if(pending_user) begin pending_user<=0;ack_toggle<=request_sync[1]; end
            else if(request_sync[1]!=ack_toggle) begin
                pending_user<=1;
                if(held_op==8'h6b) begin
                    u_base<=cfg_base;u_count<=cfg_count;u_seed<=cfg_seed;u_job<=next_job_h;u_ctl<=cfg_ctl;
                    u_mw<=cfg_mw;u_mr<=cfg_mr;u_run<=cfg_run;u_stride<=cfg_stride;u_start<=1;
                end else if(held_op==8'h6c) u_cancel<=1;
            end
        end
    end
    mem_bw #(.PAIRED_WRITE(1),.APP_ROW_PAD(ROW_PAD)) engine(
        .clk(user_clk),.reset_n(user_reset_n),.calibrated(calibrated),.start(u_start),.cancel(u_cancel),
        .mode(u_ctl[1:0]),.pattern(u_ctl[4:2]),.region_log2(u_ctl[9:5]),.burst_log2(u_ctl[12:10]),
        .mix_w(u_mw),.mix_r(u_mr),.base_byte(u_base),.beat_count(u_count),.seed(u_seed),.job_id(u_job),
        .run_len(u_run),.stride(u_stride),
        .busy(e_busy),.done(e_done),.faulted(e_fault),.error_code(e_err),.accepted_job_id(e_jobid),
        .cnt_cycles(c_cyc),.cnt_cmds(c_cmd),.cnt_wbeats(c_wb),.cnt_rbeats(c_rb),.cnt_cmd_stall(c_cs),.cnt_wd_stall(c_ws),
        .lat_sum(l_sum),.lat_samples(l_n),.lat_max(e_latmax),.ck_wr(ck_wr),.ck_rd(ck_rd),.ck_exp(ck_exp),
        .ck_wr_match(wr_ok),.ck_rd_match(rd_ok),
        .app_burst_number(app_burst_number),.app_cmd(app_cmd),.app_cmd_en(app_cmd_en),.app_addr(app_addr),.app_cmd_ready(app_cmd_ready),
        .app_write_data(app_write_data),.app_write_en(app_write_en),.app_write_end(app_write_end),.app_write_mask(app_write_mask),
        .app_write_ready(app_write_ready),.app_read_data(app_read_data),.app_read_valid(app_read_valid),.app_read_end(app_read_end));

    // ---------------- SYS side ----------------
    wire [991:0] snap={ck_exp,ck_rd,ck_wr,e_latmax,l_n,l_sum,c_ws,c_cs,c_rb,c_wb,c_cmd,c_cyc,e_jobid,{8'b0,e_err},
                       {11'b0,rd_ok,wr_ok,e_fault,e_done,e_busy}};
    reg [10:0] cfg_written;
    reg [1:0] ack_sync,cal_sync,busy_sync,done_sync,fault_sync,bist_sync,ready_sync;
    reg [31:0] calibration_guard,deadline;
    reg pending_sys,settle,port_timeout,snapshot_valid;
    reg [15:0] generation;
    wire hold_busy=busy_sync[1]||bist_sync[1];
    wire [63:0] cfg_end={32'b0,cfg_base}+({32'b0,cfg_count}<<4);
    always @(posedge sys_clk or negedge sys_reset_n) begin
        if(!sys_reset_n) begin
            cfg_base<=0;cfg_count<=0;cfg_seed<=0;cfg_ctl<=0;cfg_mw<=8'd1;cfg_mr<=8'd1;cfg_run<=16'd1;cfg_stride<=24'd1;
            cfg_written<=0;next_job<=32'h00010000;next_job_h<=0;held_op<=0;request_toggle<=0;
            ack_sync<=0;cal_sync<=0;busy_sync<=0;done_sync<=0;fault_sync<=0;bist_sync<=0;ready_sync<=0;
            calibration_guard<=0;deadline<=0;pending_sys<=0;settle<=0;port_timeout<=0;snapshot_valid<=0;generation<=0;
            command_done<=0;status<=0;result<=0;
        end else begin
            command_done<=0;
            ack_sync<={ack_sync[0],ack_toggle};cal_sync<={cal_sync[0],calibrated};
            busy_sync<={busy_sync[0],e_busy};done_sync<={done_sync[0],e_done};fault_sync<={fault_sync[0],e_fault};
            bist_sync<={bist_sync[0],bist_busy};ready_sync<={ready_sync[0],u_ready};
            if(!cal_sync[1]) calibration_guard<=0; else if(calibration_guard<CAL_GUARD_CYCLES) calibration_guard<=calibration_guard+1'b1;
            if(pending_sys) begin
                deadline<=deadline+1'b1;
                if(ack_sync[1]==request_toggle) begin
                    if(!settle) settle<=1;
                    else begin pending_sys<=0;settle<=0;command_done<=1;status<=0;result<=next_job_h[15:0]; end
                end else if(deadline>=DEADLINE-1 || !ready_sync[1]) begin
                    pending_sys<=0;settle<=0;command_done<=1;status<=4;result<=0;port_timeout<=1;
                end
            end
            if(command_start&&!pending_sys) begin
                command_done<=1;status<=0;result<=0;
                case(opcode)
                    8'h60,8'h61,8'h62,8'h63,8'h64,8'h65,8'h66,8'h67,8'h68,8'h69,8'h6a: begin
                        if(busy_sync[1]||port_timeout) status<=5;
                        else if(opcode==8'h6a && b!=0) status<=3;
                        else if(opcode==8'h66 && {b,a}>16'h1fff) status<=3;
                        else begin
                            case(opcode)
                                8'h60: cfg_base[15:0]<={b,a};   8'h61: cfg_base[31:16]<={b,a};
                                8'h62: cfg_count[15:0]<={b,a};  8'h63: cfg_count[31:16]<={b,a};
                                8'h64: cfg_seed[15:0]<={b,a};   8'h65: cfg_seed[31:16]<={b,a};
                                8'h66: cfg_ctl<={b,a};
                                8'h67: begin cfg_mw<=a;cfg_mr<=b; end
                                8'h68: cfg_run<={b,a};
                                8'h69: cfg_stride[15:0]<={b,a};
                                8'h6a: cfg_stride[23:16]<=a;
                            endcase
                            cfg_written[opcode-8'h60]<=1;result<={b,a};snapshot_valid<=0;
                        end
                    end
                    8'h6b,8'h6c: begin
                        if({b,a}!=0) status<=3;
                        else if(port_timeout) status<=5;
                        else if(opcode==8'h6b && (!cal_sync[1]||calibration_guard<CAL_GUARD_CYCLES||!ready_sync[1]||hold_busy||fault_sync[1]||
                                 cfg_written[6:0]!=7'h7f)) status<=5;
                        else if(opcode==8'h6c && !busy_sync[1]) status<=5;
                        else begin
                            command_done<=0;pending_sys<=1;settle<=0;deadline<=0;held_op<=opcode;
                            request_toggle<=~request_toggle;
                            if(opcode==8'h6b) begin next_job_h<=next_job;next_job<=next_job+1'b1;snapshot_valid<=0; end
                        end
                    end
                    8'h6d: begin
                        if({b,a}!=0) status<=3;
                        else if(!(done_sync[1] && !busy_sync[1]) || port_timeout) status<=5;
                        else begin snapshot_valid<=1;generation<=generation+1'b1;result<=generation+1'b1; end
                    end
                    8'h6e: begin
                        if(b!=0||a>8'd61) status<=3;
                        else if(!snapshot_valid||busy_sync[1]||!done_sync[1]) status<=5;
                        else result<=snap[a*16+:16];
                    end
                    8'h6f: begin
                        if(b!=0) status<=3;
                        else case(a)
                            0: result<=16'h0150;
                            1: result<={cfg_written[7:0],bist_sync[1],snapshot_valid,port_timeout,fault_sync[1],done_sync[1],busy_sync[1],ready_sync[1],cal_sync[1]};
                            2: result<=generation;
                            3: result<=16'd62;
                            4: result<=16'd1;
                            5: result<=USER_MHZ;
                            default: status<=3;
                        endcase
                    end
                    default: status<=2;
                endcase
            end
        end
    end
endmodule
