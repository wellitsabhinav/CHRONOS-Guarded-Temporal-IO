"""Run only the specified protocol comparison and drained-restart measurements."""
from run_sim import run


if __name__ == '__main__':
    parameters=dict(TIME_W=16,DEPTH=8,GEN_W=8,GUARDS_ENABLED=1)
    run('chronos_programmable_core','test_m2_experiments',parameters)
    run('chronos_programmable_core','test_m2_throughput',parameters)
