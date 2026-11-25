`timescale 1ns/1ps
module acx720_v3_uart_top (
    input wire clk, input wire reset_n, input wire uart_rx,
    output wire uart_tx, output wire led0, output wire led1, output wire led2
);
    (* ASYNC_REG = "TRUE" *) reg [1:0] reset_sync=2'b11;
    always @(posedge clk or negedge reset_n) begin
        if(!reset_n) reset_sync<=2'b11;
        else reset_sync<={reset_sync[0],1'b0};
    end
    heartbeat #(.CLK_HZ(50000000)) u_heartbeat (
        .clk(clk),.rst(reset_sync[1]),.led(led0)
    );
    uart_echo #(.CLKS_PER_BIT(434)) u_echo (
        .clk(clk),.rst(reset_sync[1]),.rx(uart_rx),.tx(uart_tx),.received(led1),.error(led2)
    );
endmodule
