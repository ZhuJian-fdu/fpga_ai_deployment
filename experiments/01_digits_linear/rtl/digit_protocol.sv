`timescale 1ns/1ps
// Stop-and-wait protocol. See docs/image_protocol.md for byte layout and CRC.
module digit_protocol #(parameter integer TIMEOUT_CYCLES=2500000) (
    input wire clk, input wire rst,
    input wire [7:0] rx_data, input wire rx_valid, input wire rx_error,
    output reg [7:0] tx_data, output wire tx_valid, input wire tx_ready,
    output reg completed, output reg error
);
    function automatic [7:0] crc8(input [7:0] crc, input [7:0] value);
        reg [7:0] c;
        integer k;
        begin
            c=crc^value;
            for(k=0;k<8;k=k+1) c=c[7] ? (c<<1)^8'h07 : c<<1;
            crc8=c;
        end
    endfunction
    localparam H0=0,H1=1,SEQ=2,LEN=3,PIXELS=4,CHECK=5,RUN=6,SEND=7,DRAIN=8;
    reg [3:0] state;
    reg [7:0] seq_id,request_crc,response_crc;
    reg [5:0] pixel_index,send_index;
    reg bad_pixel;
    reg [$clog2(TIMEOUT_CYCLES)-1:0] timer;
    reg pixel_we,start;
    reg [5:0] pixel_addr;
    reg [7:0] pixel_data;
    wire busy,done,score_valid;
    wire [3:0] prediction,score_class;
    wire signed [31:0] score_value;
    reg [31:0] scores[0:9];
    digit_classifier u_classifier(.*);
    assign tx_valid=(state==SEND);
    always @* begin
        tx_data=0;
        case(send_index)
            0: tx_data=8'h5a;
            1: tx_data=8'ha5;
            2: tx_data=seq_id;
            3: tx_data=0; // status = success
            4: tx_data={4'b0,prediction};
            45: tx_data=response_crc;
            default: if(send_index>=5 && send_index<=44)
                tx_data=scores[(send_index-5)>>2] >> (8*((send_index-5)&3));
        endcase
    end
    always @(posedge clk) begin
        if(rst) begin
            state<=H0; seq_id<=0; request_crc<=0; response_crc<=0;
            pixel_index<=0; send_index<=0; bad_pixel<=0; timer<=0;
            pixel_we<=0; pixel_addr<=0; pixel_data<=0; start<=0;
            completed<=0; error<=0;
        end else begin
            pixel_we<=0; start<=0;
            if(score_valid) scores[score_class]<=score_value;
            // The sender must wait until the complete reply has arrived.
            if(rx_valid && state>=RUN) error<=1;
            if(rx_error) error<=1;
            if(rx_error && state<RUN) begin
                error<=1;
                if(state<RUN) state<=H0;
                timer<=0;
            end else if(state>=H1 && state<=CHECK && !rx_valid && timer==TIMEOUT_CYCLES-1) begin
                state<=H0; timer<=0; error<=1;
            end else begin
                if(rx_valid || state==H0 || state>=RUN) timer<=0;
                else timer<=timer+1'b1;
                case(state)
                    H0: if(rx_valid && rx_data==8'ha5) state<=H1;
                    H1: if(rx_valid) begin
                        if(rx_data==8'h5a) state<=SEQ;
                        else if(rx_data!=8'ha5) state<=H0;
                    end
                    SEQ: if(rx_valid) begin
                        seq_id<=rx_data; request_crc<=crc8(0,rx_data); state<=LEN;
                    end
                    LEN: if(rx_valid) begin
                        if(rx_data!=64) begin state<=H0; error<=1; end
                        else begin
                            request_crc<=crc8(request_crc,rx_data);
                            pixel_index<=0; bad_pixel<=0; state<=PIXELS;
                        end
                    end
                    PIXELS: if(rx_valid) begin
                        pixel_we<=1; pixel_addr<=pixel_index; pixel_data<=rx_data;
                        request_crc<=crc8(request_crc,rx_data);
                        if(rx_data>16) bad_pixel<=1;
                        if(pixel_index==63) state<=CHECK;
                        else pixel_index<=pixel_index+1'b1;
                    end
                    CHECK: if(rx_valid) begin
                        if(rx_data!=request_crc || bad_pixel) begin state<=H0; error<=1; end
                        else begin start<=1; state<=RUN; end
                    end
                    RUN: if(done) begin
                        completed<=1; response_crc<=0; send_index<=0; state<=SEND;
                    end
                    SEND: if(tx_ready) begin
                        if(send_index>=2 && send_index<=44) response_crc<=crc8(response_crc,tx_data);
                        if(send_index==45) state<=DRAIN;
                        else send_index<=send_index+1'b1;
                    end
                    // TX ready goes low during the last byte and high after its stop bit.
                    DRAIN: if(tx_ready) state<=H0;
                    default: state<=H0;
                endcase
            end
        end
    end
endmodule
