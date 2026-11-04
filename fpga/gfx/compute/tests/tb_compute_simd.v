`timescale 1ns/1ps
module tb_compute_simd;
    parameter LANES=4;
    reg clk=0;
    always #5 clk=~clk;
    reg reset=1, program_we=0, start=0;
    reg [7:0] program_addr=0;
    reg [31:0] program_data=0, group_base=0, instruction_limit=10000;
    reg [15:0] entry=0;
    wire busy,done;
    wire [3:0] error;
    wire [31:0] cycles,instructions;
    wire mem_valid, mem_write, rsp_ready;
    wire [31:0] mem_word_addr,mem_wdata;
    reg rsp_valid=0, rsp_error=0;
    reg [31:0] rsp_data=0;
    reg pending=0, accepted_write=0;
    reg [31:0] accepted_addr=0,accepted_data=0;
    reg [31:0] rng=32'h79bade01;
    integer delay_left=0, ticks=0, requests=0;
    integer stall_mode=1, fault_address=-1, expected_error=0, expected_instructions=0;
    integer expected_requests=0, program_words=0, run_index,i,j;
    reg force_stall=0, preflight=1;
    reg [15:0] saved_entry;
    reg [31:0] saved_limit;
    wire mem_ready=!pending && !rsp_valid && !force_stall && (!stall_mode || rng[1:0]==0);
    reg [31:0] memory[0:255], expected[0:255], code[0:255], present[0:255];
    reg [31:0] expected_regs[0:LANES*16-1];
    reg [31:0] trace_write[0:4095],trace_addr[0:4095],trace_data[0:4095];
    reg held=0, held_write;
    reg [31:0] held_addr,held_data;
    reg [4095:0] directory;
    compute_simd #(.LANES(LANES)) dut(.*);

    always @(posedge clk) begin
        if (reset) begin
            pending<=0; rsp_valid<=0; rsp_error<=0; held<=0;
            ticks<=0; requests<=0; rng<=32'h79bade01;
        end else begin
            ticks<=ticks+1;
            rng<={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};
            if (ticks>300000) $fatal(1,"simulation timeout");
            if (held && (!mem_valid || mem_word_addr!==held_addr || mem_wdata!==held_data || mem_write!==held_write))
                $fatal(1,"request changed under backpressure");
            held<=mem_valid && !mem_ready;
            held_addr<=mem_word_addr; held_data<=mem_wdata; held_write<=mem_write;
            if (rsp_valid && rsp_ready) rsp_valid<=0;
            if (mem_valid && mem_ready) begin
                if (!preflight && requests>=expected_requests) $fatal(1,"unexpected memory request");
                if (!preflight && (mem_write!==trace_write[requests][0] || mem_word_addr!==trace_addr[requests] || mem_wdata!==trace_data[requests]))
                    $fatal(1,"request %0d mismatch addr=%h expected=%h",requests,mem_word_addr,trace_addr[requests]);
                requests<=requests+1;
                accepted_addr<=mem_word_addr; accepted_data<=mem_wdata; accepted_write<=mem_write;
                pending<=1; delay_left<=stall_mode ? (rng[5:2]+1) : 1;
            end
            if (pending) begin
                if (delay_left!=0) delay_left<=delay_left-1;
                else begin
                    pending<=0; rsp_valid<=1;
                    rsp_error<=accepted_addr>=256 || accepted_addr==fault_address;
                    rsp_data<=0;
                    if (accepted_addr<256 && accepted_addr!=fault_address) begin
                        if (accepted_write) memory[accepted_addr]<=accepted_data;
                        else rsp_data<=memory[accepted_addr];
                    end
                end
            end
        end
    end

    task write_program;
        input [7:0] address;
        input [31:0] value;
        begin
            @(negedge clk); program_we=1; program_addr=address; program_data=value;
            @(negedge clk); program_we=0;
        end
    endtask
    task launch;
        begin @(negedge clk); start=1; @(negedge clk); start=0; end
    endtask
    initial begin
        if (!$value$plusargs("directory=%s",directory)) $fatal(1,"directory missing");
        if (!$value$plusargs("program_words=%d",program_words)) $fatal(1,"program size missing");
        if (!$value$plusargs("budget=%d",instruction_limit)) $fatal(1,"budget missing");
        if (!$value$plusargs("entry=%d",entry)) $fatal(1,"entry missing");
        if (!$value$plusargs("base=%d",group_base)) $fatal(1,"base missing");
        if (!$value$plusargs("error=%d",expected_error)) $fatal(1,"error missing");
        if (!$value$plusargs("instructions=%d",expected_instructions)) $fatal(1,"count missing");
        if (!$value$plusargs("requests=%d",expected_requests)) $fatal(1,"requests missing");
        if (!$value$plusargs("stall=%d",stall_mode)) $fatal(1,"stall missing");
        if (!$value$plusargs("fault=%d",fault_address)) $fatal(1,"fault missing");
        $readmemh({directory,"/program.hex"},code);
        $readmemh({directory,"/present.hex"},present);
        $readmemh({directory,"/expected.hex"},expected);
        $readmemh({directory,"/registers.hex"},expected_regs);
        $readmemh({directory,"/trace_write.hex"},trace_write);
        $readmemh({directory,"/trace_addr.hex"},trace_addr);
        $readmemh({directory,"/trace_data.hex"},trace_data);
        repeat(3) @(negedge clk);
        reset=0;
        saved_entry=entry; saved_limit=instruction_limit;
        entry=0; instruction_limit=8; force_stall=1;
        write_program(0,32'h2c400000); // LOAD r2,[r0+0]
        launch;
        while(!mem_valid) @(negedge clk);
        repeat(4) @(negedge clk);
        if(!busy || !mem_valid) $fatal(1,"stalled request was not held");
        reset=1; repeat(2) @(negedge clk); reset=0; force_stall=0;
        if(busy || mem_valid || rsp_ready) $fatal(1,"reset did not cancel unaccepted request");
        write_program(0,32'h2c400000);
        launch;
        while(!pending) @(negedge clk);
        // The memory adapter is reset together with the core, as required.
        reset=1; repeat(2) @(negedge clk); reset=0;
        if(busy || mem_valid || pending || rsp_valid) $fatal(1,"reset did not clear in-flight request");
        launch; while(!done) @(negedge clk);
        if(error!=2) $fatal(1,"reset did not revoke in-flight program");
        @(negedge clk);
        entry=saved_entry; instruction_limit=saved_limit; preflight=0;
        for(i=0;i<program_words;i=i+1) if(present[i]) write_program(i,code[i]);
        for(run_index=0;run_index<2;run_index=run_index+1) begin
            $readmemh({directory,"/input.hex"},memory);
            requests=0;
            launch;
            // Attempts to overwrite code and relaunch while busy must be ignored.
            if(busy && expected_instructions>3) begin
                @(negedge clk);
                if(busy) begin program_we=1; program_addr=0; program_data=32'hfc000000; start=1; end
                @(negedge clk); program_we=0; start=0;
            end
            while(!done) @(negedge clk);
            if(busy || error!==expected_error[3:0] || instructions!==expected_instructions)
                $fatal(1,"completion mismatch error=%0d instructions=%0d expected=%0d/%0d",error,instructions,expected_error,expected_instructions);
            if(requests!=expected_requests) $fatal(1,"request count mismatch");
            for(j=0;j<256;j=j+1) if(memory[j]!==expected[j]) $fatal(1,"memory %0d got=%h expected=%h",j,memory[j],expected[j]);
            if(entry<256 && instruction_limit!=0)
                for(j=0;j<LANES*16;j=j+1) if(dut.regs[j]!==expected_regs[j]) $fatal(1,"register %0d got=%h expected=%h",j,dut.regs[j],expected_regs[j]);
            $display("PASS run=%0d lanes=%0d cycles=%0d instructions=%0d requests=%0d error=%0d",run_index,LANES,cycles,instructions,requests,error);
            @(negedge clk); if(done) $fatal(1,"done must pulse once");
        end
        // Reset must revoke the loaded program; a new launch cannot execute stale code.
        reset=1; @(negedge clk); reset=0; entry=0; instruction_limit=10;
        launch; while(!done) @(negedge clk);
        if(error!=2 || mem_valid || busy) $fatal(1,"reset failed to revoke program");
        $finish;
    end
endmodule
