"""Small M2 differential suites, using the portable existing simulator runner."""
from run_sim import run

if __name__ == '__main__':
    for depth in (1,3):
        run('chronos_programmable_core','test_programmable',dict(TIME_W=16,DEPTH=depth,GEN_W=2,GUARDS_ENABLED=1))
    run('chronos_programmable_core','test_programmable',dict(TIME_W=16,DEPTH=3,GEN_W=8,GUARDS_ENABLED=0))
    run('chronos_programmable_core','test_m2_wrap',dict(TIME_W=5,DEPTH=3,GEN_W=2,GUARDS_ENABLED=1))
    run('tt_um_chronos_m2','test_m2_pins')
    run('chronos_reclaiming_engine','test_m2_reclaim',dict(TIME_W=8,DEPTH=3,GEN_W=2))
