#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "${ROOT}/runtime_ws/src"

ln -sfn "${ROOT}/exercise_coach/coach_main_folder" "${ROOT}/runtime_ws/src/pepper_exercise_coach"
ln -sfn "${ROOT}/exercise_coach/polar_hr_ros" "${ROOT}/runtime_ws/src/polar_hr_ros"

# shellcheck disable=SC1091
source "${ROOT}/scripts/portable_env.sh"

if [ "${1:-}" = "--build" ]; then
  if ! command -v catkin_make >/dev/null 2>&1; then
    echo "catkin_make was not found. Source ROS first or install ROS on this computer." >&2
    exit 1
  fi
  cd "${ROOT}/runtime_ws"
  catkin_make
fi

cat <<EOF
Portable study folder is ready.

ROS workspace:
  ${ROOT}/runtime_ws

Study outputs:
  ${EXERCISE_ROBOT_OUTPUT_DIR}

Build the ROS workspace with:
  ./setup_study_folder.sh --build
EOF
