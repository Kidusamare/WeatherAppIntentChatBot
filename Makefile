PYTHON ?= python
PIP ?= pip

.PHONY: install install-dev test lint eval docker-build docker-run

install:
	$(PIP) install --upgrade pip setuptools wheel
	$(PIP) install -r requirements.txt

install-dev: install
	$(PIP) install -r requirements-dev.txt

test:
	$(PYTHON) -m pytest -q

eval:
	$(PYTHON) scripts/eval.py --train data/nlu.yml --eval data/eval.yml

docker-build:
	docker build -t weather-bot:latest .

docker-run:
	docker run --rm -p 8000:8000 weather-bot:latest
