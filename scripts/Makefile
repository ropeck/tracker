VENV = venv
PYTHON = $(VENV)/bin/python
PIP = $(VENV)/bin/pip
PYTEST = $(VENV)/bin/pytest

.PHONY: all setup run test clean

all: setup

setup: $(VENV)/bin/activate

$(VENV)/bin/activate:
	@echo "🔧 Creating virtual environment..."
	python3 -m venv $(VENV)
	@echo "⬆️  Upgrading pip..."
	$(PIP) install --upgrade pip
	@echo "📦 Installing required packages..."
	$(PIP) install fastapi python-multipart uvicorn

clean:
	@echo "🧹 Cleaning up..."
	rm -rf $(VENV)
	find . -type d -name "__pycache__" -exec rm -r {} +


