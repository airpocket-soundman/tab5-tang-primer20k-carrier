// DDR3 user-interface bandwidth measurement engine (USER clock domain).
// Design: docs/DDR3_冷起動_複数seed_soak手順_2026-11-04.md section B. Documentation: fpga/mem/BW_ENGINE.md.
// STATUS: simulation only. Not instantiated in mem_top, no host ABI, never run on hardware.
//
// Native Gowin DDR3 interface (1:4, BL8): one 128-bit beat per command, independent cmd_ready / wr_data_rdy,
// read data in order with rd_data_valid / rd_data_end, 27-bit app address.
//
// Jobs:  mode 0 write_stream, 1 read_stream, 2 mixed (mix_w writes / mix_r reads, repeated).
// Patterns (beat index i, byte address = (p(i)*16 + base) mod 128MiB):
//   0 seq              p = i
//   1 bank_interleave  bank = i[2:0] (byte[13:11]), column group = i[9:3] (byte[10:4]), row = i[22:10] (byte[26:14])
//   2 row_miss         row = i[12:0] (byte[26:14]), rest = i[22:13] (byte[13:4])  -> stride 16 KiB while i < 8192
//   3 lfsr             p = xorshift32 state[31:9] & mask(region_log2)  (may repeat addresses)
//   4 scatter          p = (i * 0x4F1BBD) mod 2^23 & mask(region_log2) (odd multiplier: collision free for beat_count <= 2^region_log2)
//   5 strided runs     runs of `run_len` consecutive commands, run starts `stride` beats apart (row crossing / same-bank row miss /
//                      bank rotation by the choice of stride; beat position = (r*stride + w*L) mod 2^23, r=cmd/run_len, w=cmd%run_len)
// Burst length: burst_log2 (0..6) selects L=2^burst_log2 beats per command; app_burst_number = L-1 (old Sipeed IP only, unverified on
//   hardware; the sample tester uses 7 = 8 beats and advances the address by 64 native units = 8 beats). Patterns are evaluated on the
//   beat index of the first beat of each command (low burst_log2 bits zero); beat_count and base_byte must be multiples of L resp. 16*L.
//   L>1 needs mode 0 (PAIRED_WRITE=1) or mode 1; mixed mode is L=1 only. rd_data_end is not checked for L>1 (IP behaviour unknown).
// Data: 4 independent xorshift32 lanes seeded from `seed`, one new 128-bit beat per accepted write (and per
// expected beat). No data comparison in the hot loop: rolling checksums ck_wr / ck_rd / ck_exp are compared once.
module mem_bw #(
    parameter TIMEOUT_CYCLES=8100000,
    parameter [63:0] TOTAL_TIMEOUT_CYCLES=64'd4860000000,
    // 1: write command and write data are issued together, only while both ready inputs are high (IPUG281 4.4.6).
    // 0: independent channels, at most one beat of skew between command and data counts (regression use only).
    parameter PAIRED_WRITE=1,
    parameter CALIBRATION_SETTLE_CYCLES=256,
    // 1: IP with 14 row bits (zero pad above the 13 row bits); same meaning as mem_bist.
    parameter APP_ROW_PAD=0,
    // mixed mode: a read command is only issued when at least this many more write commands than read commands
    // were issued (or all writes are issued). Read-after-write ordering is not assumed inside the IP.
    parameter MIX_LAG=8,
    // Native-enable structure (timing). 0: enables = IP ready flops & want_*_q & !blk_q & !cancel (original).
    // 1: the enables are taken from dedicated registered flops en_wc_q/en_rc_q/en_wb_q (= want & !blk, folded one cycle ahead), so that
    //    each enable is a small AND of the IP ready flops, one registered enable flop and !cancel (the same idea as mem_bist PIPELINE=4).
    //    Cycle behaviour is IDENTICAL to 0 (same cycle counters, stalls, latency); only the logic depth in front of the IP changes.
    // 2: additionally the wants are evaluated from the state of the CURRENT cycle (not the next one) and every accepted command / data beat
    //    blocks the following cycle (stale-want block), exactly like mem_bist PIPELINE=4: at most one command or data beat per TWO cycles.
    //    Cycle definitions are unchanged; the idle cycle after every acceptance shows up in cnt_cycles (see bw_model.py).
    parameter EN_PIPE=0,
    parameter SEED_ONE_LANE=0 // diagnostic opt-in: seed only one lane, preventing XOR-fold cancellation
)(
    input wire clk,reset_n,calibrated,start,cancel,
    input wire [1:0] mode,
    input wire [2:0] pattern,
    input wire [4:0] region_log2,
    input wire [7:0] mix_w,mix_r,
    input wire [31:0] base_byte,beat_count,seed,job_id,
    input wire [2:0] burst_log2,        // beats per command = 2^burst_log2, 0..6
    input wire [15:0] run_len,          // pattern 5: commands per run (>=1)
    input wire [23:0] stride,           // pattern 5: beats between run starts (< 2^23, multiple of L, >=1)
    output reg busy,done,faulted,
    output reg [7:0] error_code,
    output reg [31:0] accepted_job_id,
    output wire [63:0] cnt_cycles,cnt_cmds,cnt_wbeats,cnt_rbeats,cnt_cmd_stall,cnt_wd_stall,
    output wire [63:0] lat_sum,lat_samples,
    output wire [31:0] lat_max,
    output wire [127:0] ck_wr,ck_rd,ck_exp,
    output reg ck_wr_match,ck_rd_match,
    output wire [5:0] app_burst_number, // L-1, constant during a job
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
    // Next-cycle gate values (D inputs of en_wc_q/en_rc_q/en_wb_q), for a shared top-level enable stage (mem_top BW_EN_PIPE>=1):
    // app_cmd_en = cmd_ready & (gate_rc | gate_wc & write_ready), app_write_en = write_ready & (gate_wb | gate_wc & cmd_ready), with
    // gate_* the registered values of these D inputs and cancel folded in by the caller. Equal to the internal enables (PAIRED_WRITE=1).
    output wire gate_wc_d,gate_rc_d,gate_wb_d
);
    // error_code: 0 ok, 1 not calibrated, 2 bad configuration, 3 no progress (command/write side),
    // 4 no progress with reads outstanding, 5 unexpected/ill-formed read data, 7 cancel, 8 calibration lost, 9 total deadline.

    // ---------------- registered configuration / start ----------------
    reg start_q,range_ok_q;
    reg [1:0] mode_q; reg [2:0] pat_q; reg [4:0] rl_q; reg [7:0] mw_q,mr_q;
    reg [31:0] base_q,count_q,seed_q,job_q;
    reg [2:0] bl_q; reg [15:0] run_q; reg [23:0] stride_q;
    wire [6:0] lmask_in=(7'd1<<burst_log2)-7'd1;             // L-1
    wire valid_cfg=base_byte[3:0]==4'd0 && base_byte[31:27]==5'd0 && beat_count!=32'd0 && beat_count<=32'd8388608 &&
        mode!=2'd3 && pattern<=3'd5 &&
        (mode!=2'd2 || (PAIRED_WRITE!=0 && mix_w!=8'd0 && mix_r!=8'd0)) &&
        (pattern<3'd3 || pattern>3'd4 || (region_log2>=5'd1 && region_log2<=5'd23)) &&
        burst_log2<=3'd6 &&
        (burst_log2==3'd0 || ((mode==2'd1 || (mode==2'd0 && PAIRED_WRITE!=0)) &&
            (beat_count[5:0]&lmask_in[5:0])==6'd0 && ((base_byte[9:4]&lmask_in[5:0])==6'd0))) &&
        (pattern!=3'd5 || (run_len!=16'd0 && stride!=24'd0 && stride<=24'h7fffff && (stride[5:0]&lmask_in[5:0])==6'd0));
    always @(posedge clk or negedge reset_n) begin
        if(!reset_n) begin start_q<=0;range_ok_q<=0;mode_q<=0;pat_q<=0;rl_q<=0;mw_q<=0;mr_q<=0;
            base_q<=0;count_q<=0;seed_q<=0;job_q<=0;bl_q<=0;run_q<=0;stride_q<=0; end
        else begin start_q<=start;range_ok_q<=valid_cfg;mode_q<=mode;pat_q<=pattern;rl_q<=region_log2;
            mw_q<=mix_w;mr_q<=mix_r;base_q<=base_byte;count_q<=beat_count;seed_q<=seed;job_q<=job_id;
            bl_q<=burst_log2;run_q<=run_len;stride_q<=stride; end
    end
    reg cal_q;
    always @(posedge clk or negedge reset_n) if(!reset_n) cal_q<=0; else cal_q<=calibrated;
    reg [15:0] settle_count; reg settled_q;
    always @(posedge clk or negedge reset_n) begin
        if(!reset_n) begin settle_count<=0;settled_q<=0; end
        else begin
            if(!cal_q) settle_count<=0; else if(settle_count<CALIBRATION_SETTLE_CYCLES) settle_count<=settle_count+1'b1;
            settled_q<=cal_q && settle_count>=CALIBRATION_SETTLE_CYCLES;
        end
    end

    // ---------------- job state ----------------
    reg m_wr,m_rd,m_mx;
    reg [2:0] pat_l; reg [22:0] rmask_l; reg [7:0] mw_l,mr_l;
    reg [31:0] base_l,count_l,seed_l;
    reg [2:0] bl_l; reg [15:0] run_l; reg [23:0] stride_l; reg [23:0] ncmd_l; reg [5:0] bnum_l;
    reg want_wb_q; reg [5:0] wb_left;   // continuation write beats (2..L of the current write command), PAIRED_WRITE=1 only
    assign app_burst_number=bnum_l;
    reg [4:0] sr;               // setup: sr[0] load, sr[1..3] address pipeline fill, armed afterwards
    reg armed,scat_bad_q;
    reg want_wc_q,want_rc_q,want_wd_q,blk_q;
    reg en_wc_q,en_rc_q,en_wb_q,en_wd_q;   // EN_PIPE>=1: want & !blk, registered
    reg [1:0] skew;             // write commands issued minus write data beats issued (-1,0,1), PAIRED_WRITE=0 only
    reg run_wr; reg [7:0] run_left;
    wire accept=start_q && !busy && !faulted;

    // ---------------- native strobes ----------------
    // *_n: the same strobes without the cancel term. They are used for the next-state logic of the control registers, which are all
    // overridden by fail_job in a cancel cycle (cancel && busy is the first branch), so the long cancel -> state paths are not needed.
    // The counters, address generators and data/checksum pipelines use the real strobes (with !cancel).
    wire fire_wc_n=(EN_PIPE>=1)?(app_cmd_ready && en_wc_q && ((PAIRED_WRITE!=0)?app_write_ready:1'b1)):
        (app_cmd_ready && want_wc_q && ((PAIRED_WRITE!=0)?app_write_ready:1'b1) && !blk_q);
    wire fire_rc_n=(EN_PIPE>=1)?(app_cmd_ready && en_rc_q):(app_cmd_ready && want_rc_q && !blk_q);
    wire fire_wb_n=(PAIRED_WRITE!=0) && ((EN_PIPE>=1)?(app_write_ready && en_wb_q):(app_write_ready && want_wb_q && !blk_q));
    wire fire_wd_n=(PAIRED_WRITE!=0)?(fire_wc_n||fire_wb_n):((EN_PIPE>=1)?(app_write_ready && en_wd_q):(app_write_ready && want_wd_q && !blk_q));
    wire fire_wc=fire_wc_n && !cancel;
    wire fire_rc=fire_rc_n && !cancel;
    wire fire_wb=fire_wb_n && !cancel;
    wire fire_wd=fire_wd_n && !cancel;
    assign app_cmd_en=fire_wc||fire_rc;
    assign app_write_en=fire_wd;
    assign app_write_end=fire_wd;
    assign app_write_mask=16'h0000;
    assign app_cmd={2'b00,want_rc_q};
    wire progress=fire_wc||fire_rc||fire_wd||app_read_valid;
    wire progress_n=fire_wc_n||fire_rc_n||fire_wd_n||app_read_valid;

    // ---------------- remaining-work counters (ge1/ge2 flags are registered) ----------------
    wire wc1,wc2,rc1,rc2,d1,d2,r1,r2,e1,e2;
    wire [23:0] n_wc=(m_wr||m_mx)?ncmd_l:24'd0;          // commands
    wire [23:0] n_rc=(m_rd||m_mx)?ncmd_l:24'd0;
    wire [23:0] n_wd=(m_wr||m_mx)?count_l[23:0]:24'd0;   // data beats
    wire [23:0] n_rd=(m_rd||m_mx)?count_l[23:0]:24'd0;
    wire ld=sr[0];
    mem_bw_cnt c_wc(clk,reset_n,ld,n_wc,fire_wc,wc1,wc2);
    mem_bw_cnt c_rc(clk,reset_n,ld,n_rc,fire_rc,rc1,rc2);
    mem_bw_cnt c_d (clk,reset_n,ld,n_wd,fire_wd,d1,d2);
    mem_bw_cnt c_r (clk,reset_n,ld,n_rd,app_read_valid,r1,r2);
    wire e_v=armed && e1;
    mem_bw_cnt c_e (clk,reset_n,ld,count_l[23:0],e_v,e1,e2);
    wire idle_io=!wc1 && !rc1 && !d1 && !r1;

    // ---------------- address generators ----------------
    wire [26:0] wa_cur,ra_cur;
    wire fill=sr[1]||sr[2]||sr[3];
    mem_bw_agen wa(clk,reset_n,ld,fill||fire_wc,base_l[26:0],pat_l,rmask_l,seed_l,bl_l,run_l,stride_l,wa_cur);
    mem_bw_agen ra(clk,reset_n,ld,fill||fire_rc,base_l[26:0],pat_l,rmask_l,seed_l,bl_l,run_l,stride_l,ra_cur);
    wire [26:0] byte_addr=want_rc_q?ra_cur:wa_cur;
    wire [25:0] lw=byte_addr[26:1];
    assign app_addr=(APP_ROW_PAD!=0)?{lw[12:10],1'b0,lw[25:13],lw[9:0]}:{1'b0,lw[12:10],lw[25:13],lw[9:0]};

    // ---------------- data generators / checksums ----------------
    function [31:0] xs32;
        input [31:0] x; reg [31:0] t;
        begin t=x^(x<<13); t=t^(t>>17); xs32=t^(t<<5); end
    endfunction
    function [127:0] gnext;
        input [127:0] d;
        gnext={xs32(d[127:96]),xs32(d[95:64]),xs32(d[63:32]),xs32(d[31:0])};
    endfunction
    function [31:0] lane0;
        input [31:0] s,k; reg [31:0] v;
        begin v=s^k; lane0=(v==32'd0)?k:v; end
    endfunction
    function [127:0] ginit;
        input [31:0] s;
        ginit={lane0(SEED_ONE_LANE?32'd0:s,32'h85EBCA6B),lane0(SEED_ONE_LANE?32'd0:s,32'hB7E15162),lane0(SEED_ONE_LANE?32'd0:s,32'h243F6A88),lane0(s,32'h9E3779B9)};
    endfunction
    reg [127:0] wdata,edata;
    always @(posedge clk or negedge reset_n) begin
        if(!reset_n) begin wdata<=0;edata<=0; end
        else begin
            if(ld) begin wdata<=ginit(seed_l);edata<=ginit(seed_l); end
            else begin
                if(fire_wd) wdata<=gnext(wdata);
                if(e_v) edata<=gnext(edata);
            end
        end
    end
    assign app_write_data=wdata;
    wire wck_busy,rck_busy,eck_busy;
    mem_bw_ck wck(clk,reset_n,accept,fire_wd,wdata,ck_wr,wck_busy);
    mem_bw_ck rck(clk,reset_n,accept,app_read_valid,app_read_data,ck_rd,rck_busy);
    mem_bw_ck eck(clk,reset_n,accept,e_v,edata,ck_exp,eck_busy);
    reg wr_eq_q,rd_eq_q;
    always @(posedge clk) begin wr_eq_q<=(ck_wr==ck_exp); rd_eq_q<=(ck_rd==ck_exp); end

    // ---------------- request arbitration (registered wants) ----------------
    wire nwc1=fire_wc_n?wc2:wc1;
    wire nrc1=fire_rc_n?rc2:rc1;
    wire nd1=fire_wd_n?d2:d1;
    wire [5:0] nwb=fire_wc_n?bnum_l:(fire_wb_n?wb_left-6'd1:wb_left);   // continuation beats still owed after this cycle
    wire nwb_z=(PAIRED_WRITE!=0)?(nwb==6'd0):1'b1;
    wire [1:0] nskew=skew+{1'b0,fire_wc_n}+{2{fire_wd_n}};
    wire ok_c=(nskew!=2'b01);
    wire ok_d=!nskew[1];
    reg [23:0] lagc;           // write commands issued minus read commands issued
    wire lag_ok=(lagc>=MIX_LAG) || !wc1;
    wire can_w=wc1;
    wire can_r=rc1 && lag_ok;
    wire pick_w=can_w && (run_wr || !can_r);
    wire pick_r=can_r && (!run_wr || !can_w);
    wire go=armed && settled_q;
    // wants for the next cycle. EN_PIPE=2 evaluates them from the current state (the fire of this cycle is not yet visible).
    wire s_wc1=(EN_PIPE>=2)?wc1:nwc1, s_rc1=(EN_PIPE>=2)?rc1:nrc1, s_d1=(EN_PIPE>=2)?d1:nd1;
    wire [5:0] s_wb=(EN_PIPE>=2)?wb_left:nwb;
    wire s_wb_z=(PAIRED_WRITE!=0)?(s_wb==6'd0):1'b1;
    wire [1:0] s_skew=(EN_PIPE>=2)?skew:nskew;
    wire s_ok_c=(s_skew!=2'b01), s_ok_d=!s_skew[1];
    wire nx_wb=(PAIRED_WRITE!=0) && m_wr && !s_wb_z;
    wire nx_wc=m_mx?pick_w:(m_wr && s_wc1 && s_wb_z && (PAIRED_WRITE!=0 || s_ok_c));
    wire nx_rc=m_mx?pick_r:(m_rd && s_rc1);
    wire nx_wd=(PAIRED_WRITE==0) && m_wr && s_d1 && s_ok_d;
    wire fire_any=fire_wc_n||fire_rc_n||fire_wd_n;
    wire stale=(EN_PIPE>=2)?fire_any:(fire_any && m_mx);   // blk_q of the next cycle
    reg lat_v_q;
    wire pipe_busy=wck_busy||rck_busy||eck_busy||e1||lat_v_q;

    // ---------------- control ----------------
    reg [31:0] wait_cycles; reg [63:0] elapsed; reg wait_hit_q,tot_hit_q,fin_q;
    reg [23:0] rd_out;
    wire rd_out_nz=|rd_out;
    wire bad_rd=app_read_valid && (!rd_out_nz || (!app_read_end && bl_l==3'd0));
    wire fail_c=!cal_q || tot_hit_q || bad_rd || (wait_hit_q && !progress_n);
    wire gate_ok=busy && !cancel && !fail_c && !(sr[1] && scat_bad_q) && go && !fin_q;
    wire en_wb_d=gate_ok && nx_wb && !stale;
    wire en_wc_d=gate_ok && nx_wc && !stale;
    wire en_rc_d=gate_ok && nx_rc && !stale;
    wire en_wd_d=gate_ok && nx_wd && !stale;
    assign gate_wc_d=en_wc_d;
    assign gate_rc_d=en_rc_d;
    assign gate_wb_d=en_wb_d;
    task fail_job;
        input [7:0] code;
        begin busy<=0;done<=1;faulted<=1;error_code<=code;
            want_wc_q<=0;want_rc_q<=0;want_wd_q<=0;want_wb_q<=0;en_wc_q<=0;en_rc_q<=0;en_wb_q<=0;en_wd_q<=0;blk_q<=0;sr<=0;armed<=0;fin_q<=0;wait_hit_q<=0;tot_hit_q<=0; end
    endtask
    always @(posedge clk or negedge reset_n) begin
        if(!reset_n) begin
            busy<=0;done<=0;faulted<=0;error_code<=0;accepted_job_id<=0;
            m_wr<=0;m_rd<=0;m_mx<=0;pat_l<=0;rmask_l<=0;mw_l<=0;mr_l<=0;base_l<=0;count_l<=0;seed_l<=0;
            sr<=0;armed<=0;want_wc_q<=0;want_rc_q<=0;want_wd_q<=0;want_wb_q<=0;en_wc_q<=0;en_rc_q<=0;en_wb_q<=0;en_wd_q<=0;blk_q<=0;skew<=0;
            bl_l<=0;run_l<=0;stride_l<=0;ncmd_l<=0;bnum_l<=0;wb_left<=0;
            run_wr<=1;run_left<=0;wait_cycles<=0;elapsed<=0;wait_hit_q<=0;tot_hit_q<=0;fin_q<=0;
            ck_wr_match<=0;ck_rd_match<=0;
        end else if(cancel && busy) fail_job(8'd7);
        else if(accept) begin
            done<=0;error_code<=0;accepted_job_id<=job_q;ck_wr_match<=0;ck_rd_match<=0;
            sr<=0;armed<=0;want_wc_q<=0;want_rc_q<=0;want_wd_q<=0;want_wb_q<=0;en_wc_q<=0;en_rc_q<=0;en_wb_q<=0;en_wd_q<=0;blk_q<=0;fin_q<=0;wb_left<=0;
            bl_l<=bl_q;run_l<=run_q;stride_l<=stride_q;ncmd_l<=count_q[23:0]>>bl_q;bnum_l<=(6'd1<<bl_q)-6'd1;
            wait_cycles<=0;elapsed<=0;wait_hit_q<=0;tot_hit_q<=0;
            m_wr<=(mode_q==2'd0);m_rd<=(mode_q==2'd1);m_mx<=(mode_q==2'd2);
            pat_l<=pat_q;rmask_l<=23'h7fffff>>(5'd23-rl_q);mw_l<=mw_q;mr_l<=mr_q;
            base_l<=base_q;count_l<=count_q;seed_l<=seed_q;
            if(!cal_q) begin done<=1;error_code<=8'd1; end
            else if(!range_ok_q) begin done<=1;error_code<=8'd2; end
            else begin busy<=1;sr<=5'b00001; end
        end else if(busy) begin
            elapsed<=elapsed+1'b1;
            wait_cycles<=progress_n?32'd0:wait_cycles+1'b1;
            wait_hit_q<=!progress_n && wait_cycles>=TIMEOUT_CYCLES-2;
            tot_hit_q<=elapsed>=TOTAL_TIMEOUT_CYCLES-2;
            if(!cal_q) fail_job(8'd8);
            else if(tot_hit_q) fail_job(8'd9);
            else if(bad_rd) fail_job(8'd5);
            else if(wait_hit_q && !progress_n) fail_job(rd_out_nz?8'd4:8'd3);
            else if(sr[1] && scat_bad_q) begin
                busy<=0;done<=1;error_code<=8'd2;sr<=0;armed<=0;
            end else begin
                sr<={sr[3:0],1'b0};
                if(sr[3]) armed<=1;
                if(sr[0]) begin run_wr<=1;run_left<=mw_l;skew<=0; end else skew<=nskew;
                wb_left<=nwb;
                blk_q<=stale;
                if(m_mx) begin
                    if(fire_wc_n && run_wr) begin
                        if(run_left==8'd1) begin run_wr<=0;run_left<=mr_l; end else run_left<=run_left-1'b1;
                    end else if(fire_rc_n && !run_wr) begin
                        if(run_left==8'd1) begin run_wr<=1;run_left<=mw_l; end else run_left<=run_left-1'b1;
                    end
                end
                if(!go) begin want_wc_q<=0;want_rc_q<=0;want_wd_q<=0;want_wb_q<=0;en_wc_q<=0;en_rc_q<=0;en_wb_q<=0;en_wd_q<=0; end
                else begin
                    want_wb_q<=nx_wb;
                    want_wc_q<=nx_wc;
                    want_rc_q<=nx_rc;
                    want_wd_q<=nx_wd;
                    en_wb_q<=en_wb_d;
                    en_wc_q<=en_wc_d;
                    en_rc_q<=en_rc_d;
                    en_wd_q<=en_wd_d;
                end
                fin_q<=armed && idle_io && !pipe_busy;
                if(fin_q) begin
                    busy<=0;done<=1;want_wc_q<=0;want_rc_q<=0;want_wd_q<=0;want_wb_q<=0;en_wc_q<=0;en_rc_q<=0;en_wb_q<=0;en_wd_q<=0;
                    ck_wr_match<=m_wr?wr_eq_q:(m_mx?wr_eq_q:1'b0);
                    ck_rd_match<=(m_rd||m_mx)?rd_eq_q:1'b0;
                end
            end
        end
    end
    always @(posedge clk) scat_bad_q<=(pat_l==3'd4) && (count_l[23:0]>{1'b0,rmask_l}+24'd1);

    // ---------------- counters, latency sampling ----------------
    reg tc_run,lat_busy;
    reg [31:0] cyc,lat_start,lat_q;
    reg [23:0] lat_left;
    wire first_fire=(fire_wc||fire_rc) && !tc_run;
    wire cnt_en=(tc_run||first_fire) && !idle_io;
    wire want_cmd_any=(want_wc_q||want_rc_q) && !blk_q;
    wire want_wd_any=((PAIRED_WRITE!=0)?(want_wc_q||want_wb_q):want_wd_q) && !blk_q;
    // 64-bit statistics: 16-bit segments with registered carries (events counted in busy only; the carries ripple on after busy falls
    // and are settled a few cycles later, long before done is visible to the LINK side). Cleared by accept.
    wire cb=busy;
    mem_bw_ctr k_cyc(clk,reset_n,accept,cb&&cnt_en,cnt_cycles);
    mem_bw_ctr k_cmd(clk,reset_n,accept,cb&&(fire_wc||fire_rc),cnt_cmds);
    mem_bw_ctr k_wb (clk,reset_n,accept,cb&&fire_wd,cnt_wbeats);
    mem_bw_ctr k_rb (clk,reset_n,accept,cb&&app_read_valid,cnt_rbeats);
    mem_bw_ctr k_cs (clk,reset_n,accept,cb&&cnt_en&&want_cmd_any&&!app_cmd_ready,cnt_cmd_stall);
    mem_bw_ctr k_ws (clk,reset_n,accept,cb&&cnt_en&&want_wd_any&&!app_write_ready,cnt_wd_stall);
    mem_bw_ctr k_ls (clk,reset_n,accept,cb&&lat_v_q,lat_samples);
    mem_bw_acc k_lsum(clk,reset_n,accept,cb&&lat_v_q,lat_q,lat_sum);
    reg [31:0] lat_max_r; assign lat_max=lat_max_r;
    always @(posedge clk or negedge reset_n) begin
        if(!reset_n) begin
            lat_max_r<=0;tc_run<=0;lat_busy<=0;lat_v_q<=0;cyc<=0;lat_start<=0;lat_q<=0;
            lat_left<=0;lagc<=0;rd_out<=0;
        end else if(accept) begin
            lat_max_r<=0;tc_run<=0;lat_busy<=0;lat_v_q<=0;cyc<=0;lagc<=0;rd_out<=0;
        end else if(busy) begin
            cyc<=cyc+1'b1;
            if(first_fire) tc_run<=1;
            lagc<=lagc+fire_wc-fire_rc;
            rd_out<=rd_out+(fire_rc?{18'd0,bnum_l}+24'd1:24'd0)-((app_read_valid && rd_out_nz)?24'd1:24'd0);   // outstanding read BEATS
            // read latency sampling: one command at a time is timestamped
            lat_v_q<=0;
            if(lat_busy && app_read_valid && lat_left==24'd0) begin
                lat_q<=cyc-lat_start;lat_v_q<=1;lat_busy<=0;
            end else if(lat_busy && app_read_valid) lat_left<=lat_left-1'b1;
            else if(!lat_busy && fire_rc) begin
                lat_busy<=1;lat_start<=cyc;lat_left<=rd_out-(app_read_valid?24'd1:24'd0);
            end
            if(lat_v_q) begin
                if(lat_q>lat_max_r) lat_max_r<=lat_q;
            end
        end
    end
endmodule

// 64-bit event counter: four 16-bit segments, registered carries between them (value settles <= 3 cycles after the last event)
module mem_bw_ctr(input wire clk,reset_n,clear,inc,output wire [63:0] q);
    reg [15:0] s0,s1,s2,s3; reg c0,c1,c2;
    assign q={s3,s2,s1,s0};
    always @(posedge clk or negedge reset_n) begin
        if(!reset_n) begin s0<=0;s1<=0;s2<=0;s3<=0;c0<=0;c1<=0;c2<=0; end
        else if(clear) begin s0<=0;s1<=0;s2<=0;s3<=0;c0<=0;c1<=0;c2<=0; end
        else begin
            if(inc) s0<=s0+1'b1;
            c0<=inc && (s0==16'hffff);
            if(c0) s1<=s1+1'b1;
            c1<=c0 && (s1==16'hffff);
            if(c1) s2<=s2+1'b1;
            c2<=c1 && (s2==16'hffff);
            if(c2) s3<=s3+1'b1;
        end
    end
endmodule

// 64-bit accumulator of a 32-bit value: 32-bit low sum with registered carry into a 32-bit high counter (two 16-bit segments)
module mem_bw_acc(input wire clk,reset_n,clear,add_en,input wire [31:0] add,output wire [63:0] q);
    reg [31:0] lo; reg [15:0] h0,h1; reg c,ch;
    assign q={h1,h0,lo};
    wire [32:0] sum={1'b0,lo}+{1'b0,add};
    always @(posedge clk or negedge reset_n) begin
        if(!reset_n) begin lo<=0;h0<=0;h1<=0;c<=0;ch<=0; end
        else if(clear) begin lo<=0;h0<=0;h1<=0;c<=0;ch<=0; end
        else begin
            if(add_en) lo<=sum[31:0];
            c<=add_en && sum[32];
            if(c) h0<=h0+1'b1;
            ch<=c && (h0==16'hffff);
            if(ch) h1<=h1+1'b1;
        end
    end
endmodule

// remaining-beat counter with registered >=1 / >=2 flags (no wide compare after the fire strobe)
module mem_bw_cnt(input wire clk,reset_n,ld,input wire [23:0] ldv,input wire dec,output reg ge1,ge2);
    reg [23:0] rem;
    wire ge3=(|rem[23:2])||(rem[1]&&rem[0]);
    always @(posedge clk or negedge reset_n) begin
        if(!reset_n) begin rem<=0;ge1<=0;ge2<=0; end
        else if(ld) begin rem<=ldv;ge1<=|ldv;ge2<=|ldv[23:1]; end
        else if(dec && ge1) begin rem<=rem-1'b1;ge1<=ge2;ge2<=ge3; end
    end
endmodule

// byte-address generator, 3-stage pipeline that shifts on every accepted command (and during the 3 fill cycles).
// State advances per COMMAND: idx by L=2^bl beats; scatter counter by one command; strided-run position by L or to the next run start.
module mem_bw_agen(input wire clk,reset_n,load,shift,input wire [26:0] base,input wire [2:0] pattern,
    input wire [22:0] rmask,input wire [31:0] seed,input wire [2:0] bl,input wire [15:0] run_len,input wire [23:0] stride,
    output reg [26:0] cur);
    reg [23:0] idx; reg [31:0] xs; reg [22:0] sc; reg [26:0] p_q,a1;
    reg [22:0] pos,rstart; reg [15:0] rleft;
    wire [22:0] i=idx[22:0];
    wire [22:0] lmask=~((23'd1<<bl)-23'd1);
    wire [22:0] step=23'd1<<bl;
    wire [22:0] nstart=rstart+stride[22:0];
    reg [26:0] p_n;
    wire [31:0] t1=xs^(xs<<13); wire [31:0] t2=t1^(t1>>17); wire [31:0] xs_n=t2^(t2<<5);
    always @* begin
        case(pattern)
            3'd1: p_n={i[22:10],i[2:0],i[9:3],4'b0000};
            3'd2: p_n={i[12:0],i[22:13],4'b0000};
            3'd3: p_n={xs[31:9]&rmask&lmask,4'b0000};
            3'd4: p_n={(sc&(rmask>>bl))<<bl,4'b0000};
            3'd5: p_n={pos,4'b0000};
            default: p_n={i,4'b0000};
        endcase
    end
    always @(posedge clk or negedge reset_n) begin
        if(!reset_n) begin idx<=0;xs<=0;sc<=0;p_q<=0;a1<=0;cur<=0;pos<=0;rstart<=0;rleft<=0; end
        else if(load) begin idx<=0;xs<=(seed==32'd0)?32'h2545F491:seed;sc<=0;p_q<=0;a1<=0;cur<=0;pos<=0;rstart<=0;rleft<=run_len; end
        else if(shift) begin
            idx<=idx+{1'b0,step};xs<=xs_n;sc<=sc+23'h4F1BBD;
            if(rleft==16'd1) begin rstart<=nstart;pos<=nstart;rleft<=run_len; end
            else begin pos<=pos+step;rleft<=rleft-1'b1; end
            p_q<=p_n;a1<=p_q+base;cur<=a1;
        end
    end
endmodule

// rolling checksum: a += fold, b = rotl1(b) ^ fold, fold = d[127:64]^d[63:0]; 2 pipeline stages after input capture
module mem_bw_ck(input wire clk,reset_n,clear,v,input wire [127:0] d,output wire [127:0] ck,output wire busy);
    reg [127:0] d1; reg v1,v2; reg [63:0] f,a,b;
    assign ck={b,a};
    assign busy=v1||v2;
    always @(posedge clk or negedge reset_n) begin
        if(!reset_n) begin d1<=0;v1<=0;v2<=0;f<=0;a<=0;b<=0; end
        else if(clear) begin v1<=0;v2<=0;a<=0;b<=0; end
        else begin
            d1<=d;v1<=v;
            f<=d1[127:64]^d1[63:0];v2<=v1;
            if(v2) begin a<=a+f;b<={b[62:0],b[63]}^f; end
        end
    end
endmodule
