#
# Targets for DEVELOPMENT of Public API Server
#
include ../../scripts/common.Makefile

# Custom variables
APP_NAME     := $(notdir $(CURDIR))
APP_CLI_NAME := simcore-service-$(APP_NAME)
export APP_VERSION = $(shell cat VERSION)
SRC_DIR      := $(abspath $(CURDIR)/src/$(subst -,_,$(APP_CLI_NAME)))

.PHONY: reqs
reqs: ## compiles pip requirements (.in -> .txt)
	@$(MAKE_C) requirements reqs


.PHONY: install-dev install-prod install-ci
install-dev install-prod install-ci: _check_venv_active ## install app in development/production or CI mode
	# installing in $(subst install-,,$@) mode
	pip-sync requirements/$(subst install-,,$@).txt


PHONY: tests-unit tests-integration tests
tests: tests-unit tests-integration

tests-unit: ## runs unit tests
	# running unit tests
	@pytest -vv --exitfirst --failed-first --durations=10 --pdb $(CURDIR)/tests/unit

tests-integration: ## runs integration tests against local+production images
	# running integration tests local/(service):production images ...
	@export DOCKER_REGISTRY=local; \
	export DOCKER_IMAGE_TAG=production; \
	pytest -vv --exitfirst --failed-first --durations=10 --pdb $(CURDIR)/tests/integration


# DEVELOPMENT TOOLS ########

.env:
	cp .env-devel $@

docker-compose.yml:
	cp $(CURDIR)/tests/utils/docker-compose.yml $@

.PHONY: run-devel down
run-devel: .env docker-compose.yml down ## runs app on host with pg fixture for development [for development]
	# Starting db (under $<)
	docker-compose up --detach
	# start app (under $<)
	uvicorn simcore_service_api_server.__main__:the_app \
		--reload --reload-dir $(SRC_DIR) \
		--port=8000 --host=0.0.0.0

.PHONY: db-tables
db-tables: .env-devel ## upgrades and create tables [for development]
	# Upgrading and creating tables
	export $(shell grep -v '^#' $< | xargs  -d '\n'); \
	python3 tests/utils/init-pg.py

.PHONY: db-migration
db-migration: .env-devel ## runs discover and upgrade on running pg-db [for development]
	# Creating tables
	export $(shell grep -v '^#' $< | xargs  -d '\n'); \
	sc-pg discover && sc-pg upgrade

down: docker-compose.yml ## stops pg fixture
	# stopping extra services
	-@docker-compose -f $< down
	# killing any process using port 8000
	-@fuser --kill --verbose --namespace tcp 8000

######################


.PHONY: build
build: ## builds docker image (using main services/docker-compose-build.yml)
	@$(MAKE_C) ${REPO_BASE_DIR} target=${APP_NAME} $@


# GENERATION python client -------------------------------------------------
.PHONY: python-client generator-help
# SEE https://openapi-generator.tech/docs/usage#generate
# SEE https://openapi-generator.tech/docs/generators/python

# NOTE: assumes this repo exists
GIT_USER_ID := ITISFoundation
GIT_REPO_ID := osparc-simcore-python-client

SCRIPTS_DIR := $(abspath $(CURDIR)/../../scripts)
GENERATOR_NAME := python

# TODO: put instead to additional-props.yaml and --config=openapi-generator/python-config.yaml
ADDITIONAL_PROPS := \
	generateSourceCodeOnly=false\
	hideGenerationTimestamp=true\
	library=urllib3\
	packageName=osparc\
	packageUrl=https://github.com/$(GIT_USER_ID)/${GIT_REPO_ID}.git\
	packageVersion=$(APP_VERSION)\
	projectName=osparc-simcore-python-api
ADDITIONAL_PROPS := $(foreach prop,$(ADDITIONAL_PROPS),$(strip $(prop)))

null  :=
space := $(null) #
comma := ,

# TODO: fix this, shall be generated upon start when flag is provided



# TODO: code_samples still added by hand!
client:
	# cloning $(GIT_USER_ID)/$(GIT_REPO_ID) -> $@
	git clone git@github.com:$(GIT_USER_ID)/$(GIT_REPO_ID).git $@
	cd client; git checkout -b "upgrade-${APP_VERSION}"


python-client: client ## runs python client generator
	# download openapi.json
	curl -O http://localhost:8000/api/v0/openapi.json

	cd $(CURDIR); \
	$(SCRIPTS_DIR)/openapi-generator-cli.bash generate \
		--generator-name=$(GENERATOR_NAME) \
		--git-user-id=$(GIT_USER_ID)\
		--git-repo-id=$(GIT_REPO_ID)\
		--http-user-agent="osparc-api/{packageVersion}/{language}"\
		--input-spec=/local/openapi.json \
		--output=/local/client \
		--additional-properties=$(subst $(space),$(comma),$(strip $(ADDITIONAL_PROPS)))\
		--package-name=osparc\
		--release-note="Updated to $(APP_VERSION)"




generator-help: ## help on client-api generator
	# generate help
	@$(SCRIPTS_DIR)/openapi-generator-cli.bash help generate
	# generator config help
	@$(SCRIPTS_DIR)/openapi-generator-cli.bash config-help -g $(GENERATOR_NAME)