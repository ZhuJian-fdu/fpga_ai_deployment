`timescale 1ns/1ps
// Small FIFO absorbs short bursts and TX turnaround. No hardware flow control.
module uart_echo #(parameter integer CLKS_PER_BIT=434) (
    input wire clk, input wire rst, input wire rx,
    output wire tx, output reg received, output reg error
);
    wire [7:0] rx_data;
    wire rx_valid, framing_error, tx_ready;
    reg [7:0] fifo [0:15];
    reg [3:0] wr_ptr, rd_ptr;
    reg [4:0] count;
    wire pop=(count!=0) && tx_ready;
    wire push=rx_valid && ((count<16) || pop);
    uart_rx #(.CLKS_PER_BIT(CLKS_PER_BIT)) u_rx (
        .clk(clk),.rst(rst),.rx(rx),.data(rx_data),.valid(rx_valid),.framing_error(framing_error)
    );
    uart_tx #(.CLKS_PER_BIT(CLKS_PER_BIT)) u_tx (
        .clk(clk),.rst(rst),.data(fifo[rd_ptr]),.valid(count!=0),.ready(tx_ready),.tx(tx)
    );
    always @(posedge clk) begin
        if(rst) begin wr_ptr<=0; rd_ptr<=0; count<=0; received<=0; error<=0; end
        else begin
            if(rx_valid) received<=1;
            if(framing_error || (rx_valid && !push)) error<=1;
            if(push) begin fifo[wr_ptr]<=rx_data; wr_ptr<=wr_ptr+1'b1; end
            if(pop) rd_ptr<=rd_ptr+1'b1;
            case({push,pop})
                2'b10: count<=count+1'b1;
                2'b01: count<=count-1'b1;
                default: count<=count;
            endcase
        end
    end
endmodule
