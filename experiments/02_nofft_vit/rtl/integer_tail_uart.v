`timescale 1ns/1ps
// Request C3 3C | seq16 LE | 192 int16 LE | CRC16 LE.
// Reply 3C C3 | seq16 LE | status8 | 42*(acc48 LE,y16 LE,flags8) | CRC16 LE.
// CRC-16/CCITT-FALSE: init FFFF, polynomial 1021, no final xor; header excluded.
module integer_tail_uart #(parameter CLKS_PER_BIT=434,parameter TIMEOUT_CYCLES=5000000)(
    input wire clk,reset,rx,output wire tx,output reg completed,error
);
    wire [7:0] rx_data;wire rx_valid,rx_error,tx_ready;
    reg [7:0] tx_data;wire tx_valid;
    uart_rx #(.CLKS_PER_BIT(CLKS_PER_BIT)) u_rx(.clk(clk),.rst(reset),.rx(rx),.data(rx_data),.valid(rx_valid),.framing_error(rx_error));
    uart_tx #(.CLKS_PER_BIT(CLKS_PER_BIT)) u_tx(.clk(clk),.rst(reset),.data(tx_data),.valid(tx_valid),.ready(tx_ready),.tx(tx));
    localparam SYNC0=0,SYNC1=1,BODY=2,LAUNCH=3,COMPUTE=4,REPLY=5;
    reg [2:0] state;
    reg [8:0] rx_index;reg [7:0] low_byte,crc_low,status;
    reg [15:0] sequence_id,rx_crc,tx_crc;
    reg [8:0] tx_index;
    reg [5:0] tx_record;reg [3:0] tx_byte;
    reg [23:0] timeout_count;
    reg [71:0] results[0:41];
    wire input_we=state==BODY && rx_valid && !rx_error && rx_index>=3 && rx_index<=385 && rx_index[0];
    wire [7:0] input_addr=(rx_index-9'd3)>>1;
    wire engine_ready,engine_done,result_valid,result_sat,result_error;
    wire [5:0] result_index;wire signed [47:0] result_acc;wire signed [15:0] result_y;
    integer_tail_engine u_engine(.clk(clk),.reset(reset),.input_we(input_we),.input_addr(input_addr),
        .input_data({rx_data,low_byte}),.start(state==LAUNCH),.ready(engine_ready),.done(engine_done),
        .result_valid(result_valid),.result_ready(1'b1),.result_index(result_index),
        .result_acc(result_acc),.result_y(result_y),.result_sat(result_sat),.result_error(result_error));
    function [15:0] crc_byte;
        input [15:0] crc;input [7:0] data;integer i;reg [15:0] value;
        begin
            value=crc^{data,8'b0};
            for(i=0;i<8;i=i+1) value=value[15] ? (value<<1)^16'h1021 : value<<1;
            crc_byte=value;
        end
    endfunction
    assign tx_valid=state==REPLY;
    always @* begin
        case(tx_index)
            0:tx_data=8'h3c;
            1:tx_data=8'hc3;
            2:tx_data=sequence_id[7:0];
            3:tx_data=sequence_id[15:8];
            4:tx_data=status;
            383:tx_data=tx_crc[7:0];
            384:tx_data=tx_crc[15:8];
            default:tx_data=(status==1) ? 8'b0 : results[tx_record][tx_byte*8 +: 8];
        endcase
    end
    always @(posedge clk) begin
        if(reset) begin
            state<=SYNC0;completed<=0;error<=0;rx_index<=0;low_byte<=0;crc_low<=0;
            status<=0;sequence_id<=0;rx_crc<=16'hffff;tx_crc<=16'hffff;
            tx_index<=0;tx_record<=0;tx_byte<=0;timeout_count<=0;
        end else begin
            if(result_valid) begin
                results[result_index]<={6'b0,result_error,result_sat,result_y,result_acc};
                if(result_error) begin status<=2;error<=1;end
            end
            if(state==SYNC1 || state==BODY) begin
                if(rx_valid) timeout_count<=0;else timeout_count<=timeout_count+1'b1;
            end else timeout_count<=0;
            if(rx_error && (state==SYNC0 || state==SYNC1 || state==BODY)) begin state<=SYNC0;error<=1;end
            else if((state==SYNC1 || state==BODY) && !rx_valid && timeout_count==TIMEOUT_CYCLES-1) begin
                state<=SYNC0;error<=1;
            end else case(state)
                SYNC0: if(rx_valid && rx_data==8'hc3) state<=SYNC1;
                SYNC1: if(rx_valid) begin
                    if(rx_data==8'h3c) begin state<=BODY;rx_index<=0;rx_crc<=16'hffff;completed<=0;end
                    else if(rx_data!=8'hc3) state<=SYNC0;
                end
                BODY: if(rx_valid) begin
                    if(rx_index<386) begin
                        rx_crc<=crc_byte(rx_crc,rx_data);
                        if(rx_index==0) sequence_id[7:0]<=rx_data;
                        else if(rx_index==1) sequence_id[15:8]<=rx_data;
                        else if(!rx_index[0]) low_byte<=rx_data;
                    end else if(rx_index==386) crc_low<=rx_data;
                    else begin
                        tx_index<=0;tx_record<=0;tx_byte<=0;tx_crc<=16'hffff;
                        if({rx_data,crc_low}!=rx_crc) begin status<=1;error<=1;state<=REPLY;end
                        else begin status<=0;state<=LAUNCH;end
                    end
                    rx_index<=rx_index+1'b1;
                end
                LAUNCH: if(engine_ready) state<=COMPUTE;
                COMPUTE: if(engine_done) begin
                    tx_index<=0;tx_record<=0;tx_byte<=0;tx_crc<=16'hffff;state<=REPLY;
                end
                REPLY: if(tx_ready) begin
                    if(tx_index>=2 && tx_index<=382) tx_crc<=crc_byte(tx_crc,tx_data);
                    if(tx_index>=5 && tx_index<=382) begin
                        if(tx_byte==8) begin tx_byte<=0;if(tx_record<41) tx_record<=tx_record+1'b1;end
                        else tx_byte<=tx_byte+1'b1;
                    end
                    if(tx_index==384) begin state<=SYNC0;if(status==0) completed<=1;end
                    else tx_index<=tx_index+1'b1;
                end
                default: state<=SYNC0;
            endcase
        end
    end
endmodule
