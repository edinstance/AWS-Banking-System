.PHONY: help init test test-cov-report lint lint-fix lint-diff format format-check
help:
	$(info ${HELP_MESSAGE})
	@exit 0

init:
	pip install --upgrade -r dev-requirements.txt

test:
	pytest --cov functions --cov layers --cov-report term-missing --cov-fail-under 95 -n auto tests/

test-cov-report:
	pytest --cov functions --cov layers --cov-report term-missing --cov-report html -n auto tests/
	xdg-open htmlcov/index.html &> /dev/null || open htmlcov/index.html &> /dev/null || true

lint:
	ruff check functions tests layers/python

lint-fix:
	ruff check --fix functions tests layers/python

lint-diff:
	ruff check --diff functions tests layers/python

format:
	black functions tests layers/python

format-check:
	black --check functions tests layers/python

build:
	sam build

define HELP_MESSAGE

Usage: $ make [TARGETS]

TARGETS
	init                Initialize and install the requirements and dev-requirements for this project.
	test                Run the Unit tests.
	test-cov-report     Run the Unit tests and generate a coverage report.
	lint                Run the linter.
	lint-diff           Show the diff of the linter.
	lint-fix            Run the linter and fix the issues.
	format              Format the code using Black.
	format-check        Check the code formatting using Black.
	build               Builds the project using AWS SAM.
endef
