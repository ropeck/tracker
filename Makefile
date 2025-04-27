# Makefile for Home Inventory Tracker

APP_NAME := home-app
IMAGE := fogcat5/$(APP_NAME)
TAG := latest
DEPLOYMENT := $(APP_NAME)
NAMESPACE := default
VENV = venv
PYTHON = $(VENV)/bin/python
PIP = $(VENV)/bin/pip
PYTEST = $(VENV)/bin/pytest

# For pushing to GitHub Container Registry:
# IMAGE := ghcr.io/ropeck/$(APP_NAME)

.PHONY: all build push deploy logs shell

all: build push deploy

dev:	$(VENV)/bin/activate

$(VENV)/bin/activate:
	@echo "🔧 Creating virtual environment..."
	python3 -m venv $(VENV)
	@echo "⬆️  Upgrading pip..."
	$(PIP) install --upgrade pip
	@echo "📦 Installing required packages..."
	$(PIP) install fastapi python-multipart uvicorn pillow openai jinja2 dotenv
	$(PIP) install -r requirements.txt

clean:
	rm -rf $(VENV)

build:
	docker build -t $(IMAGE):$(TAG) . --load

run-local: build
	docker run -it --rm -p 8000:8000 -e NOLOGIN=1 tracker-app

push:
	docker push $(IMAGE):$(TAG)

deploy:
	kubectl rollout restart deployment $(DEPLOYMENT) -n $(NAMESPACE)

logs:
	kubectl logs -l app=$(APP_NAME) --tail=100 -n $(NAMESPACE)

shell:
	kubectl exec -it deploy/$(DEPLOYMENT) -n $(NAMESPACE) -- /bin/bash

apply-secrets:
	kubectl apply -f k8s/secrets.yaml

describe:
	kubectl describe deployment $(DEPLOYMENT) -n $(NAMESPACE)

clean:
	docker rmi $(IMAGE):$(TAG)

tag:
	@read -p "Enter tag version: " version; \
	docker tag $(IMAGE):latest $(IMAGE):$$version; \
	docker push $(IMAGE):$$version

