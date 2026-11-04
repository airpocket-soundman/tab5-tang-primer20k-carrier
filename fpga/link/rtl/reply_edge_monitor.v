// Diagnostic-only per-reply edge monitor for the conditioned reply clock (v2).
//
// Runs in the 216MHz sampler domain next to reply_clock_filter. It observes the
// filter's one-tick strobes and never drives clean_clk, fault or any serializer
// input, so the reply datapath is unchanged.
//
// WINDOW   offer start ((fast_offer && dir) synchronized HIGH) -> raw DIR LOW
//          (or a ~9.7ms safety timeout). At window end a snapshot is registered
//          and snap_toggle flips (bundled-data toggle). The SYS domain copies the
//          snapshot after a 2FF-synchronized toggle change; the snapshot registers
//          do not change again until the next window end.
// VALID    the data-valid interval inside the window: from offer start until the
//          expect_edges-th ACCEPTED rise (that rise is the last byte the
//          serializer outputs) or, earlier, the serializer's synchronized done
//          (abort/error). Everything after it is TAIL: in continuous RX the host
//          keeps clocking until its ISR lease closes, so tail rises are normal
//          and never count as excess.
//
// Counted inside VALID only (so a healthy reply gives all-zero anomaly counters):
//   pre       accepted rises (== bytes consumed by the serializer, == expect when
//             the interval completed by count)
//   reject    qualified rises inside the 5-sample cooldown (also trips fault)
//   drop      qualified rises swallowed after a fault inside the window
//   runt      one-sample excursions rejected by the 2-sample qualification
//   fall      qualified falls
//   min_high/min_low  shortest qualified HIGH/LOW run (sampler ticks, 4.63ns)
//   sp_min/sp_max/sp_jump  rise-to-rise spacing of accepted rises (ticks), and the
//             number of times it stepped by >=4 ticks from the previous spacing
//             (an extra or missing edge that the filter still accepted)
//   ticks     ticks from the first accepted rise to the end of VALID
//   first_pos/first_kind  accepted-rise count when the first anomaly was seen
//             (the anomaly sits after byte #first_pos) and its kind:
//             1 reject  2 drop  3 runt  4 spacing jump   (first_pos=0xFFF: none)
// Counted after VALID:
//   post      accepted rises after the interval (host tail clocking)
//   tail_noise  reject+drop+runt after the interval
//
// snap_flags: [0] serializer done seen   [1] serializer error   [2] filter fault
//             [3] timeout close          [4] counter saturated  [5] no edges at all
//             [6] VALID completed by count (expect_edges accepted rises seen)
//             [7] valid snapshot (0 after reset)
// A pulse narrower than the 216MHz sampling can alias; these counters are not an
// analog measurement. Spacing saturates at 255 ticks (below ~0.85MHz).
module reply_edge_monitor #(parameter TIMEOUT_BIT = 21)(
    input wire clk,reset_n,
    input wire window_async,dir_async,
    input wire [11:0] expect_edges,expect_last,
    input wire ev_accept,ev_reject,ev_drop,ev_runt,ev_fall,filter_fault,
    input wire ser_done,ser_error,
    input wire [11:0] ser_done_index,
    output reg snap_toggle,
    output reg [11:0] snap_pre,snap_post,snap_fall,snap_expect,snap_done_index,snap_first_pos,
    output reg [7:0] snap_reject,snap_drop,snap_runt,snap_tail_noise,snap_min_high,snap_min_low,
    output reg [7:0] snap_sp_min,snap_sp_max,snap_sp_jump,snap_flags,
    output reg [23:0] snap_ticks,
    output reg [2:0] snap_first_kind
);
    (* ASYNC_REG="TRUE" *) reg [1:0] win_s,dir_s,done_s,err_s;
    reg open,vact,vend_cnt,first,first_none,fault_seen,sat_seen,done_seen,err_seen;
    reg [11:0] pre,post,fall_cnt,exp_l,last_l,first_pos;
    reg [7:0] rej,drp,rnt,tailn,min_h,min_l,run_len;
    reg [2:0] first_kind;
    reg acc_last;
    // 216MHz timing: wide carry chains are too slow. Low byte + registered carry into a high counter.
    reg [7:0] age_lo;reg age_tick;reg [TIMEOUT_BIT-8:0] age_hi;
    wire timeout=age_hi[TIMEOUT_BIT-8];
    reg [7:0] t_lo;reg t_tick,t_en;reg [15:0] t_hi;
    // Accepted-rise spacing, pipelined over three ticks (accepted rises are >=5 ticks apart).
    reg [7:0] sp_len,sp_val,sp_prev,sp_min,sp_max,sp_jump,sp_diff;
    reg sp_have,sp_prev_valid,sp_ge;
    reg [2:0] sp_pipe;
    // Registered near-saturation flags (one cycle late is safe: events are >=5 ticks apart).
    reg pre_full,post_full,fall_full,rej_full,drp_full,rnt_full,tail_full,jump_full;
    wire any_rise=ev_accept|ev_reject|ev_drop;
    wire any_trans=any_rise|ev_fall;
    wire anom_ev=vact&(ev_reject|ev_drop|ev_runt);
    wire [2:0] anom_kind=ev_reject?3'd1:(ev_drop?3'd2:3'd3);
    wire jump_ev=sp_pipe[2]&sp_prev_valid&(|sp_diff[7:2]);
    always @(posedge clk or negedge reset_n) begin
        if(!reset_n) begin
            win_s<=0;dir_s<=0;done_s<=0;err_s<=0;
            open<=0;vact<=0;vend_cnt<=0;first<=1;first_none<=1;fault_seen<=0;sat_seen<=0;done_seen<=0;err_seen<=0;
            pre<=0;post<=0;fall_cnt<=0;exp_l<=0;last_l<=0;first_pos<=12'hfff;first_kind<=0;
            rej<=0;drp<=0;rnt<=0;tailn<=0;min_h<=8'hff;min_l<=8'hff;run_len<=0;acc_last<=0;
            age_lo<=0;age_tick<=0;age_hi<=0;t_lo<=0;t_tick<=0;t_en<=0;t_hi<=0;
            sp_len<=0;sp_val<=0;sp_prev<=0;sp_min<=8'hff;sp_max<=0;sp_jump<=0;sp_diff<=0;
            sp_have<=0;sp_prev_valid<=0;sp_ge<=0;sp_pipe<=0;
            pre_full<=0;post_full<=0;fall_full<=0;rej_full<=0;drp_full<=0;rnt_full<=0;tail_full<=0;jump_full<=0;
            snap_toggle<=0;snap_pre<=0;snap_post<=0;snap_fall<=0;snap_expect<=0;snap_done_index<=0;snap_first_pos<=12'hfff;
            snap_reject<=0;snap_drop<=0;snap_runt<=0;snap_tail_noise<=0;snap_min_high<=8'hff;snap_min_low<=8'hff;
            snap_sp_min<=8'hff;snap_sp_max<=0;snap_sp_jump<=0;snap_flags<=0;snap_ticks<=0;snap_first_kind<=0;
        end else begin
            win_s<={win_s[0],window_async};
            dir_s<={dir_s[0],dir_async};
            done_s<={done_s[0],ser_done};
            err_s<={err_s[0],ser_error};
            if(run_len!=8'hff) run_len<=run_len+1'b1;
            if(!open) begin
                if(win_s[1]) begin
                    open<=1;vact<=1;vend_cnt<=0;first<=1;first_none<=1;fault_seen<=0;sat_seen<=0;done_seen<=0;err_seen<=0;run_len<=0;
                    age_lo<=0;age_tick<=0;age_hi<=0;t_lo<=0;t_tick<=0;t_en<=0;t_hi<=0;
                    pre<=0;post<=0;fall_cnt<=0;rej<=0;drp<=0;rnt<=0;tailn<=0;min_h<=8'hff;min_l<=8'hff;
                    first_pos<=12'hfff;first_kind<=0;acc_last<=0;
                    sp_len<=0;sp_val<=0;sp_prev<=0;sp_min<=8'hff;sp_max<=0;sp_jump<=0;sp_diff<=0;
                    sp_have<=0;sp_prev_valid<=0;sp_ge<=0;sp_pipe<=0;
                    exp_l<=expect_edges;last_l<=expect_last;
                end
            end else begin
                age_lo<=age_lo+1'b1;age_tick<=&age_lo;
                if(age_tick) age_hi<=age_hi+1'b1;
                pre_full<=(pre>=12'hffe);post_full<=(post>=12'hffe);fall_full<=(fall_cnt>=12'hffe);
                rej_full<=(rej>=8'hfe);drp_full<=(drp>=8'hfe);rnt_full<=(rnt>=8'hfe);
                tail_full<=(tailn>=8'hfe);jump_full<=(sp_jump>=8'hfe);
                acc_last<=(pre==last_l);
                // Early end of the valid interval: the serializer finished without
                // the expected number of accepted rises (abort, error, fault).
                // The serializer clears done/error again once the offer drops, so keep them sticky for the window.
                if(done_s[1]) done_seen<=1;
                if(err_s[1]) err_seen<=1;
                if(vact && done_s[1]) begin vact<=0;t_en<=0; end
                if(vact && filter_fault) fault_seen<=1;
                // ---- accepted rises ----
                sp_pipe[0]<=1'b0;
                if(sp_len!=8'hff) sp_len<=sp_len+1'b1;
                if(ev_accept) begin
                    if(vact) begin
                        if(pre_full) sat_seen<=1; else pre<=pre+1'b1;
                        if(acc_last) begin vact<=0;vend_cnt<=1;t_en<=0; end
                        else if(!sp_have) t_en<=1;
                        if(sp_have) begin sp_val<=sp_len;sp_pipe[0]<=1'b1; end
                        sp_have<=1;sp_len<=8'd1;
                    end else begin
                        if(post_full) sat_seen<=1; else post<=post+1'b1;
                    end
                end
                // ---- other events ----
                if(vact) begin
                    if(ev_reject) begin if(rej_full) sat_seen<=1; else rej<=rej+1'b1; end
                    if(ev_drop) begin if(drp_full) sat_seen<=1; else drp<=drp+1'b1; end
                    if(ev_runt) begin if(rnt_full) sat_seen<=1; else rnt<=rnt+1'b1; end
                    if(ev_fall) begin if(fall_full) sat_seen<=1; else fall_cnt<=fall_cnt+1'b1; end
                end else if(ev_reject|ev_drop|ev_runt) begin
                    if(tail_full) sat_seen<=1; else tailn<=tailn+1'b1;
                end
                // ---- run lengths of the qualified signal (valid interval only) ----
                if(any_trans) begin
                    first<=0;run_len<=1;
                    // The run that just ended started at the previous transition.
                    // The very first transition of a window ends a run of unknown
                    // start, so it is not recorded.
                    if(vact && !first) begin
                        if(ev_fall) begin if(run_len<min_h) min_h<=run_len; end
                        else begin if(run_len<min_l) min_l<=run_len; end
                    end
                end
                // ---- spacing pipeline: stage1 compare/min/max, stage2 |diff|, stage3 jump ----
                sp_pipe[1]<=sp_pipe[0];sp_pipe[2]<=sp_pipe[1];
                if(sp_pipe[0]) begin
                    sp_ge<=(sp_val>=sp_prev);
                    if(sp_val<sp_min) sp_min<=sp_val;
                    if(sp_val>sp_max) sp_max<=sp_val;
                end
                if(sp_pipe[1]) sp_diff<=sp_ge?(sp_val-sp_prev):(sp_prev-sp_val);
                if(sp_pipe[2]) begin
                    sp_prev<=sp_val;sp_prev_valid<=1;
                    if(jump_ev) begin if(jump_full) sat_seen<=1; else sp_jump<=sp_jump+1'b1; end
                end
                // ---- first anomaly position ----
                if(first_none) begin
                    if(jump_ev) begin first_none<=0;first_pos<=pre;first_kind<=3'd4; end
                    else if(anom_ev) begin first_none<=0;first_pos<=pre;first_kind<=anom_kind; end
                end
                // ---- valid-interval length in ticks ----
                if(t_en) begin
                    t_lo<=t_lo+1'b1;t_tick<=&t_lo;
                end else t_tick<=1'b0;
                if(t_tick) t_hi<=t_hi+1'b1;
                // ---- window end ----
                if(!dir_s[1] || timeout) begin
                    open<=0;vact<=0;
                    snap_pre<=pre;snap_post<=post;snap_fall<=fall_cnt;snap_expect<=exp_l;
                    snap_done_index<=ser_done_index;snap_first_pos<=first_pos;snap_first_kind<=first_kind;
                    snap_reject<=rej;snap_drop<=drp;snap_runt<=rnt;snap_tail_noise<=tailn;
                    snap_min_high<=min_h;snap_min_low<=min_l;
                    snap_sp_min<=sp_min;snap_sp_max<=sp_max;snap_sp_jump<=sp_jump;
                    snap_ticks<={t_hi,t_lo};
                    snap_flags<={1'b1,vend_cnt,first,sat_seen,timeout,fault_seen,err_seen,done_seen};
                    snap_toggle<=~snap_toggle;
                end
            end
        end
    end
endmodule
