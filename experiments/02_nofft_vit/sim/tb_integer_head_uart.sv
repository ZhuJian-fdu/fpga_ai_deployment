`timescale 1ns/1ps
module tb_integer_head_uart;
    reg clk=0,reset=1,rx=1;always #5 clk=~clk;
    wire tx,completed,error;
    integer_head_uart #(.CLKS_PER_BIT(8),.TIMEOUT_CYCLES(1000)) dut(.*);
    wire [7:0] received;wire received_valid,frame_error;
    uart_rx #(.CLKS_PER_BIT(8)) monitor(.clk(clk),.rst(reset),.rx(tx),.data(received),.valid(received_valid),.framing_error(frame_error));
    reg [7:0] requests[0:989],responses[0:1924];
    integer response_count=0,transaction=0,i,j;
    reg checking=0;
    always @(posedge clk) if(!reset && checking) begin
        if(frame_error) $fatal(1,"TX framing error");
        if(received_valid) begin
            if(response_count>=385 || received!==responses[transaction*385+response_count])
                $fatal(1,"Reply byte mismatch transaction=%0d byte=%0d got=%h want=%h",transaction,response_count,received,responses[transaction*385+response_count]);
            response_count=response_count+1;
        end
    end
    task send_byte(input [7:0] value);
        integer b;
        begin
            @(negedge clk);rx=0;repeat(8) @(negedge clk);
            for(b=0;b<8;b=b+1) begin rx=value[b];repeat(8) @(negedge clk);end
            rx=1;repeat(8) @(negedge clk);
        end
    endtask
    initial begin
        $readmemh("uart_requests.mem",requests);$readmemh("uart_responses.mem",responses);
        repeat(4) @(negedge clk);reset=0;
        // Prefix garbage, then a truncated request must time out and resynchronize.
        send_byte(8'h55);send_byte(8'ha5);send_byte(8'h5a);send_byte(8'h01);
        repeat(1200) @(negedge clk);
        if(!error) $fatal(1,"Partial request timeout not flagged");
        reset=1;repeat(4) @(negedge clk);reset=0;
        for(transaction=0;transaction<5;transaction=transaction+1) begin
            response_count=0;checking=1;
            for(i=0;i<198;i=i+1) send_byte(requests[transaction*198+i]);
            wait(response_count==385);repeat(20) @(negedge clk);checking=0;
            if(transaction==2 && (!error || completed)) $fatal(1,"Bad request CRC was accepted");
            if(transaction!=2 && !completed) $fatal(1,"Successful transaction not completed");
        end
        if(!error) $fatal(1,"Error latch lost");
        reset=1;repeat(4) @(negedge clk);reset=0;repeat(4) @(negedge clk);
        if(completed || error) $fatal(1,"Reset did not clear status");
        $display("PASS: UART runtime inputs, 5 replies/1925 bytes, bad CRC, timeout recovery, reset");$finish;
    end
    initial begin repeat(400000) @(posedge clk);$fatal(1,"Timeout");end
endmodule
