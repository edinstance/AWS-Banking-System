target:
	$(info ${HELP_MESSAGE})
	@exit 0

init:
	pip install -r dev-requirements.txt

test:
	pytest --cov functions --cov-report term-missing --cov-fail-under 95 -n auto tests/

test-cov-report:
	pytest --cov functions --cov-report term-missing --cov-report html --cov-fail-under 95 -n auto tests/
	open htmlcov/index.html &> /dev/null || true

lint:
	ruff check functions tests

lint-fix:
	ruff check --fix functions tests

format:
	black functions tests

define HELP_MESSAGE

Usage: $ make [TARGETS]

TARGETS
	init				Initialize and install the requirements and dev-requirements for this project.
	test				Run the Unit tests.
	test-cov-report		Run the Unit tests and generate a coverage report.
	lint				Run the linter.
	lint-fix			Run the linter and fix the issues.
	format				Format the code using Black.
endef
