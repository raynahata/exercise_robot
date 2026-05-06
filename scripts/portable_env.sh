#!/usr/bin/env bash
set -euo pipefail

export EXERCISE_ROBOT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export EXERCISE_ROBOT_OUTPUT_BASE="${EXERCISE_ROBOT_OUTPUT_BASE:-${EXERCISE_ROBOT_ROOT}/study_outputs}"
export EXERCISE_ROBOT_OUTPUT_DIR="${EXERCISE_ROBOT_OUTPUT_DIR:-${EXERCISE_ROBOT_OUTPUT_BASE}}"

if [ -f /opt/ros/noetic/setup.bash ]; then
  # shellcheck disable=SC1091
  source /opt/ros/noetic/setup.bash
elif [ -f /opt/ros/melodic/setup.bash ]; then
  # shellcheck disable=SC1091
  source /opt/ros/melodic/setup.bash
fi

if [ -f "${EXERCISE_ROBOT_ROOT}/runtime_ws/devel/setup.bash" ]; then
  # shellcheck disable=SC1091
  source "${EXERCISE_ROBOT_ROOT}/runtime_ws/devel/setup.bash"
fi

NAOQI_SDK="${EXERCISE_ROBOT_ROOT}/dependencies/pynaoqi-python2.7-2.8.6.23-linux64-20191127_152327"
export NAOQI_PYTHONPATH="${NAOQI_SDK}/lib/python2.7/site-packages"
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}:${NAOQI_SDK}/lib"

mkdir -p "${EXERCISE_ROBOT_OUTPUT_BASE}"
