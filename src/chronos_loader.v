/* Copyright 2026 CHRONOS contributors. SPDX-License-Identifier: Apache-2.0 */
`default_nettype none
`timescale 1ns/1ps
module chronos_loader (
    input wire clk, rst_n, ena,
    input wire [7:0] ui_in,
    output wire event_valid,
    input wire event_ready,
    output wire event_drop,
    output wire [31:0] event_timestamp,
    output wire [23:0] event_state,
    input wire [31:0] time_now,
    input wire [23:0] gpio_state,
    input wire [3:0] occupancy,
    input wire [2:0] faults,
    input wire epoch_closed, accepted, rejected, executed,
    output wire [7:0] readback
);
    reg [55:0] stage;
    reg [3:0] nibble_count;
    reg format_fault;
    reg [71:0] snapshot;
    wire [2:0] command = ui_in[6:4];
    assign event_valid = ena && (command == 3'd2) && (nibble_count == 4'd14);
    assign event_drop = event_valid && !event_ready;
    assign event_timestamp = stage[31:0];
    assign event_state = stage[55:32];
    assign readback = snapshot[7:0];
    wire [7:0] status = {executed, accepted, event_ready, epoch_closed, format_fault, faults};
    wire [7:0] queue_status = {3'b000, rejected, occupancy};
    always @(posedge clk) begin
        if (!rst_n) begin
            stage <= 0; nibble_count <= 0; format_fault <= 0; snapshot <= 0;
        end else if (ena) begin
            case (command)
                3'd1: begin
                    stage <= {ui_in[3:0], stage[55:4]};
                    if (nibble_count < 4'd14) nibble_count <= nibble_count + 1'b1;
                end
                3'd2: begin
                    nibble_count <= 0;
                    if (nibble_count != 4'd14) format_fault <= 1'b1;
                end
                3'd3: begin stage <= 0; nibble_count <= 0; end
                3'd4: snapshot <= {gpio_state, time_now, queue_status, status};
                3'd5: snapshot <= {8'b0, snapshot[71:8]};
                default: begin end
            endcase
        end
    end
    wire _unused = &{ui_in[7], 1'b0};
endmodule
