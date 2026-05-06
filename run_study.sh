#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:-}"
CONFIG_PYTHON="${CONFIG_PYTHON:-$(command -v python3)}"

if [ -z "${MODE}" ] || { [ "${MODE}" != "full" ] && [ "${MODE}" != "intro" ] && [ "${MODE}" != "coach" ] && [ "${MODE}" != "social" ]; }; then
  echo "Usage: ./run_study.sh full|intro|coach|social" >&2
  echo "  full   = intro, then conditions in study_config.yaml group order" >&2
  echo "  intro  = social buddy intro only" >&2
  echo "  coach  = adaptive Pepper exercise coach ROS launch" >&2
  echo "  social = social buddy exercise session only" >&2
  exit 2
fi

"${ROOT}/setup_study_folder.sh" >/dev/null
if [ ! -f "${ROOT}/runtime_ws/devel/setup.bash" ]; then
  "${ROOT}/setup_study_folder.sh" --build
fi

# shellcheck disable=SC1091
source "${ROOT}/scripts/portable_env.sh"
"${CONFIG_PYTHON}" "${ROOT}/scripts/manage_participant_config.py" refresh --quiet
"${CONFIG_PYTHON}" "${ROOT}/scripts/apply_study_config.py" --apply
eval "$("${CONFIG_PYTHON}" "${ROOT}/scripts/apply_study_config.py" --env)"
mkdir -p "${EXERCISE_ROBOT_OUTPUT_DIR}"
echo "Study outputs: ${EXERCISE_ROBOT_OUTPUT_DIR}"

ROSCORE_PID=""
CONTROLLER_PID=""

cleanup() {
  if [ -n "${CONTROLLER_PID}" ] && kill -0 "${CONTROLLER_PID}" >/dev/null 2>&1; then
    kill "${CONTROLLER_PID}" >/dev/null 2>&1 || true
  fi
  if [ -n "${ROSCORE_PID}" ] && kill -0 "${ROSCORE_PID}" >/dev/null 2>&1; then
    kill "${ROSCORE_PID}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

if ! rostopic list >/dev/null 2>&1; then
  roscore &
  ROSCORE_PID="$!"
  sleep 5
fi

run_coach() {
  echo "Starting exercise coach condition..."
  PYTHONPATH="${PYTHONPATH:-}:${NAOQI_PYTHONPATH}" python2 "${ROOT}/exercise_coach/coach_main_folder/scripts/pepper_controller.py" &
  CONTROLLER_PID="$!"
  sleep 4
  roslaunch pepper_exercise_coach pepper_exercise_coach.launch
  if [ -n "${CONTROLLER_PID}" ] && kill -0 "${CONTROLLER_PID}" >/dev/null 2>&1; then
    kill "${CONTROLLER_PID}" >/dev/null 2>&1 || true
  fi
  CONTROLLER_PID=""
}

run_social_controller_script() {
  SCRIPT_NAME="$1"
  echo "Starting social buddy ${SCRIPT_NAME}..."
  cd "${ROOT}/social_buddy/scripts/SocialCoach-main"
  PYTHONPATH="${PYTHONPATH:-}:${NAOQI_PYTHONPATH}" python2 pepper_controller.py &
  CONTROLLER_PID="$!"
  sleep 4
  python3 "${SCRIPT_NAME}"
  if [ -n "${CONTROLLER_PID}" ] && kill -0 "${CONTROLLER_PID}" >/dev/null 2>&1; then
    kill "${CONTROLLER_PID}" >/dev/null 2>&1 || true
  fi
  CONTROLLER_PID=""
  cd "${ROOT}"
}

run_intro() {
  run_social_controller_script pepper_intro.py
}

run_social() {
  run_social_controller_script pepper_social.py
}

if [ "${MODE}" = "coach" ]; then
  run_coach
elif [ "${MODE}" = "intro" ]; then
  run_intro
elif [ "${MODE}" = "social" ]; then
  run_social
else
  run_intro
  for STEP in $("${CONFIG_PYTHON}" "${ROOT}/scripts/apply_study_config.py" --order); do
    if [ "${STEP}" = "exercise_coach" ]; then
      run_coach
    elif [ "${STEP}" = "social_buddy" ]; then
      run_social
    else
      echo "Unknown study step in study_config.yaml: ${STEP}" >&2
      exit 1
    fi
  done
fi
