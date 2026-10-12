/* Copyright 2026 CHRONOS contributors. SPDX-License-Identifier: Apache-2.0 */
`default_nettype none
`timescale 1ns/1ps
/* TEST ONLY: programmable edge compare plus relative WAIT/action descriptor.
 * gpio_in is the SAME pre-edge sync2 word used by the other M3 participants;
 * this module contains no additional input synchronization.
 * All programming inputs are captured on START. GPIO/OE and sticky faults
 * are preserved across START, matching frozen CHRONOS output retention.
 * START edge 0 loads first_delay-1; emissions occur at D+i*spacing.
 * Decisions must be registered before the action edge: R<=O-1.
 * A missing decision fail-stops and sets faults[0], preserving prior GPIO.
 * No absolute/global timer, timestamp, FIFO, branch delay or extra issue edge.
 * CS gates comparison only and does not cancel prepared responses.
 * Valid descriptor: edge mode, 1..4 actions, positive 24-bit WAIT distances.
 * Invalid START fail-stops with faults[1]. Reset clears all state/output.
 */
module m3_countdown (
    input wire clk, rst_n,
    input wire [7:0] gpio_in,
    input wire start,
    input wire [23:0] action0, action1, compare_config,
    input wire [3:0] invert_sequence,
    input wire [2:0] response_length,
    input wire [23:0] first_delay, spacing,
    output reg [23:0] gpio_state,
    output reg active, completed, resolved,
    output reg [2:0] bit_index,
    output reg sampled, emitted,
    output reg [7:0] sample_word,
    output reg [23:0] wait_count,
    output reg [1:0] faults,
    output wire [7:0] previous_state
);
    reg [7:0] previous;
    reg [23:0] saved_action0, saved_action1, saved_config, saved_spacing;
    reg [3:0] saved_invert;
    reg [2:0] saved_length;
    reg value;
    wire descriptor_valid=compare_config[16] && response_length>=1 && response_length<=4 &&
                          first_delay!=0 && spacing!=0;
    wire selected=!saved_config[20] || !gpio_in[saved_config[23:21]];
    wire trigger_edge=gpio_in[saved_config[19:17]] && !previous[saved_config[19:17]];
    wire compare_value=(gpio_in & saved_config[7:0]) == saved_config[15:8];
    assign previous_state=previous;
    always @(posedge clk) begin
        if(!rst_n) begin
            gpio_state<=0; previous<=0; sample_word<=0; wait_count<=0;
            bit_index<=0; faults<=0;
            active<=0; completed<=0; resolved<=0; value<=0;
            sampled<=0; emitted<=0;
            saved_action0<=0; saved_action1<=0; saved_config<=0; saved_spacing<=0;
            saved_invert<=0; saved_length<=0;
        end else begin
            previous<=gpio_in; sampled<=0; emitted<=0;
            if(start) begin
                saved_action0<=action0; saved_action1<=action1; saved_config<=compare_config;
                saved_spacing<=spacing; saved_invert<=invert_sequence; saved_length<=response_length;
                active<=descriptor_valid; completed<=0; resolved<=0; value<=0;
                sample_word<=0; bit_index<=0; wait_count<=first_delay-1'b1;
                if(!descriptor_valid) faults<=faults | 2'b10;
            end else if(active) begin
                if(!resolved && selected && trigger_edge) begin
                    resolved<=1; value<=compare_value; sample_word<=gpio_in; sampled<=1;
                end
                if(wait_count!=0) wait_count<=wait_count-1'b1;
                else if(!resolved) begin
                    active<=0; faults<=faults | 2'b01;
                end else begin
                    gpio_state<=(value ^ saved_invert[bit_index]) ? saved_action1 : saved_action0;
                    emitted<=1;
                    if(bit_index==saved_length-1'b1) begin active<=0; completed<=1; end
                    else begin bit_index<=bit_index+1'b1; wait_count<=saved_spacing-1'b1; end
                end
            end
        end
    end
endmodule
