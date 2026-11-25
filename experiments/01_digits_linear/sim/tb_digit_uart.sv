`timescale 1ns/1ps
`include "sim_config.vh"
module tb_digit_uart;
    reg clk=0,rst=1,rx=1;
    wire tx,completed,error;
    always #5 clk=~clk;
    digit_uart #(.CLKS_PER_BIT(32),.TIMEOUT_CYCLES(10000)) dut(.*);
    reg [7:0] requests[0:`NUM_CASES*69-1],responses[0:`NUM_CASES*46-1];
    reg [7:0] value;
    integer testcase=0,received=0,i,j,n,waits;
    task send_byte(input [7:0] data);
        integer b;
        begin
            rx=0; #320;
            for(b=0;b<8;b=b+1) begin rx=data[b]; #320; end
            rx=1; #320;
        end
    endtask
    initial forever begin
        @(negedge tx); #160;
        if(tx!==0) $fatal(1,"bad start");
        for(j=0;j<8;j=j+1) begin #320; value[j]=tx; end
        #320;
        if(tx!==1 || received>=46 || value!==responses[testcase*46+received])
            $fatal(1,"UART response mismatch case=%0d byte=%0d",testcase,received);
        received=received+1;
    end
    initial begin
        $readmemh("requests.mem",requests); $readmemh("responses.mem",responses);
        repeat(4) @(negedge clk); rst=0;
        #57;
        for(n=0;n<10;n=n+1) begin
            testcase=n; received=0;
            for(i=0;i<69;i=i+1) send_byte(requests[n*69+i]);
            waits=0;
            while(received<46) begin #320; waits=waits+1;
                if(waits>1000) $fatal(1,"UART timeout");
            end
            #1000;
        end
        if(error || !completed) $fatal(1,"bad status");
        $display("PASS: 10 images through UART RX, protocol, model and UART TX; 460 reply bytes matched.");
        $finish;
    end
    initial begin #10000000; $fatal(1,"global timeout"); end
endmodule
