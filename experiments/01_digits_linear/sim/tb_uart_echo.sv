`timescale 1ns/1ps
module tb_uart_echo;
    reg clk=0,rst=1,rx=1;
    always #5 clk=~clk;
    wire tx,received,error;
    uart_echo #(.CLKS_PER_BIT(32)) dut(.*);
    reg [7:0] expected[0:1023];
    reg [7:0] got;
    integer sent=0, seen=0, j, i;
    reg monitor=1;
    task send_byte(input [7:0] value, input integer bit_ns, input bit good_stop);
        integer b;
        begin
            if(good_stop) begin expected[sent]=value; sent=sent+1; end
            rx=0; #(bit_ns);
            for(b=0;b<8;b=b+1) begin rx=value[b]; #(bit_ns); end
            rx=good_stop; #(bit_ns); rx=1;
        end
    endtask
    // Independent line decoder: checks transmitted start, data and stop bits.
    initial forever begin
        @(negedge tx);
        if(monitor) begin
            #160;
            if(tx!==0) $fatal(1,"bad start bit");
            for(j=0;j<8;j=j+1) begin #320; got[j]=tx; end
            #320;
            if(tx!==1) $fatal(1,"bad stop bit");
            if(seen>=sent || got!==expected[seen])
                $fatal(1,"byte %0d: got %02x expected %02x",seen,got,expected[seen]);
            seen=seen+1;
        end
    end
    initial begin
        repeat(5) @(negedge clk); rst=0;
        #37;
        // Short start glitch must not generate a byte or error.
        rx=0; #50; rx=1; #4000;
        if(received || error || seen!=0) $fatal(1,"glitch was not rejected");
        // All byte values, continuous bursts; +/- 1% sender bit timing.
        for(i=0;i<256;i=i+1) send_byte(i,320,1);
        #10000;
        for(i=0;i<256;i=i+1) send_byte(i^8'ha5,317,1);
        #20000;
        for(i=0;i<256;i=i+1) send_byte(255-i,323,1);
        #20000;
        if(seen!=sent || error || !received) $fatal(1,"burst/status check failed");
        send_byte(8'h00,320,0); // invalid stop bit must be dropped
        #10000;
        if(!error || seen!=sent) $fatal(1,"framing error handling failed");
        send_byte(8'h5a,320,1); #5000;
        if(seen!=sent) $fatal(1,"failed to recover after framing error");
        rst=1; repeat(3) @(negedge clk); rst=0;
        #1000;
        if(error || received || tx!==1) $fatal(1,"reset did not clear status");
        send_byte(8'hc3,320,1); #5000;
        if(seen!=sent || error) $fatal(1,"post-reset echo failed");
        $display("PASS: %0d exact UART echoes, back-to-back data, +/-1%% timing, glitch, framing recovery and reset.",seen);
        $finish;
    end
    initial begin #10000000; $fatal(1,"timeout"); end
endmodule
