# ABEST WMS - Multi-platform Makefile

ifeq ($(OS),Windows_NT)
    VENV_BIN = .venv/Scripts
    PYTHON = $(VENV_BIN)/python.exe
    PIP = $(PYTHON) -m pip
    RUFF = $(VENV_BIN)/ruff.exe
    BLACK = $(VENV_BIN)/black.exe
    MYPY = $(VENV_BIN)/mypy.exe
    PYTEST = $(VENV_BIN)/pytest.exe
    UVICORN = $(VENV_BIN)/uvicorn.exe
    BASH = bash
else
    VENV_BIN = .venv/bin
    PYTHON = $(VENV_BIN)/python
    PIP = $(PYTHON) -m pip
    RUFF = $(VENV_BIN)/ruff
    BLACK = $(VENV_BIN)/black
    MYPY = $(VENV_BIN)/mypy
    PYTEST = $(VENV_BIN)/pytest
    UVICORN = $(VENV_BIN)/uvicorn
    BASH = bash
endif

.PHONY: help install db-reset db-test lint typecheck test ci run-server run-client

help:
	@echo "Danh sach cac lenh ho tro:"
	@echo "  make install      - Tao moi truong ao va cai dat thu vien"
	@echo "  make db-reset     - Reset va seed CSDL (chay scripts/reset_db.sh)"
	@echo "  make db-test      - Chay kiem thu CSDL (chay scripts/run_db_tests.sh)"
	@echo "  make lint         - Kiem tra dinh dang ma nguon (Black & Ruff)"
	@echo "  make typecheck    - Kiem tra kieu tinh voi MyPy"
	@echo "  make test         - Chay cac bai kiem thu Pytest"
	@echo "  make ci           - Chay toan bo kiem tra CI (lint + typecheck + test)"
	@echo "  make run-server   - Khoi chay FastAPI server backend"
	@echo "  make run-client   - Khoi chay FastAPI client web"

install:
	python -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -r server/requirements.txt
	$(PIP) install -r client/requirements.txt

db-reset:
	$(BASH) scripts/reset_db.sh

db-test:
	$(BASH) scripts/run_db_tests.sh

lint:
	$(BLACK) --check .
	$(RUFF) check .

typecheck:
	$(MYPY) server client scripts

test:
	$(PYTEST) server/tests

ci: lint typecheck test

run-server:
	$(UVICORN) server.app.main:app --host 0.0.0.0 --port 8000 --reload

run-client:
	$(UVICORN) client.app.main:app --host 0.0.0.0 --port 3000 --reload
