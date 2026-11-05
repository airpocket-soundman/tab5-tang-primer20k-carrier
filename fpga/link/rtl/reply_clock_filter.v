// Experimental sampled conditioning. No analog glitch-width guarantee.
// At216MHz: qualify two equal samples, emit2tick HIGH, rises >=5ticks apart.
// The request parser never uses this clock. Slow DIR0 clocks still reach the
// reply serializer so its existing offer=0 reset/metadata lifecycle is retained.
module reply_clock_filter #(parameter ACTIVE_PIPELINE=0, parameter FAST_FILTER_SYNC=0)(
    input wire sample_clk,reset_n,raw_clk,reply_active,
    output reg clean_clk,
    output reg fault
);
    (* ASYNC_REG="TRUE" *) reg meta,sampled;
    wire effective_active;
    generate if(ACTIVE_PIPELINE) begin: active_pipe
        // Only the fault/qualification policy is delayed. Physical OE/READY
        // remains immediately gated by raw DIR/offer in the LINK wrapper.
        (* ASYNC_REG="TRUE" *) reg [1:0] active_sync;
        always @(posedge sample_clk or negedge reset_n)
            if(!reset_n) active_sync<=0;
            else active_sync<={active_sync[0],reply_active};
        assign effective_active=active_sync[1];
    end else begin: active_direct
        assign effective_active=reply_active;
    end endgenerate
    reg qualified,changing;
    reg [2:0] cooldown;
    reg pulse_remaining;
    always @(posedge sample_clk or negedge reset_n) begin
        if(!reset_n) begin
            meta<=0;sampled<=0;qualified<=0;changing<=0;
            cooldown<=0;pulse_remaining<=0;clean_clk<=0;fault<=0;
        end else begin
            meta<=raw_clk;sampled<=meta;
            if(!effective_active)fault<=0;
            if(cooldown!=0)cooldown<=cooldown-1'b1;
            if(pulse_remaining)pulse_remaining<=0;
            else clean_clk<=0;
            if(sampled==qualified)changing<=0;
            // Fast candidate keeps both synchronizer stages, but qualifies
            // their sampled level immediately instead of waiting one more tick.
            // This deliberately changes rejection of one-sample excursions.
            else if(!FAST_FILTER_SYNC && !changing)changing<=1;
            else begin
                qualified<=sampled;changing<=0;
                if(sampled)begin
                    if(cooldown!=0)begin
                        if(effective_active)fault<=1;
                    end else if(!fault || !effective_active)begin
                        clean_clk<=1;pulse_remaining<=1;cooldown<=4;
                    end
                end
            end
        end
    end
endmodule
