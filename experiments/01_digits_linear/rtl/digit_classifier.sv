`timescale 1ns/1ps
// A deliberately simple sequential 64-input, 10-class integer classifier.
// Load all 64 pixels while idle, then pulse start for one clock.
// Pixel writes and start must not overlap. Pixel values must be 0..16.
module digit_classifier (
    input  wire clk,
    input  wire rst,  // synchronous, active high
    input  wire pixel_we,
    input  wire [5:0] pixel_addr,
    input  wire [7:0] pixel_data,
    input  wire start,
    output reg busy,
    output reg done,
    output reg [3:0] prediction,
    output reg score_valid,
    output reg [3:0] score_class,
    output reg signed [31:0] score_value
);
    reg [7:0] pixels [0:63];
    reg signed [7:0] weights [0:639];
    reg signed [31:0] biases [0:9];
    initial begin
        $readmemh("weights.mem", weights);
        $readmemh("biases.mem", biases);
    end

    localparam IDLE=0, BIAS=1, FETCH=2, MAC=3, EMIT=4, FINISH=5;
    reg [2:0] state;
    reg [5:0] feature_idx;
    reg [3:0] class_idx;
    reg [9:0] weight_addr;
    reg signed [8:0] pixel_q;
    reg signed [7:0] weight_q;
    wire signed [16:0] product = pixel_q * weight_q;
    wire signed [31:0] product_extended = {{15{product[16]}}, product};
    reg signed [31:0] accumulator;
    reg signed [31:0] best_score;
    reg [3:0] best_class;

    always @(posedge clk) begin
        if (rst) begin
            state <= IDLE;
            busy <= 0;
            done <= 0;
            prediction <= 0;
            score_valid <= 0;
            score_class <= 0;
            score_value <= 0;
            feature_idx <= 0;
            class_idx <= 0;
            weight_addr <= 0;
            pixel_q <= 0;
            weight_q <= 0;
            accumulator <= 0;
            best_score <= 0;
            best_class <= 0;
        end else begin
            done <= 0;
            score_valid <= 0;
            if (pixel_we && !busy && !start)
                pixels[pixel_addr] <= pixel_data;
            case (state)
                IDLE: if (start) begin
                    busy <= 1;
                    class_idx <= 0;
                    weight_addr <= 0;
                    best_class <= 0;
                    state <= BIAS;
                end
                BIAS: begin
                    accumulator <= biases[class_idx];
                    feature_idx <= 0;
                    state <= FETCH;
                end
                FETCH: begin
                    pixel_q <= $signed({1'b0, pixels[feature_idx]});
                    weight_q <= weights[weight_addr];
                    state <= MAC;
                end
                MAC: begin
                    accumulator <= accumulator + product_extended;
                    if (feature_idx == 63) begin
                        if (class_idx != 9) weight_addr <= weight_addr + 1'b1;
                        state <= EMIT;
                    end else begin
                        feature_idx <= feature_idx + 1'b1;
                        weight_addr <= weight_addr + 1'b1;
                        state <= FETCH;
                    end
                end
                EMIT: begin
                    score_valid <= 1;
                    score_class <= class_idx;
                    score_value <= accumulator;
                    if (class_idx == 0 || accumulator > best_score) begin
                        best_score <= accumulator;
                        best_class <= class_idx;
                    end
                    if (class_idx == 9) state <= FINISH;
                    else begin
                        class_idx <= class_idx + 1'b1;
                        state <= BIAS;
                    end
                end
                FINISH: begin
                    prediction <= best_class;
                    done <= 1;
                    busy <= 0;
                    state <= IDLE;
                end
                default: begin
                    state <= IDLE;
                    busy <= 0;
                end
            endcase
        end
    end
endmodule
