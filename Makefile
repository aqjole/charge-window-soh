PY      := .venv/bin/python
DATA    := data/raw/Oxford_Battery_Degradation_Dataset_1.mat
DATA_URL := https://ora.ox.ac.uk/objects/uuid:03ba4b01-cfed-46d3-9b1a-7d4a7bdf6fac/files/m5ac36a1e2073852e4f1f7dee647909a7
export PYTHONPATH := src
CFLAGS  := -std=c99 -O2 -Wall -Wextra -pedantic -Werror -ffp-contract=off

.PHONY: venv data test audit validate degrade freeze export c agree reproduce clean

venv: .venv/.done
.venv/.done: requirements.txt
	uv venv --python 3.11 .venv
	uv pip install --python $(PY) -r requirements.txt
	touch $@

data: $(DATA)
$(DATA):
	mkdir -p data/raw
	curl -L --fail -o $@ $(DATA_URL)

test: venv
	$(PY) -m pytest -q

audit: venv $(DATA)
	$(PY) -m soh.load

validate: venv $(DATA)
	$(PY) -m soh.validate

degrade: venv $(DATA)
	$(PY) -m soh.degrade

freeze: venv $(DATA)
	$(PY) -m soh.freeze

export: venv $(DATA)
	$(PY) -m soh.export

c: build/replay
build/replay: c/replay.c c/soh_est.c c/soh_est.h c/soh_model.h
	mkdir -p build
	$(CC) $(CFLAGS) -Ic -o $@ c/replay.c c/soh_est.c -lm

# freeze rewrites c/soh_model.h, so the replay tool is rebuilt after it
agree: freeze export
	$(MAKE) c
	$(PY) -m soh.agree

reproduce: test audit validate degrade agree

clean:
	rm -rf results/*.png results/*.csv results/*.md build
