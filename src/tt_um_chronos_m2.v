/* Copyright 2026 CHRONOS contributors. SPDX-License-Identifier: Apache-2.0 */
`default_nettype none
`timescale 1ns/1ps
module tt_um_chronos_m2 #(
    parameter integer GUARDS_ENABLED=0
) (
    input wire [7:0] ui_in, uio_in,
    output wire [7:0] uo_out, uio_out, uio_oe,
    input wire ena, clk, rst_n
);
    reg [31:0] stage;
    reg [3:0] nibble_count, address;
    reg format_fault;
    reg [119:0] snapshot;
    wire [2:0] command=ui_in[6:4];
    wire ready, halted, epoch, busy, accepted, executed, sampled;
    wire [3:0] pc, occupancy;
    wire [31:0] time_now, cursor;
    wire [23:0] gpio;
    wire [6:0] faults;
    wire [7:0] status={format_fault,sampled,executed,accepted,busy,epoch,ready,halted};
    wire write_request=ena && command==2 && nibble_count==8 && ready;
    wire start_request=ena && command==7;
    wire _unused_write, _unused_start, _unused_retired, _unused_stalled, _unused_rejected;
    wire _unused_normal, _unused_false, _unused_true, _unused_miss, _unused_pa, _unused_pr;
    wire [31:0] _unused_instruction, _unused_origin, _unused_generations;
    wire [3:0] _unused_active, _unused_resolved, _unused_values;
    wire [15:0] _unused_refs;
    wire [7:0] _unused_sample;
    chronos_programmable_core #(.GUARDS_ENABLED(GUARDS_ENABLED)) core (
        .clk(clk),.rst_n(rst_n),.gpio_in(uio_in),.program_write(write_request),.program_start(start_request),
        .program_address(address),.program_data(stage),.control_ready(ready),
        .write_accepted(_unused_write),.start_accepted(_unused_start),.halted(halted),
        .instruction_retired(_unused_retired),.stalled(_unused_stalled),.sampled(sampled),
        .pc(pc),.instruction(_unused_instruction),.origin(_unused_origin),.cursor(cursor),
        .time_now(time_now),.gpio_state(gpio),.occupancy(occupancy),.faults(faults),.epoch_closed(epoch),
        .accepted(accepted),.rejected(_unused_rejected),.executed(executed),
        .normal_executed(_unused_normal),.false_executed(_unused_false),.true_executed(_unused_true),
        .guard_missed(_unused_miss),.predicate_accepted(_unused_pa),.predicate_rejected(_unused_pr),
        .predicate_active_state(_unused_active),.predicate_resolved_state(_unused_resolved),
        .predicate_value_state(_unused_values),.predicate_generation_state(_unused_generations),
        .predicate_refcount_state(_unused_refs),.sampler_busy(busy),.sample_word(_unused_sample)
    );
    always @(posedge clk) begin
        if(!rst_n) begin stage<=0; nibble_count<=0; address<=0; format_fault<=0; snapshot<=0; end
        else if(ena) case(command)
            1: begin
                stage<={ui_in[3:0],stage[31:4]};
                if(nibble_count<9) nibble_count<=nibble_count+1'b1;
            end
            2: begin
                nibble_count<=0;
                if(nibble_count!=8 || !ready) format_fault<=1;
                else address<=address+1'b1;
            end
            3: begin stage<=0; nibble_count<=0; end
            4: snapshot<={gpio,cursor,time_now,4'b0,occupancy,4'b0,pc,1'b0,faults,status};
            5: snapshot<={8'b0,snapshot[119:8]};
            6: address<=ui_in[3:0];
            7: if(!ready) format_fault<=1;
            default: begin end
        endcase
    end
    assign uo_out=ena ? (ui_in[7] ? snapshot[7:0] : gpio[7:0]) : 0;
    assign uio_out=ena ? gpio[15:8] : 0;
    assign uio_oe=ena ? gpio[23:16] : 0;
endmodule
