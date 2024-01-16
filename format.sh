#!/usr/bin/env bash

set -ex

cd $(dirname $0)/

MODULE_PATH="src"

isort $MODULE_PATH tests
autoflake --recursive --remove-all-unused-imports --remove-unused-variables --in-place $MODULE_PATH tests
black $MODULE_PATH tests
