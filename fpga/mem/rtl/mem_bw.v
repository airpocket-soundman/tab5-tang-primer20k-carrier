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
    parameter MIX_LAG=8
)(
    input wire clk,reset_n,calibrated,start,cancel,
    input wire [1:0] mode,
    input wire [2:0] pattern,
    input wire [4:0] region_log2,
    input wire [7:0] mix_w,mix_r,
    input wire [31:0] base_byte,beat_count,seed,job_id,
    output reg busy,done,faulted,
    output reg [7:0] error_code,
    output reg [31:0] accepted_job_id,
    output reg [63:0] cnt_cycles,cnt_cmds,cnt_wbeats,cnt_rbeats,cnt_cmd_stall,cnt_wd_stall,
    output reg [63:0] lat_sum,lat_samples,
    output reg [31:0] lat_max,
    output wire [127:0] ck_wr,ck_rd,ck_exp,
    output reg ck_wr_match,ck_rd_match,
    output wire [2:0] app_cmd,
    output wire app_cmd_en,
    output wire [26:0] app_addr,
    input wire app_cmd_ready,
    output wire [127:0] app_write_data,
    output wire app_write_en,app_write_end,
    output wire [15:0] app_write_mask,
    input wire app_write_ready,
    input wire [127:0] app_read_data,
    input wire app_read_valid,app_read_end
);
    // error_code: 0 ok, 1 not calibrated, 2 bad configuration, 3 no progress (command/write side),
    // 4 no progress with reads outstanding, 5 unexpected/ill-formed read data, 7 cancel, 8 calibration lost, 9 total deadline.

    // ---------------- registered configuration / start ----------------
    reg start_q,range_ok_q;
    reg [1:0] mode_q; reg [2:0] pat_q; reg [4:0] rl_q; reg [7:0] mw_q,mr_q;
    reg [31:0] base_q,count_q,seed_q,job_q;
    wire valid_cfg=base_byte[3:0]==4'd0 && base_byte[31:27]==5'd0 && beat_count!=32'd0 && beat_count<=32'd8388608 &&
        mode!=2'd3 && pattern<=3'd4 &&
        (mode!=2'd2 || (PAIRED_WRITE!=0 && mix_w!=8'd0 && mix_r!=8'd0)) &&
        (pattern<3'd3 || (region_log2>=5'd1 && region_log2<=5'd23));
    always @(posedge clk or negedge reset_n) begin
        if(!reset_n) begin start_q<=0;range_ok_q<=0;mode_q<=0;pat_q<=0;rl_q<=0;mw_q<=0;mr_q<=0;
            base_q<=0;count_q<=0;seed_q<=0;job_q<=0; end
        else begin start_q<=start;range_ok_q<=valid_cfg;mode_q<=mode;pat_q<=pattern;rl_q<=region_log2;
            mw_q<=mix_w;mr_q<=mix_r;base_q<=base_byte;count_q<=beat_count;seed_q<=seed;job_q<=job_id; end
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
    reg [4:0] sr;               // setup: sr[0] load, sr[1..3] address pipeline fill, armed afterwards
    reg armed,scat_bad_q;
    reg want_wc_q,want_rc_q,want_wd_q,blk_q;
    reg [1:0] skew;             // write commands issued minus write data beats issued (-1,0,1), PAIRED_WRITE=0 only
    reg run_wr; reg [7:0] run_left;
    wire accept=start_q && !busy && !faulted;

    // ---------------- native strobes ----------------
    wire en_ok=!blk_q && !cancel;
    wire fire_wc=app_cmd_ready && want_wc_q && ((PAIRED_WRITE!=0)?app_write_ready:1'b1) && en_ok;
    wire fire_rc=app_cmd_ready && want_rc_q && en_ok;
    wire fire_wd=(PAIRED_WRITE!=0)?fire_wc:(app_write_ready && want_wd_q && en_ok);
    assign app_cmd_en=fire_wc||fire_rc;
    assign app_write_en=fire_wd;
    assign app_write_end=fire_wd;
    assign app_write_mask=16'h0000;
    assign app_cmd={2'b00,want_rc_q};
    wire progress=fire_wc||fire_rc||fire_wd||app_read_valid;

    // ---------------- remaining-work counters (ge1/ge2 flags are registered) ----------------
    wire wc1,wc2,rc1,rc2,d1,d2,r1,r2,e1,e2;
    wire [23:0] n_wc=(m_wr||m_mx)?count_l[23:0]:24'd0;
    wire [23:0] n_rc=(m_rd||m_mx)?count_l[23:0]:24'd0;
    wire ld=sr[0];
    mem_bw_cnt c_wc(clk,reset_n,ld,n_wc,fire_wc,wc1,wc2);
    mem_bw_cnt c_rc(clk,reset_n,ld,n_rc,fire_rc,rc1,rc2);
    mem_bw_cnt c_d (clk,reset_n,ld,n_wc,fire_wd,d1,d2);
    mem_bw_cnt c_r (clk,reset_n,ld,n_rc,app_read_valid,r1,r2);
    wire e_v=armed && e1;
    mem_bw_cnt c_e (clk,reset_n,ld,count_l[23:0],e_v,e1,e2);
    wire idle_io=!wc1 && !rc1 && !d1 && !r1;

    // ---------------- address generators ----------------
    wire [26:0] wa_cur,ra_cur;
    wire fill=sr[1]||sr[2]||sr[3];
    mem_bw_agen wa(clk,reset_n,ld,fill||fire_wc,base_l[26:0],pat_l,rmask_l,seed_l,wa_cur);
    mem_bw_agen ra(clk,reset_n,ld,fill||fire_rc,base_l[26:0],pat_l,rmask_l,seed_l,ra_cur);
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
        ginit={lane0(s,32'h85EBCA6B),lane0(s,32'hB7E15162),lane0(s,32'h243F6A88),lane0(s,32'h9E3779B9)};
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
    wire nwc1=fire_wc?wc2:wc1;
    wire nrc1=fire_rc?rc2:rc1;
    wire nd1=fire_wd?d2:d1;
    wire [1:0] nskew=skew+{1'b0,fire_wc}+{2{fire_wd}};
    wire ok_c=(nskew!=2'b01);
    wire ok_d=!nskew[1];
    reg [23:0] lagc;           // write commands issued minus read commands issued
    wire lag_ok=(lagc>=MIX_LAG) || !wc1;
    wire can_w=wc1;
    wire can_r=rc1 && lag_ok;
    wire pick_w=can_w && (run_wr || !can_r);
    wire pick_r=can_r && (!run_wr || !can_w);
    wire go=armed && settled_q;
    reg lat_v_q;
    wire pipe_busy=wck_busy||rck_busy||eck_busy||e1||lat_v_q;

    // ---------------- control ----------------
    reg [31:0] wait_cycles; reg [63:0] elapsed; reg wait_hit_q,tot_hit_q,fin_q;
    reg [23:0] rd_out;
    wire rd_out_nz=|rd_out;
    wire bad_rd=app_read_valid && (!rd_out_nz || !app_read_end);
    task fail_job;
        input [7:0] code;
        begin busy<=0;done<=1;faulted<=1;error_code<=code;
            want_wc_q<=0;want_rc_q<=0;want_wd_q<=0;blk_q<=0;sr<=0;armed<=0;fin_q<=0;wait_hit_q<=0;tot_hit_q<=0; end
    endtask
    always @(posedge clk or negedge reset_n) begin
        if(!reset_n) begin
            busy<=0;done<=0;faulted<=0;error_code<=0;accepted_job_id<=0;
            m_wr<=0;m_rd<=0;m_mx<=0;pat_l<=0;rmask_l<=0;mw_l<=0;mr_l<=0;base_l<=0;count_l<=0;seed_l<=0;
            sr<=0;armed<=0;want_wc_q<=0;want_rc_q<=0;want_wd_q<=0;blk_q<=0;skew<=0;
            run_wr<=1;run_left<=0;wait_cycles<=0;elapsed<=0;wait_hit_q<=0;tot_hit_q<=0;fin_q<=0;
            ck_wr_match<=0;ck_rd_match<=0;
        end else if(cancel && busy) fail_job(8'd7);
        else if(accept) begin
            done<=0;error_code<=0;accepted_job_id<=job_q;ck_wr_match<=0;ck_rd_match<=0;
            sr<=0;armed<=0;want_wc_q<=0;want_rc_q<=0;want_wd_q<=0;blk_q<=0;fin_q<=0;
            wait_cycles<=0;elapsed<=0;wait_hit_q<=0;tot_hit_q<=0;
            m_wr<=(mode_q==2'd0);m_rd<=(mode_q==2'd1);m_mx<=(mode_q==2'd2);
            pat_l<=pat_q;rmask_l<=23'h7fffff>>(5'd23-rl_q);mw_l<=mw_q;mr_l<=mr_q;
            base_l<=base_q;count_l<=count_q;seed_l<=seed_q;
            if(!cal_q) begin done<=1;error_code<=8'd1; end
            else if(!range_ok_q) begin done<=1;error_code<=8'd2; end
            else begin busy<=1;sr<=5'b00001; end
        end else if(busy) begin
            elapsed<=elapsed+1'b1;
            wait_cycles<=progress?32'd0:wait_cycles+1'b1;
            wait_hit_q<=!progress && wait_cycles>=TIMEOUT_CYCLES-2;
            tot_hit_q<=elapsed>=TOTAL_TIMEOUT_CYCLES-2;
            if(!cal_q) fail_job(8'd8);
            else if(tot_hit_q) fail_job(8'd9);
            else if(bad_rd) fail_job(8'd5);
            else if(wait_hit_q && !progress) fail_job(rd_out_nz?8'd4:8'd3);
            else if(sr[1] && scat_bad_q) begin
                busy<=0;done<=1;error_code<=8'd2;sr<=0;armed<=0;
            end else begin
                sr<={sr[3:0],1'b0};
                if(sr[3]) armed<=1;
                if(sr[0]) begin run_wr<=1;run_left<=mw_l;skew<=0; end else skew<=nskew;
                blk_q<=(fire_wc||fire_rc||fire_wd) && m_mx;
                if(m_mx) begin
                    if(fire_wc && run_wr) begin
                        if(run_left==8'd1) begin run_wr<=0;run_left<=mr_l; end else run_left<=run_left-1'b1;
                    end else if(fire_rc && !run_wr) begin
                        if(run_left==8'd1) begin run_wr<=1;run_left<=mw_l; end else run_left<=run_left-1'b1;
                    end
                end
                if(!go) begin want_wc_q<=0;want_rc_q<=0;want_wd_q<=0; end
                else begin
                    want_wc_q<=m_mx?pick_w:(m_wr && nwc1 && (PAIRED_WRITE!=0 || ok_c));
                    want_rc_q<=m_mx?pick_r:(m_rd && nrc1);
                    want_wd_q<=(PAIRED_WRITE==0) && m_wr && nd1 && ok_d;
                end
                fin_q<=armed && idle_io && !pipe_busy;
                if(fin_q) begin
                    busy<=0;done<=1;want_wc_q<=0;want_rc_q<=0;want_wd_q<=0;
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
    wire want_wd_any=((PAIRED_WRITE!=0)?want_wc_q:want_wd_q) && !blk_q;
    always @(posedge clk or negedge reset_n) begin
        if(!reset_n) begin
            cnt_cycles<=0;cnt_cmds<=0;cnt_wbeats<=0;cnt_rbeats<=0;cnt_cmd_stall<=0;cnt_wd_stall<=0;
            lat_sum<=0;lat_samples<=0;lat_max<=0;tc_run<=0;lat_busy<=0;lat_v_q<=0;cyc<=0;lat_start<=0;lat_q<=0;
            lat_left<=0;lagc<=0;rd_out<=0;
        end else if(accept) begin
            cnt_cycles<=0;cnt_cmds<=0;cnt_wbeats<=0;cnt_rbeats<=0;cnt_cmd_stall<=0;cnt_wd_stall<=0;
            lat_sum<=0;lat_samples<=0;lat_max<=0;tc_run<=0;lat_busy<=0;lat_v_q<=0;cyc<=0;lagc<=0;rd_out<=0;
        end else if(busy) begin
            cyc<=cyc+1'b1;
            if(fire_wc||fire_rc) cnt_cmds<=cnt_cmds+1'b1;
            if(fire_wd) cnt_wbeats<=cnt_wbeats+1'b1;
            if(app_read_valid) cnt_rbeats<=cnt_rbeats+1'b1;
            if(first_fire) tc_run<=1;
            if(cnt_en) begin
                cnt_cycles<=cnt_cycles+1'b1;
                if(want_cmd_any && !app_cmd_ready) cnt_cmd_stall<=cnt_cmd_stall+1'b1;
                if(want_wd_any && !app_write_ready) cnt_wd_stall<=cnt_wd_stall+1'b1;
            end
            lagc<=lagc+fire_wc-fire_rc;
            if(fire_rc && !(app_read_valid && rd_out_nz)) rd_out<=rd_out+1'b1;
            else if(!fire_rc && app_read_valid && rd_out_nz) rd_out<=rd_out-1'b1;
            // read latency sampling: one command at a time is timestamped
            lat_v_q<=0;
            if(lat_busy && app_read_valid && lat_left==24'd0) begin
                lat_q<=cyc-lat_start;lat_v_q<=1;lat_busy<=0;
            end else if(lat_busy && app_read_valid) lat_left<=lat_left-1'b1;
            else if(!lat_busy && fire_rc) begin
                lat_busy<=1;lat_start<=cyc;lat_left<=rd_out-(app_read_valid?24'd1:24'd0);
            end
            if(lat_v_q) begin
                lat_sum<=lat_sum+lat_q;lat_samples<=lat_samples+1'b1;
                if(lat_q>lat_max) lat_max<=lat_q;
            end
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

// byte-address generator, 3-stage pipeline that shifts on every accepted command (and during the 3 fill cycles)
module mem_bw_agen(input wire clk,reset_n,load,shift,input wire [26:0] base,input wire [2:0] pattern,
    input wire [22:0] rmask,input wire [31:0] seed,output reg [26:0] cur);
    reg [23:0] idx; reg [31:0] xs; reg [22:0] sc; reg [26:0] p_q,a1;
    wire [22:0] i=idx[22:0];
    reg [26:0] p_n;
    wire [31:0] t1=xs^(xs<<13); wire [31:0] t2=t1^(t1>>17); wire [31:0] xs_n=t2^(t2<<5);
    always @* begin
        case(pattern)
            3'd1: p_n={i[22:10],i[2:0],i[9:3],4'b0000};
            3'd2: p_n={i[12:0],i[22:13],4'b0000};
            3'd3: p_n={xs[31:9]&rmask,4'b0000};
            3'd4: p_n={sc&rmask,4'b0000};
            default: p_n={i,4'b0000};
        endcase
    end
    always @(posedge clk or negedge reset_n) begin
        if(!reset_n) begin idx<=0;xs<=0;sc<=0;p_q<=0;a1<=0;cur<=0; end
        else if(load) begin idx<=0;xs<=(seed==32'd0)?32'h2545F491:seed;sc<=0;p_q<=0;a1<=0;cur<=0; end
        else if(shift) begin
            idx<=idx+1'b1;xs<=xs_n;sc<=sc+23'h4F1BBD;
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
