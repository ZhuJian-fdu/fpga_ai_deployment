`timescale 1ns/1ps
module acx720_v3_integer_uart_top(input wire clk50m,reset_n,uart_rx,output wire uart_tx,led0,led1,led2);
    (* ASYNC_REG="TRUE" *) reg [2:0] reset_pipe=3'b111;
    always @(posedge clk50m) reset_pipe<={reset_pipe[1:0],!reset_n};
    wire reset=reset_pipe[2];
    reg [24:0] heartbeat=0;
    always @(posedge clk50m) if(reset) heartbeat<=0;else heartbeat<=heartbeat+1'b1;
    assign led1=heartbeat[24];
    integer_head_uart u_uart(.clk(clk50m),.reset(reset),.rx(uart_rx),.tx(uart_tx),.completed(led0),.error(led2));
endmodule
