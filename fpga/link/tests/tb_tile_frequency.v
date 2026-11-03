`timescale 1ps/1ps
// Nominal27MHz with1ps quantization:37037ps period. Digital transport model,
// not a signal-integrity/electrical measurement. TX remains slow1us edges.
module tb_tile_frequency;
    parameter integer ONE_WAY_DELAY_PS=0;
    reg sys_clk=0,reset_n=0,arm=0,host_clk=0,host_dir=0;
    reg [7:0] host_data=0;
    wire bus_clk,dir;
    wire [7:0] data_i,data_o,sampled;
    wire data_oe,ready,host_ready;
    assign #(ONE_WAY_DELAY_PS) bus_clk=host_clk;
    assign #(ONE_WAY_DELAY_PS) dir=host_dir;
    assign #(ONE_WAY_DELAY_PS) data_i=host_data;
    assign #(ONE_WAY_DELAY_PS) sampled=data_oe?data_o:8'hzz;
    assign #(ONE_WAY_DELAY_PS) host_ready=ready;
    always begin #18518;sys_clk=1;#18519;sys_clk=0;end
    link_bringup #(.GFX_ENABLE(2),.TIMEOUT_CYCLES(2700000)) dut(
        sys_clk,reset_n,arm,bus_clk,dir,data_i,data_o,data_oe,ready);
    reg [7:0] q[0:7],expected[0:2065],got[0:2065];
    integer f,p,kind,i,j,frequency,period_ps,half_ps,length,case_id=0,first_bad,pass,cycles;
    reg [15:0] crc,stream;
    reg [7:0] sequence_id,row,plane;
    time target;
    function [15:0] crc_byte(input [15:0] c,input [7:0] b);
        reg [15:0] v;integer k;
        begin v=c^{b,8'h00};for(k=0;k<8;k=k+1)v=v[15]?(v<<1)^16'h1021:v<<1;crc_byte=v;end
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
        for(f=0;f<1;f=f+1) begin
            case(f)0:begin frequency=5000000;period_ps=200000;end
                1:begin frequency=8000000;period_ps=125000;end
                2:begin frequency=10000000;period_ps=100000;end
                3:begin frequency=20000000;period_ps=50000;end endcase
            half_ps=period_ps/2;
            for(p=0;p<8;p=p+1)for(kind=0;kind<3;kind=kind+1)begin
                host_clk=0;host_dir=0;host_data=0;arm=0;reset_n=0;#2000000;
                reset_n=1;arm=1;#2000000;
                if(kind!=0)clear_tile();
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
                        expected[i]=plane==1?0:(i%2==0?8'h34:8'h12);
                        stream=crc_byte(stream,expected[i]);
                    end
                    expected[kind==1?80:2064]=stream[7:0];expected[kind==1?81:2065]=stream[15:8];length=kind==1?82:2066;
                end
                // First sample is aligned to the nominal sys_clk positive
                // edge+phase. Host samples old byte immediately before CLK rise.
                target=(($time-18518)/37037+2)*37037+18518+p*5000;
                #(target-$time);first_bad=-1;
                for(i=0;i<length;i=i+1)begin
                    got[i]=sampled;
                    if(got[i]!==expected[i] && first_bad<0)first_bad=i;
                    host_clk=1;#(half_ps);host_clk=0;#(period_ps-half_ps);
                end
                #2000000;pass=(first_bad<0 && !host_ready);
                $display("SWEEP,%0d,%0d,%0d,%0d,%0d,%0d,%0d",frequency,p*5,ONE_WAY_DELAY_PS/1000,kind,pass,first_bad,host_ready);
                case_id=case_id+1;
            end
        end
        $display("DONE response frequency cases=%0d",case_id);$finish;
    end
    initial begin #100000000000;$fatal(1,"watchdog");end
endmodule
