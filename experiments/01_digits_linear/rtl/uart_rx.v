`timescale 1ns/1ps
// 8N1 receiver. CLKS_PER_BIT must be >= 8. Outputs are one-clock pulses.
module uart_rx #(parameter integer CLKS_PER_BIT=434) (
    input wire clk, input wire rst, input wire rx,
    output reg [7:0] data, output reg valid, output reg framing_error
);
    (* ASYNC_REG = "TRUE" *) reg [1:0] rx_sync=2'b11;
    always @(posedge clk) begin
        if(rst) rx_sync<=2'b11;
        else rx_sync<={rx_sync[0],rx};
    end
    localparam IDLE=0, START=1, DATA=2, STOP=3, WAIT_HIGH=4;
    localparam WIDTH=$clog2(CLKS_PER_BIT);
    reg [2:0] state;
    reg [WIDTH-1:0] timer;
    reg [2:0] bit_index;
    always @(posedge clk) begin
        if(rst) begin
            state<=IDLE; timer<=0; bit_index<=0;
            data<=0; valid<=0; framing_error<=0;
        end else begin
            valid<=0; framing_error<=0;
            case(state)
                IDLE: if(!rx_sync[1]) begin
                    timer<=CLKS_PER_BIT/2-1; state<=START;
                end
                START: if(timer!=0) timer<=timer-1'b1;
                else if(rx_sync[1]) state<=IDLE; // reject short low glitch
                else begin
                    timer<=CLKS_PER_BIT-1; bit_index<=0; state<=DATA;
                end
                DATA: if(timer!=0) timer<=timer-1'b1;
                else begin
                    data[bit_index]<=rx_sync[1]; timer<=CLKS_PER_BIT-1;
                    if(bit_index==7) state<=STOP;
                    else bit_index<=bit_index+1'b1;
                end
                STOP: if(timer!=0) timer<=timer-1'b1;
                else if(rx_sync[1]) begin valid<=1; state<=IDLE; end
                else begin framing_error<=1; state<=WAIT_HIGH; end
                WAIT_HIGH: if(rx_sync[1]) state<=IDLE;
                default: state<=IDLE;
            endcase
        end
    end
endmodule
