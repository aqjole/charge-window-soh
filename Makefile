PY      := .venv/bin/python
DATA    := data/raw/Oxford_Battery_Degradation_Dataset_1.mat
DATA_URL := https://ora.ox.ac.uk/objects/uuid:03ba4b01-cfed-46d3-9b1a-7d4a7bdf6fac/files/m5ac36a1e2073852e4f1f7dee647909a7
export PYTHONPATH := src

.PHONY: venv data test audit validate degrade reproduce clean

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

reproduce: test audit validate degrade

clean:
	rm -rf results/*.png results/*.csv results/*.md
