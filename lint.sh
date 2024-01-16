#!/bin/bash
set -e

cd $(dirname $0)/

LINT_PATH="src"

isort --check-only $LINT_PATH tests
black $LINT_PATH tests --check --diff --color
flake8 $LINT_PATH
mypy $LINT_PATH
vulture $LINT_PATH --min-confidence 70
