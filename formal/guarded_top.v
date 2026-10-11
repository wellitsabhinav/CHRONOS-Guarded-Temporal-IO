`default_nettype none
module guarded_formal_top(input wire clk);
    (* anyseq *) reg rst_n,event_valid,event_drop,event_guarded;
    (* anyseq *) reg [3:0] event_timestamp;
    (* anyseq *) reg [1:0] event_state,event_state_true,event_generation;
    (* anyseq *) reg event_predicate;
    (* anyseq *) reg predicate_valid,predicate_arm,predicate_value,predicate_id;
    (* anyseq *) reg [1:0] predicate_generation;
    chronos_guarded_engine #(.TIME_W(4),.GPIO_W(2),.DEPTH(3),.PRED_W(1),.GEN_W(2)) dut (
        .clk(clk),.rst_n(rst_n),.event_valid(event_valid),.event_drop(event_drop),
        .event_guarded(event_guarded),.event_timestamp(event_timestamp),
        .event_state(event_state),.event_state_true(event_state_true),
        .event_predicate(event_predicate),.event_generation(event_generation),
        .predicate_valid(predicate_valid),.predicate_arm(predicate_arm),
        .predicate_value(predicate_value),.predicate_id(predicate_id),
        .predicate_generation(predicate_generation)
    );
endmodule
