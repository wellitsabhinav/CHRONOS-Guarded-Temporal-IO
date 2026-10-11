/* Copyright 2026 CHRONOS contributors. SPDX-License-Identifier: Apache-2.0 */
`default_nettype none
`timescale 1ns/1ps
/* TEST ONLY: edge-reactive programmable descriptor, not production CHRONOS.
 * All programming inputs are captured atomically on start. Valid descriptors
 * have compare_config[16]=1 and response_length in 1..4. compare_config uses
 * the frozen M2 mask/expected/trigger-pin/active-low-select field positions.
 * Actions have M2's full GPIO layout: {uio_oe,uio_out,uo_out}.
 * Decisions use pre-edge sync2/previous; synchronizers run through restart.
 * The sampled Boolean XOR invert_sequence[index] selects a complete action.
 * First output occurs on the trigger edge R, without an instruction delay.
 * hold_first_emit skips the first emit edge (SPI command/response boundary).
 * The final bit remains driven until synchronized select deassertion/start.
 * No timestamps, FIFO, deadline, timeout, or hidden branch delay exists.
 */
module m3_eventless (
    input wire clk, rst_n,
    input wire [7:0] gpio_in,
    input wire start,
    input wire [23:0] action0, action1, compare_config,
    input wire [3:0] invert_sequence,
    input wire [2:0] response_length,
    input wire trigger_rising,
    input wire [2:0] emit_pin,
    input wire emit_rising, hold_first_emit,
    output reg [23:0] gpio_state,
    output reg armed, active, completed,
    output reg [2:0] bit_index,
    output reg sampled, emitted, cancelled,
    output reg [7:0] sample_word,
    output wire [7:0] sync1_state, sync2_state, previous_state
);
    (* ASYNC_REG="TRUE" *) reg [7:0] sync1, sync2;
    reg [7:0] previous;
    reg [23:0] saved_action0, saved_action1, saved_config;
    reg [3:0] saved_invert;
    reg [2:0] saved_length, saved_emit_pin;
    reg saved_trigger_rising, saved_emit_rising, saved_hold_first;
    reg value, boundary_pending;
    wire selected=!saved_config[20] || !sync2[saved_config[23:21]];
    wire trigger_edge=(sync2[saved_config[19:17]] != previous[saved_config[19:17]]) &&
                      (sync2[saved_config[19:17]] == saved_trigger_rising);
    wire emit_edge=(sync2[saved_emit_pin] != previous[saved_emit_pin]) &&
                   (sync2[saved_emit_pin] == saved_emit_rising);
    wire compare_value=(sync2 & saved_config[7:0]) == saved_config[15:8];
    wire [2:0] next_index=bit_index+1'b1;
    assign sync1_state=sync1;
    assign sync2_state=sync2;
    assign previous_state=previous;

    always @(posedge clk) begin
        if(!rst_n) begin
            sync1<=0; sync2<=0; previous<=0; sample_word<=0;
            gpio_state<=0; bit_index<=0;
            armed<=0; active<=0; completed<=0;
            sampled<=0; emitted<=0; cancelled<=0;
            saved_action0<=0; saved_action1<=0; saved_config<=0;
            saved_invert<=0; saved_length<=0; saved_emit_pin<=0;
            saved_trigger_rising<=0; saved_emit_rising<=0; saved_hold_first<=0;
            value<=0; boundary_pending<=0;
        end else begin
            sync1<=gpio_in; sync2<=sync1; previous<=sync2;
            sampled<=0; emitted<=0; cancelled<=0;
            if(start) begin
                saved_action0<=action0; saved_action1<=action1; saved_config<=compare_config;
                saved_invert<=invert_sequence; saved_length<=response_length;
                saved_trigger_rising<=trigger_rising; saved_emit_pin<=emit_pin;
                saved_emit_rising<=emit_rising; saved_hold_first<=hold_first_emit;
                gpio_state<=0; bit_index<=0; sample_word<=0;
                armed<=compare_config[16] && response_length>=1 && response_length<=4;
                active<=0; completed<=0; value<=0; boundary_pending<=0;
            end else if(!selected) begin
                gpio_state[23:16]<=0;
                cancelled<=active && !completed;
                active<=0; boundary_pending<=0;
            end else if(armed && trigger_edge) begin
                armed<=0; active<=1; value<=compare_value;
                sample_word<=sync2; sampled<=1; emitted<=1; bit_index<=0;
                gpio_state<=(compare_value ^ saved_invert[0]) ? saved_action1 : saved_action0;
                completed<=saved_length==1; boundary_pending<=saved_hold_first;
            end else if(active && !completed && emit_edge) begin
                if(boundary_pending) boundary_pending<=0;
                else begin
                    bit_index<=next_index; emitted<=1;
                    gpio_state<=(value ^ saved_invert[next_index]) ? saved_action1 : saved_action0;
                    completed<=next_index==saved_length-1'b1;
                end
            end
        end
    end
endmodule
