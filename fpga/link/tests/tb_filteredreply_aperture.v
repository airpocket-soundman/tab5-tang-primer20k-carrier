`timescale 1ps/1ps
// Nominal54MHz with1ps quantization:18518ps period. Digital transport model,
// not a signal-integrity/electrical measurement. TX remains slow1us edges.
module tb_filteredreply_frequency;
    parameter integer SAMPLE_INVERTED=0;
    parameter integer ONE_WAY_DELAY_PS=0;
    parameter integer FPGA_TCO_PS=0;
    parameter integer EXTENDED_MODE=0;
    parameter integer CLOCK_PATTERN=0;
    reg filter_clk=0;always #2315 filter_clk=~filter_clk;
    reg sys_clk=0,reset_n=0,arm=0,host_clk=0,host_dir=0;
    reg [7:0] host_data=0;
    wire bus_clk,dir;
    wire [7:0] data_i,data_o,sampled;
    wire data_oe,ready,host_ready;
    assign #(ONE_WAY_DELAY_PS) bus_clk=host_clk;
    assign #(ONE_WAY_DELAY_PS) dir=host_dir;
    assign #(ONE_WAY_DELAY_PS) data_i=host_data;
    assign #(ONE_WAY_DELAY_PS+FPGA_TCO_PS) sampled=data_oe?data_o:8'hzz;
    assign #(ONE_WAY_DELAY_PS) host_ready=ready;
    always begin #9259;sys_clk=1;#9259;sys_clk=0;end
    link_bringup_filtered #(.GFX_ENABLE(2),.TIMEOUT_CYCLES(5400000),.CORE_CLOCK_MHZ(54),.CLOCK_QUERY_ENABLE(1),.FAST_REPLY_ENABLE(1)) dut(
        sys_clk,reset_n,arm,bus_clk,dir,data_i,data_o,data_oe,ready,filter_clk,reset_n && arm);
    reg [7:0] q[0:7],expected[0:2065],got[0:2081];
    integer f,p,kind,i,j,frequency,period_ps,half_ps,length,case_id=0,first_bad,pass,cycles;
    integer match_count,offset,k,match;
    integer aperture_ok,last_sample_index=-1;
    time change_time=0,setup_age[0:2081],hold_age[0:2081],sample_time[0:2081],minimum_setup,minimum_hold;
    always @(sampled)begin
        change_time=$time;
        if(last_sample_index>=0 && $time-sample_time[last_sample_index]<hold_age[last_sample_index])
            hold_age[last_sample_index]=$time-sample_time[last_sample_index];
    end
    integer div_n,frac_n,frac_d,accumulator,edge_div,cycle_ps,high_ps,low_ps,phase_ns;
    reg [15:0] crc,stream;
    reg [7:0] sequence_id,row,plane;
    time target;
    function [15:0] crc_byte(input [15:0] c,input [7:0] b);
        reg [15:0] v;integer k;
        begin v=c^{b,8'h00};for(k=0;k<8;k=k+1)v=v[15]?(v<<1)^16'h1021:v<<1;crc_byte=v;end
    endfunction
    // Independent address-varying RAM fixture catches stale next-word data;
    // no full response array is added to the synthesized RTL.
    function [15:0] tile_pattern(input integer word_address,input integer depth_plane);
        reg [15:0] v;
        begin v=word_address+1;v=v^(v<<7);v=v^(v>>9);v=v^(v<<8);
            tile_pattern=v^(depth_plane?16'hd36e:16'h5a3c);end
    endfunction
    task make_request(input [7:0] op,input [7:0] seq_byte,input [7:0] a,input [7:0] b);
        integer k;reg [15:0] v;
        begin q[0]=8'ha5;q[1]=op;q[2]=seq_byte;q[3]=2;q[4]=a;q[5]=b;
            v=16'hffff;for(k=0;k<6;k=k+1)v=crc_byte(v,q[k]);q[6]=v[7:0];q[7]=v[15:8];end
    endtask
    task send_slow;
        integer k;
        begin host_clk=0;host_dir=0;#1000000;
            for(k=0;k<8;k=k+1)begin host_data=q[k];#1000000;host_clk=1;#1000000;host_clk=0;#1000000;end
            host_data=0;#1000000;
            cycles=0;while(!host_ready && cycles<100000)begin #10000;cycles=cycles+1;end
            if(!host_ready)$fatal(1,"slow request READY timeout");
            host_dir=1;#1000000;
        end
    endtask
    task clear_tile;
        integer k;reg [7:0] reply[0:7];reg [15:0] v;
        begin make_request(8'h2b,8'h55,8'h34,8'h12);send_slow();
            for(k=0;k<8;k=k+1)begin reply[k]=sampled;host_clk=1;#1000000;host_clk=0;#1000000;end
            #1000000;
            v=16'hffff;for(k=0;k<6;k=k+1)v=crc_byte(v,reply[k]);
            if(reply[0]!=8'h5a || reply[1]!=0 || reply[6]!=v[7:0] || reply[7]!=v[15:8] || host_ready)
                $fatal(1,"slow CLEAR reference failed");
            host_dir=0;#1000000;
        end
    endtask
    initial begin
        for(f=0;f<(EXTENDED_MODE?13:9);f=f+1) begin
            frac_n=0;frac_d=1;
            if(EXTENDED_MODE)begin
                case(f)
                    0:begin frequency=11000000;div_n=14;frac_n=6;frac_d=11;end
                    1:begin frequency=12000000;div_n=13;frac_n=1;frac_d=3;end
                    2:begin frequency=12500000;div_n=12;frac_n=4;frac_d=5;end
                    3:begin frequency=12307692;div_n=13;end
                    4:begin frequency=13333333;div_n=12;end
                    5:begin frequency=14000000;div_n=11;frac_n=3;frac_d=7;end
                    6:begin frequency=14545454;div_n=11;end
                    7:begin frequency=15000000;div_n=10;frac_n=2;frac_d=3;end
                    8:begin frequency=16000000;div_n=10;end
                    9:begin frequency=20000000;div_n=8;end
                    10:begin frequency=25000000;div_n=6;frac_n=2;frac_d=5;end
                    11:begin frequency=32000000;div_n=5;end
                    12:begin frequency=40000000;div_n=4;end
                endcase
                period_ps=1000000000000.0/frequency;
            end else case(f)0:begin frequency=5000000;period_ps=200000;end
                1:begin frequency=8000000;period_ps=125000;end
                2:begin frequency=10000000;period_ps=100000;end
                3:begin frequency=12500000;period_ps=80000;end
                4:begin frequency=16000000;period_ps=62500;end
                5:begin frequency=20000000;period_ps=50000;end
                6:begin frequency=25000000;period_ps=40000;end
                7:begin frequency=32000000;period_ps=31250;end
                8:begin frequency=40000000;period_ps=25000;end endcase
            half_ps=period_ps/2;
            for(p=0;p<(EXTENDED_MODE?3:9);p=p+1)for(kind=(EXTENDED_MODE?2:0);kind<3;kind=kind+1)begin
                phase_ns=EXTENDED_MODE?p*8:p*2;accumulator=0;
                last_sample_index=-1;host_clk=0;host_dir=0;host_data=0;arm=0;reset_n=0;#2000000;
                reset_n=1;arm=1;#2000000;
                if(kind!=0)clear_tile();
                if(kind==2)begin
                    for(j=0;j<1024;j=j+1)begin
                        dut.triangle.renderer.colors[j]=tile_pattern(j,0);
                        dut.triangle.renderer.depths[j]=tile_pattern(j,1);
                    end
                end
                sequence_id=case_id;row=case_id%32;plane=(case_id/2)%2;
                if(kind==0)make_request(8'h81,sequence_id,0,0);
                else if(kind==1)make_request(8'haf,sequence_id,row,plane);
                else make_request(8'hbb,sequence_id,0,plane);
                send_slow();
                for(i=0;i<8;i=i+1)expected[i]=8'hc3;
                expected[8]=8'h5a;expected[9]=0;expected[10]=sequence_id;expected[11]=2;
                expected[12]=kind==0?8'h54:(kind==1?row:0);expected[13]=kind==0?8'h50:plane;
                crc=16'hffff;for(i=8;i<14;i=i+1)crc=crc_byte(crc,expected[i]);
                expected[14]=crc[7:0];expected[15]=crc[15:8];length=16;
                if(kind!=0)begin
                    // CLEAR1234 color; depth0. Byte order and row metadata CRC
                    // remain independently checked even for repeated words.
                    stream=crc;
                    for(i=16;i<(kind==1?80:2064);i=i+1)begin
                        if(kind==2)begin
                            crc=tile_pattern((i-16)/2,plane);
                            expected[i]=i%2==0?crc[7:0]:crc[15:8];
                        end else expected[i]=plane==1?0:(i%2==0?8'h34:8'h12);
                        stream=crc_byte(stream,expected[i]);
                    end
                    expected[kind==1?80:2064]=stream[7:0];expected[kind==1?81:2065]=stream[15:8];length=kind==1?82:2066;
                end
                // First sample is aligned to the nominal sys_clk positive
                // edge+phase. Host samples old byte immediately before CLK rise.
                target=(($time-9259)/18518+2)*18518+9259+phase_ns*1000;
                #(target-$time);first_bad=-1;
                for(i=0;i<length+16;i=i+1)begin
                    if(EXTENDED_MODE)begin
                        edge_div=div_n;accumulator=accumulator+frac_n;
                        if(accumulator>=frac_d)begin accumulator=accumulator-frac_d;edge_div=edge_div+1;end
                        cycle_ps=edge_div*6250;
                        high_ps=(CLOCK_PATTERN==1?edge_div/2:(edge_div+1)/2)*6250;
                        low_ps=cycle_ps-high_ps;
                    end else begin cycle_ps=period_ps;high_ps=half_ps;low_ps=period_ps-half_ps;end
                    if(!SAMPLE_INVERTED)begin
                        got[i]=sampled;setup_age[i]=$time-change_time;hold_age[i]=999999;
                        sample_time[i]=$time;last_sample_index=i;
                    end
                    host_clk=1;#(high_ps);
                    if(SAMPLE_INVERTED)begin
                        got[i]=sampled;setup_age[i]=$time-change_time;hold_age[i]=999999;
                        sample_time[i]=$time;last_sample_index=i;
                    end
                    host_clk=0;#(low_ps);
                end
                #2000000;match_count=0;offset=-1;
                for(j=0;j<=24;j=j+1)begin
                    match=1;for(k=0;k<length-8;k=k+1)if(got[j+k]!==expected[k+8])match=0;
                    if(match)begin match_count=match_count+1;offset=j;end
                end
                pass=(match_count==1 && !host_ready);first_bad=offset;
                aperture_ok=pass;minimum_setup=999999;minimum_hold=999999;
                if(pass)for(k=offset;k<offset+length-8;k=k+1)begin
                    if(setup_age[k]<minimum_setup)minimum_setup=setup_age[k];
                    if(hold_age[k]<minimum_hold)minimum_hold=hold_age[k];
                    if(setup_age[k]<2000 || hold_age[k]<2000)aperture_ok=0;
                end
                $display("SWEEP,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",frequency,phase_ns,ONE_WAY_DELAY_PS/1000,kind,pass,first_bad,host_ready,aperture_ok,minimum_setup,minimum_hold);
                case_id=case_id+1;
            end
        end
        $display("DONE response frequency cases=%0d",case_id);$finish;
    end
    initial begin #100000000000;$fatal(1,"watchdog");end
endmodule
