# Makefile for Home Inventory Tracker

APP_NAME := home-app
IMAGE := fogcat5/$(APP_NAME)
TAG := latest
DEPLOYMENT := $(APP_NAME)
NAMESPACE := default

# For pushing to GitHub Container Registry:
# IMAGE := ghcr.io/ropeck/$(APP_NAME)

.PHONY: all build push deploy logs shell

all: build push deploy

build:
	docker build -t $(IMAGE):$(TAG) .

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

