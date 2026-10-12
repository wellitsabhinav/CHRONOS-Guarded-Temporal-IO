"""Fair lightweight CMOS5L structure screen of the two unchanged M3 responders.

Run with CHRONOS_LIBERTY pointing to the pinned CMOS5L Liberty and YOSYS on
PATH (or explicitly configured). --output selects a curated summary path.
Both designs retain all descriptor/debug ports and full 24-bit GPIO actions.
WAIT gains only the same 16 synchronizer flops present in edge-reactive RTL.
Eventless is an alias for edge-reactive; there is no third architecture.
This is mapped standard-cell area, not physical implementation or timing.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
LIBERTY_SHA256 = '34163f3e7de9f854afac57332ba06f1739b78e7ac35660a8a5ddd39c570124ad'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def state_bits(netlist, top):
    """Count sequential register widths after proc/flatten, before optimization."""
    cells = netlist['modules'][top]['cells'].values()
    sequential = [c for c in cells if c['type'].startswith(('$dff', '$adff', '$sdff'))]
    if not sequential:
        raise RuntimeError('No sequential state found in structural checkpoint')
    return sum(int(c['parameters']['WIDTH'], 2) for c in sequential)


def map_design(name, top, sources, library, yosys):
    build = ROOT / 'build' / 'eventless-synth' / name
    build.mkdir(parents=True, exist_ok=True)
    # Local basenames avoid tool/helper shell issues with host paths containing spaces.
    for source in sources:
        (build / Path(source).name).write_bytes((ROOT / source).read_bytes())
    (build / 'cells.lib').write_bytes(library.read_bytes())
    script = [
        'read_verilog ' + ' '.join(Path(source).name for source in sources),
        f'hierarchy -check -top {top}', 'proc', 'flatten',
        'tee -o storage.json stat -json', 'write_json storage_netlist.json',
        f'synth -top {top} -flatten -noabc',
        'dfflibmap -liberty cells.lib', 'abc -liberty cells.lib', 'clean',
        'read_liberty -lib cells.lib', 'check -assert',
        'tee -o stat.json stat -json -liberty cells.lib',
    ]
    (build / 'map.ys').write_text('\n'.join(script) + '\n')
    subprocess.run([yosys, '-l', 'synth.log', '-s', 'map.ys'], cwd=build,
                   check=True, stdout=subprocess.DEVNULL)
    mapped = json.loads((build / 'stat.json').read_text())['design']
    storage = json.loads((build / 'storage.json').read_text())['design']
    registers = json.loads((build / 'storage_netlist.json').read_text())
    cells = mapped['num_cells_by_type']
    memories = storage.get('num_memory_bits', 0)
    if memories or mapped.get('num_memories', 0):
        raise RuntimeError('Unexpected inferred memory in eventless comparator')
    if any(not cell.startswith('sg13cmos5l_') for cell in cells):
        raise RuntimeError('Unmapped cells remain after standard-cell mapping')
    result = dict(
        top=top, cells=mapped['num_cells'], area_um2=mapped['area'],
        flops=sum(count for cell, count in cells.items()
                  if any(part in cell for part in ('_dff', '_dfr', '_sdf'))),
        state_bits_before_optimization=state_bits(registers, top),
        synchronizer_bits=16, queue_bits=0,
        inferred_memory_bits=memories, mapped_memories=mapped.get('num_memories', 0),
        cell_types=cells, source_sha256={source: digest(ROOT / source) for source in sources},
    )
    print(f"{name}: {result['cells']} cells, {result['flops']} flops, {result['area_um2']} um2", flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='build/eventless-synth/summary.json')
    args = parser.parse_args()
    library = Path(os.environ.get('CHRONOS_LIBERTY',
                                  ROOT / '.tools/pdk/sg13cmos5l_stdcell_typ_1p20V_25C.lib'))
    if not library.is_file() or digest(library) != LIBERTY_SHA256:
        raise SystemExit('CHRONOS_LIBERTY must identify the pinned CMOS5L Liberty SHA256 ' + LIBERTY_SHA256)
    yosys = os.environ.get('YOSYS', 'yosys')
    resolved_yosys = shutil.which(yosys) or yosys
    abc_name = 'yosys-abc.exe' if os.name == 'nt' else 'yosys-abc'
    abc = Path(resolved_yosys).resolve().parent / abc_name
    versions = dict(yosys=subprocess.check_output([yosys, '-V'], text=True).strip(),
                    python=sys.version.split()[0])
    if abc.is_file():
        version_build = ROOT / 'build' / 'eventless-synth' / 'tools'
        version_build.mkdir(parents=True, exist_ok=True)
        # ABC may write its command history; keep that artifact in ignored build.
        abc_output = subprocess.check_output([str(abc), '-c', 'version'],
                                             cwd=version_build, text=True)
        versions['abc'] = next(line.strip() for line in abc_output.splitlines()
                               if 'UC Berkeley, ABC' in line)
    results = {
        'edge_reactive': map_design('edge_reactive', 'm3_eventless',
                                  ['test/m3_eventless.v'], library, yosys),
        'relative_wait': map_design('relative_wait', 'eventless_wait_synth',
                                  ['test/m3_countdown.v', 'test/eventless_wait_synth.v'], library, yosys),
    }
    summary = dict(
        scope='unchanged test-only responder RTL; paired full descriptors/debug ports; no routing/CTS/STA',
        aliases={'eventless': 'edge_reactive'}, tool_versions=versions,
        liberty_filename=library.name, liberty_sha256=digest(library),
        runner_sha256=digest(Path(__file__)),
        configuration=dict(gpio_w=24, raw_input_w=8, synchronizer_stages=2,
                           synchronizer_bits=16, max_response_length=4,
                           relative_wait_counter_w=24, descriptor_inputs_tied=False,
                           existing_debug_ports_preserved=True),
        state_count_scope='proc/flatten sequential register widths before synth optimization; includes debug state',
        queue_count_scope='no action/event queue or inferred memory in either source',
        results=results, timing_estimate=None,
        limitations=['Mapped area does not establish clock frequency, critical-path delay or physical cost.',
                     'These are test-only descriptor implementations, not qualified production peripherals.',
                     'Debug interfaces are retained in both mappings; exact ports differ with responder semantics.'],
    )
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2) + '\n')


if __name__ == '__main__':
    main()
