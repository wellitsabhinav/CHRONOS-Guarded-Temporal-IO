PYTHON ?= python3
.DEFAULT_GOAL := test

.PHONY: test model-test rtl-test diff-test lint synth formal harden
.PHONY: m1-test m1-formal m1-synth m1-experiment
m1-test:
	$(PYTHON) -m pytest model/tests/test_guarded.py -q
	$(PYTHON) scripts/run_sim.py guarded
m1-formal:
	$(PYTHON) scripts/m1_formal.py
m1-synth:
	$(PYTHON) scripts/m1_synth.py
m1-experiment:
	$(PYTHON) scripts/m1_experiment.py
test: model-test rtl-test lint
model-test:
	$(PYTHON) -m pytest model/tests -q
rtl-test:
	$(PYTHON) scripts/run_sim.py all
diff-test:
	$(PYTHON) scripts/run_sim.py core
lint:
	$(PYTHON) scripts/lint.py
synth:
	$(PYTHON) scripts/synth.py
formal:
	$(PYTHON) scripts/formal.py
harden:
	$(PYTHON) scripts/harden.py
