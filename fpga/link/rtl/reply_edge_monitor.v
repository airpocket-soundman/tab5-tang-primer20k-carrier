// Diagnostic-only per-reply edge monitor for the conditioned reply clock.
//
// Runs in the 216MHz sampler domain next to reply_clock_filter. It observes the
// filter's one-tick strobes and never drives clean_clk, fault or any serializer
// input, so the reply datapath is unchanged. One "window" spans a reply:
//   start: (fast_offer && dir) synchronized HIGH
//   end:   raw DIR synchronized LOW, or a ~9.7ms safety timeout
// At window end a snapshot is registered and snap_toggle flips (bundled-data
// toggle). The SYS domain copies the snapshot after a 2FF-synchronized toggle
// change; the snapshot registers do not change again until the next window end.
//
// What the counters can and cannot say (see docs/CLK_edge_monitor.md):
//   pre/post   accepted rises before/after the serializer's synchronized done
//   reject     qualified rises inside the 5-sample cooldown (also trips fault)
//   drop       qualified rises swallowed after a fault inside the same window
//   runt       one-sample excursions rejected by the 2-sample qualification
//   fall       qualified falls
//   min_high/min_low  shortest qualified HIGH/LOW run in sampler ticks (4.63ns)
// snap_flags: [0] done seen  [1] serializer error  [2] filter fault seen
//             [3] timeout close  [4] counter saturated  [5] no edges at all
//             [7] valid snapshot (0 after reset)
// A pulse that is narrower than the 216MHz sampling can alias; these counters
// are not an analog measurement.
module reply_edge_monitor #(parameter TIMEOUT_BIT = 21)(
    input wire clk,reset_n,
    input wire window_async,dir_async,
    input wire [11:0] expect_edges,
    input wire ev_accept,ev_reject,ev_drop,ev_runt,ev_fall,filter_fault,
    input wire ser_done,ser_error,
    input wire [11:0] ser_done_index,
    output reg snap_toggle,
    output reg [11:0] snap_pre,snap_post,snap_fall,snap_expect,snap_done_index,
    output reg [7:0] snap_reject,snap_drop,snap_runt,snap_min_high,snap_min_low,snap_flags
);
    (* ASYNC_REG="TRUE" *) reg [1:0] win_s,dir_s,done_s,err_s;
    reg open,first,fault_seen,sat_seen;
    reg [11:0] pre,post,fall_cnt,exp_l;
    reg [7:0] rej,drp,rnt,min_h,min_l,run_len;
    reg [TIMEOUT_BIT:0] age;
    wire any_rise=ev_accept|ev_reject|ev_drop;
    wire any_trans=any_rise|ev_fall;
    always @(posedge clk or negedge reset_n) begin
        if(!reset_n) begin
            win_s<=0;dir_s<=0;done_s<=0;err_s<=0;
            open<=0;first<=1;fault_seen<=0;sat_seen<=0;
            pre<=0;post<=0;fall_cnt<=0;exp_l<=0;
            rej<=0;drp<=0;rnt<=0;min_h<=8'hff;min_l<=8'hff;run_len<=0;age<=0;
            snap_toggle<=0;snap_pre<=0;snap_post<=0;snap_fall<=0;snap_expect<=0;snap_done_index<=0;
            snap_reject<=0;snap_drop<=0;snap_runt<=0;snap_min_high<=8'hff;snap_min_low<=8'hff;snap_flags<=0;
        end else begin
            win_s<={win_s[0],window_async};
            dir_s<={dir_s[0],dir_async};
            done_s<={done_s[0],ser_done};
            err_s<={err_s[0],ser_error};
            if(run_len!=8'hff) run_len<=run_len+1'b1;
            if(!open) begin
                if(win_s[1]) begin
                    open<=1;first<=1;fault_seen<=0;sat_seen<=0;age<=0;run_len<=0;
                    pre<=0;post<=0;fall_cnt<=0;rej<=0;drp<=0;rnt<=0;min_h<=8'hff;min_l<=8'hff;
                    exp_l<=expect_edges;
                end
            end else begin
                age<=age+1'b1;
                if(filter_fault) fault_seen<=1;
                if(ev_accept) begin
                    if(!done_s[1]) begin if(&pre) sat_seen<=1; else pre<=pre+1'b1; end
                    else begin if(&post) sat_seen<=1; else post<=post+1'b1; end
                end
                if(ev_reject) begin if(&rej) sat_seen<=1; else rej<=rej+1'b1; end
                if(ev_drop) begin if(&drp) sat_seen<=1; else drp<=drp+1'b1; end
                if(ev_runt) begin if(&rnt) sat_seen<=1; else rnt<=rnt+1'b1; end
                if(ev_fall) begin if(&fall_cnt) sat_seen<=1; else fall_cnt<=fall_cnt+1'b1; end
                if(any_trans) begin
                    first<=0;run_len<=1;
                    // The run that just ended started at the previous transition.
                    // The very first transition of a window ends a run of unknown
                    // start, so it is not recorded.
                    if(!first) begin
                        if(ev_fall) begin if(run_len<min_h) min_h<=run_len; end
                        else begin if(run_len<min_l) min_l<=run_len; end
                    end
                end
                if(!dir_s[1] || age[TIMEOUT_BIT]) begin
                    open<=0;
                    snap_pre<=pre;snap_post<=post;snap_fall<=fall_cnt;snap_expect<=exp_l;
                    snap_done_index<=ser_done_index;
                    snap_reject<=rej;snap_drop<=drp;snap_runt<=rnt;
                    snap_min_high<=min_h;snap_min_low<=min_l;
                    snap_flags<={1'b1,1'b0,first,sat_seen,age[TIMEOUT_BIT],fault_seen,err_s[1],done_s[1]};
                    snap_toggle<=~snap_toggle;
                end
            end
        end
    end
endmodule
