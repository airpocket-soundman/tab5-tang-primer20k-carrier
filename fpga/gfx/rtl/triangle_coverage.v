// G0 geometric fragment test. One registered cycle, no backpressure.
// Caller supplies a candidate pixel; target/scissor/depth/memory are separate.
module triangle_coverage (
    input wire clk, reset_n, in_valid,
    input wire signed [15:0] ax, ay, bx, by, cx, cy,
    input wire [9:0] pixel_x,
    input wire [8:0] pixel_y,
    output reg out_valid, covered, degenerate, winding_swapped,
    output reg signed [63:0] area, weight_a, weight_b, weight_c
);
    // Extend BEFORE subtracting/multiplying; never evaluate at 16-bit width.
    wire signed [63:0] a_x={{48{ax[15]}},ax}, a_y={{48{ay[15]}},ay};
    wire signed [63:0] b_x={{48{bx[15]}},bx}, b_y={{48{by[15]}},by};
    wire signed [63:0] c_x={{48{cx[15]}},cx}, c_y={{48{cy[15]}},cy};
    wire signed [63:0] p_x=($signed({54'b0,pixel_x}) <<< 4)+64'sd8;
    wire signed [63:0] p_y=($signed({55'b0,pixel_y}) <<< 4)+64'sd8;
    function signed [63:0] edge64;
        input signed [63:0] ux,uy,vx,vy,px,py;
        reg signed [63:0] dx,dy,rx,ry;
        begin
            dx=vx-ux; dy=vy-uy; rx=px-ux; ry=py-uy;
            edge64=dx*ry-dy*rx;
        end
    endfunction
    function top_left;
        input signed [63:0] ux,uy,vx,vy;
        begin top_left=(vy<uy) || ((vy==uy) && (vx>ux)); end
    endfunction
    reg signed [63:0] raw_area, pos_area, nbx,nby,ncx,ncy,wa,wb,wc;
    reg swap_winding, is_degenerate, is_covered;
    always @* begin
        raw_area=edge64(a_x,a_y,b_x,b_y,c_x,c_y);
        swap_winding=raw_area<0;
        pos_area=swap_winding ? -raw_area : raw_area;
        nbx=swap_winding ? c_x:b_x; nby=swap_winding ? c_y:b_y;
        ncx=swap_winding ? b_x:c_x; ncy=swap_winding ? b_y:c_y;
        wa=edge64(nbx,nby,ncx,ncy,p_x,p_y);
        wb=edge64(ncx,ncy,a_x,a_y,p_x,p_y);
        wc=edge64(a_x,a_y,nbx,nby,p_x,p_y);
        is_degenerate=raw_area==0;
        is_covered=!is_degenerate &&
            ((wa>0) || ((wa==0) && top_left(nbx,nby,ncx,ncy))) &&
            ((wb>0) || ((wb==0) && top_left(ncx,ncy,a_x,a_y))) &&
            ((wc>0) || ((wc==0) && top_left(a_x,a_y,nbx,nby)));
    end
    always @(posedge clk or negedge reset_n) begin
        if(!reset_n) begin
            out_valid<=0; covered<=0; degenerate<=0; winding_swapped<=0;
            area<=0; weight_a<=0; weight_b<=0; weight_c<=0;
        end else begin
            out_valid<=in_valid;
            if(in_valid) begin
                covered<=is_covered; degenerate<=is_degenerate; winding_swapped<=swap_winding;
                area<=pos_area;
                // Restore original vertex order, so Z values need no swapping.
                weight_a<=is_degenerate ? 64'sd0:wa;
                weight_b<=is_degenerate ? 64'sd0:(swap_winding ? wc:wb);
                weight_c<=is_degenerate ? 64'sd0:(swap_winding ? wb:wc);
            end
        end
    end
endmodule
