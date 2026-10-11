PYTHON ?= python3

.PHONY: test model-test rtl-test diff-test lint synth formal harden
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
