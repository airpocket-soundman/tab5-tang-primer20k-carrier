`timescale 1ns/1ps
module tb_raster2d;
    reg clk=0; always #5 clk=~clk;
    reg reset_n=0,abort=0,start=0;
    reg [1:0] kind=0;
    reg signed [15:0] x0=0,y0=0,x1=0,y1=0;
    reg [15:0] color=0;
    reg [23:0] add_rgb=0;
    wire busy,done,we;
    wire [9:0] ra,wa;
    wire [15:0] wc;
    reg [15:0] rq=0,memory[0:1023],expected[0:1023];
    integer writes=0,expected_writes=0,tests=0,i,j,k,seed=32'h127385;
    raster2d dut(.clk(clk),.reset_n(reset_n),.abort(abort),.start(start),
        .kind(kind),.x0(x0),.y0(y0),.x1(x1),.y1(y1),.color(color),.add_rgb(add_rgb),
        .busy(busy),.done(done),.read_address(ra),.read_color(rq),
        .write_enable(we),.write_address(wa),.write_color(wc));
    always @(posedge clk) begin
        rq<=memory[ra];
        if(we) begin memory[wa]<=wc;writes<=writes+1;end
    end
    task put;
        input integer x,y;input [15:0] value;
        begin
            if(x>=0 && x<32 && y>=0 && y<32) begin
                expected[y*32+x]=value;expected_writes=expected_writes+1;
            end
        end
    endtask
    function [15:0] add_reference;
        input [15:0] dst;input [23:0] rgb;
        integer r,g,b;
        begin
            r=(dst>>11)*255/31+((rgb>>16)&255);
            g=((dst>>5)&63)*255/63+((rgb>>8)&255);
            b=(dst&31)*255/31+(rgb&255);
            if(r>255)r=255;if(g>255)g=255;if(b>255)b=255;
            add_reference=((r&248)<<8)|((g&252)<<3)|(b>>3);
        end
    endfunction
    task reference;
        input integer op,ax,ay,bx,by; input [15:0] ink;input [23:0] rgb;
        integer x,y,dx,dy,sx,sy,err,e2,finished;
        begin
            expected_writes=0;
            if(op==0) put(ax,ay,ink);
            if(op==1) begin
                x=ax;y=ay;dx=bx-ax;if(dx<0)dx=-dx;
                dy=by-ay;if(dy>0)dy=-dy;
                sx=ax<bx?1:-1;sy=ay<by?1:-1;err=dx+dy;finished=0;
                while(!finished) begin
                    put(x,y,ink);
                    if(x==bx && y==by) finished=1;
                    else begin
                        e2=2*err;
                        if(e2>=dy) begin err=err+dy;x=x+sx;end
                        if(e2<=dx) begin err=err+dx;y=y+sy;end
                    end
                end
            end
            if(op==2) begin
                // Restrict loop bounds for extreme coordinates, but keep invalid ordering empty.
                for(y=(ay<0?0:ay);y<=by && y<32;y=y+1)
                    for(x=(ax<0?0:ax);x<=bx && x<32;x=x+1)
                        if(ax<=bx && ay<=by) put(x,y,ink);
            end
            if(op==3 && ax>=0 && ax<32 && ay>=0 && ay<32)
                put(ax,ay,add_reference(expected[ay*32+ax],rgb));
        end
    endtask
    task check;
        input integer initial_writes;
        integer at;
        begin
            if(writes-initial_writes!=expected_writes)
                $fatal(1,"write count test%0d got%0d expected%0d",tests,writes-initial_writes,expected_writes);
            for(at=0;at<1024;at=at+1)
                if(memory[at]!==expected[at])
                    $fatal(1,"pixel test%0d index%0d got%h expected%h",tests,at,memory[at],expected[at]);
            if(busy) $fatal(1,"busy after done");
            tests=tests+1;
        end
    endtask
    task run;
        input integer op,ax,ay,bx,by;input [15:0] ink;input [23:0] rgb;
        integer before_writes,cycles;
        begin
            reference(op,ax,ay,bx,by,ink,rgb);before_writes=writes;
            @(negedge clk);kind=op;x0=ax;y0=ay;x1=bx;y1=by;color=ink;add_rgb=rgb;start=1;
            @(negedge clk);start=0;cycles=0;
            while(!done) begin
                @(negedge clk);cycles=cycles+1;
                if(cycles>70000) $fatal(1,"operation timeout");
            end
            check(before_writes);
            @(negedge clk);
        end
    endtask
    task abort_operation;
        input integer op;
        integer before_writes,at;
        begin
            @(negedge clk);kind=op;x0=3;y0=4;x1=31;y1=31;color=16'hf800;add_rgb=24'hffffff;start=1;
            @(negedge clk);start=0;abort=1;before_writes=writes;
            #1;if(we) $fatal(1,"write enabled during abort");
            repeat(3) @(negedge clk);
            if(writes!=before_writes || busy) $fatal(1,"abort did not stop writes");
            abort=0;
            // Abort is allowed to leave prior completed pixels; this test aborts before_writes the first write.
            for(at=0;at<1024;at=at+1) if(memory[at]!==expected[at]) $fatal(1,"abort changed pixel");
            tests=tests+1;
        end
    endtask
    initial begin
        for(i=0;i<1024;i=i+1) begin memory[i]=(i*29)^16'ha75c;expected[i]=memory[i];end
        repeat(3) @(negedge clk);reset_n=1;
        run(0,0,0,0,0,16'h1234,0);
        run(0,31,31,0,0,16'h2345,0);
        run(0,-1,0,0,0,16'hffff,0);
        run(0,32,31,0,0,16'hffff,0);
        run(2,-10,-12,35,40,16'h0821,0);
        run(2,3,7,3,7,16'hf800,0);
        run(2,20,20,10,31,16'hffff,0);
        run(2,-30,-30,-1,31,16'hffff,0);
        run(2,-32768,-32768,32767,32767,16'h0420,0);
        // Every octant, reverse direction, diagonal ties, single-point line and tile-crossing lines.
        for(i=-2;i<=2;i=i+1) for(j=-2;j<=2;j=j+1) begin
            run(1,16,16,16+i*11,16+j*9,16'h4000+i*5+j,0);
            run(1,16+i*11,16+j*9,16,16,16'h8000+i*5+j,0);
        end
        run(1,-32768,15,32767,15,16'h07e0,0);
        run(1,15,-32768,15,32767,16'h001f,0);
        for(i=0;i<200;i=i+1) begin
            run(1,($random(seed)&127)-48,($random(seed)&127)-48,
                  ($random(seed)&127)-48,($random(seed)&127)-48,i*257,0);
        end
        // Exercise every 5/6-bit destination component and carries, including repeated ADD on one pixel.
        for(i=0;i<64;i=i+1) begin
            run(0,7,9,0,0,((i&31)<<11)|(i<<5)|(31-(i&31)),0);
            run(3,7,9,0,0,0,24'h000000);
            run(3,7,9,0,0,0,24'h3264c8);
            run(3,7,9,0,0,0,24'hffffff);
        end
        run(3,-1,4,0,0,0,24'hffffff);
        run(3,4,32,0,0,0,24'hffffff);
        // Inputs and busy-time start cannot alter the latched operation.
        reference(1,0,3,31,17,16'hfc19,0);
        begin: latched
            integer before_writes;before_writes=writes;
            @(negedge clk);kind=1;x0=0;y0=3;x1=31;y1=17;color=16'hfc19;start=1;
            @(negedge clk);kind=2;x0=0;y0=0;x1=31;y1=31;color=0;start=1;
            repeat(3) @(negedge clk);
            start=0;
            while(!done) @(negedge clk);
            check(before_writes);
        end
        abort_operation(0);abort_operation(1);abort_operation(2);abort_operation(3);
        run(3,31,31,0,0,0,24'h123456);
        $display("raster2d RTL PASS: %0d operations; all pixels and exact write counts checked",tests);
        $finish;
    end
endmodule
