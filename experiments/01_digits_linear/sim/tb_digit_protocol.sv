`timescale 1ns/1ps
`include "sim_config.vh"
module tb_digit_protocol;
    reg clk=0,rst=1,rx_valid=0,rx_error=0,tx_ready=0;
    reg [7:0] rx_data=0;
    wire [7:0] tx_data;
    wire tx_valid,completed,error;
    always #5 clk=~clk;
    digit_protocol #(.TIMEOUT_CYCLES(32)) dut(.*);
    reg [7:0] requests[0:`NUM_CASES*69-1],responses[0:`NUM_CASES*46-1],bad_pixels[0:68];
    integer testcase=0,received=0,cycles=0,starts=0,k,n,limit;
    reg allow_response=0;
    always @(negedge clk) begin
        cycles=cycles+1;
        tx_ready=(cycles%7!=0); // receiver applies deterministic backpressure
    end
    always @(posedge clk) if(!rst) begin
        if(dut.start) starts=starts+1;
        if(tx_valid && tx_ready) begin
            if(!allow_response || received>=46) $fatal(1,"unexpected response");
            if(tx_data!==responses[testcase*46+received])
                $fatal(1,"case=%0d byte=%0d got=%02x expected=%02x",testcase,received,tx_data,responses[testcase*46+received]);
            received=received+1;
        end
    end
    task put(input [7:0] value);
        begin @(negedge clk); rx_valid=1; rx_data=value;
            @(negedge clk); rx_valid=0;
        end
    endtask
    task valid_frame(input integer index);
        begin
            testcase=index; received=0; allow_response=1;
            for(k=0;k<69;k=k+1) put(requests[index*69+k]);
            limit=0;
            while(received<46) begin
                @(negedge clk); limit=limit+1;
                if(limit>1500) $fatal(1,"response timeout");
            end
            repeat(20) @(negedge clk);
            allow_response=0;
        end
    endtask
    initial begin
        $readmemh("requests.mem",requests); $readmemh("responses.mem",responses);
        $readmemh("invalid_pixel.mem",bad_pixels);
        repeat(4) @(negedge clk); rst=0;
        put(8'h11); put(8'h22); // harmless noise before header
        for(n=0;n<`NUM_CASES;n=n+1) valid_frame(n);
        if(error || !completed || starts!=`NUM_CASES) $fatal(1,"normal-frame state error");
        // Bad checksum, invalid pixel with good CRC, bad length, partial frame timeout.
        for(k=0;k<69;k=k+1) put(requests[k] ^ ((k==68)?8'h01:8'h00));
        for(k=0;k<69;k=k+1) put(bad_pixels[k]);
        put(8'ha5); put(8'h5a); put(0); put(63);
        for(k=0;k<10;k=k+1) put(requests[k]);
        repeat(50) @(negedge clk);
        put(8'ha5); put(8'h5a);
        @(negedge clk); rx_error=1;
        @(negedge clk); rx_error=0;
        repeat(1500) @(negedge clk);
        if(!error || starts!=`NUM_CASES) $fatal(1,"bad frame started inference");
        valid_frame(0); // a complete valid frame recovers without a reset
        rst=1; repeat(4) @(negedge clk); rst=0;
        if(error || completed) $fatal(1,"status not reset");
        valid_frame(1);
        $display("PASS: %0d protocol frames matched incl. all scores; invalid CRC/pixel/length, timeout, RX error and recovery.",`NUM_CASES+2);
        $finish;
    end
    initial begin #20000000; $fatal(1,"global timeout"); end
endmodule
