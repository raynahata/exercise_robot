# pepper_exercise_coach

ROS package for running the Pepper adaptive exercise-coaching study. The system tracks participant arm motion, receives Polar heart-rate data, sends speech/action requests to Pepper, records session data, and optionally records a rosbag for post-session review.

This package is usually used together with the sibling `polar_hr_ros` package.

## Main Files

- `launch/pepper_exercise_coach.launch`: starts pose tracking, the adaptive study session, the heart-rate monitor, and `rqt_gui`.
- `scripts/study_session_pepper_adaptive.py`: top-level study-session runner. It loads session config, starts/stops rosbag recording, controls set/rest timing, and saves session data.
- `scripts/exercise_manager.py`: exercise state, repetition detection, feedback selection, adaptive-controller calls, HRR calculation, and ROS publishers/subscribers.
- `scripts/adaptive_controller.py`: contextual bandit process used when `robot_style: 5`.
- `scripts/pose_tracking.py`: publishes `/joint_angles` from pose tracking.
- `scripts/pepper_controller.py`: Python 2 Pepper/NAOqi bridge. Run this separately with the NAOqi Python path.
- `config/study_session_config.yaml`: participant/session/rosbag config to edit before each session.
- `config/computer_config.yaml`: exercise thresholds, angle definitions, and feedback behavior parameters.
- `config/pepper_controller_config.yaml`: Pepper motion/action definitions.

## Before Each Session

Edit `config/study_session_config.yaml`.

```yaml
participant:
  id: "0"
  age: 26
  resting_hr: 97
  week_number: 1
  # Optional. If omitted, max_hr is calculated as 220 - age.
  # max_hr: 194

session:
  robot_style: 5
  round_num: 1
  set_length: 40
  rest_time: 40
  exercise_list:
    - bicep_curls
    - bicep_curls
    - lateral_raises
    - lateral_raises
  verbal_cadence: 2
  nonverbal_cadence: 2

rosbag:
  enabled: true
  record_all: true
  output_dir: bags
  restart_on_exit: true
  restart_delay_sec: 5
```

Important notes:

- `robot_style: 5` enables adaptive behavior. Other styles use fixed behavior.
- `round_num` should be `1` or greater for study rounds. Round `0` is considered intro.
- `resting_hr`, `age`, and optional `max_hr` affect HRR and adaptive context.
- The participant ID is passed into `adaptive_controller.py`, so you no longer need to edit participant ID in two files.

## Running The Study

Terminal 1: launch the ROS study nodes.

```bash
source ~/pepper_ws/devel/setup.bash
roslaunch pepper_exercise_coach pepper_exercise_coach.launch
```

Terminal 2: run the Pepper controller bridge.

```bash
source ~/pepper_ws/devel/setup.bash
export PYTHONPATH=${PYTHONPATH}:../../dependencies/pynaoqi-python2.7-2.8.6.23-linux64-20191127_152327/lib/python2.7/site-packages
python2 ~/pepper_ws/src/pepper_exercise_coach/scripts/pepper_controller.py
```

The study session script will pause for keyboard input before starting the round. Follow the terminal prompts.

## Data Outputs

Session outputs are written inside the package directory:

- `logs/Participant_<id>_Week_<week>_Style_<style>_Round_<round>_<timestamp>.log`
- `data/Participant_<id>_Week_<week>_Style_<style>_Round_<round>_<timestamp>.pickle`
- `models/Participant_<id>_<timestamp>.pickle` for adaptive-controller training state
- `bags/Participant_<id>_Week_<week>_Style_<style>_Round_<round>_<timestamp>.bag` when rosbag is enabled

The session pickle includes a `session_metadata` entry with participant/session config values, plus per-set data such as joint angles, peaks, feedback, performance, heart rates, HRR, contexts, actions, and rewards.

## Rosbag Behavior

Rosbag recording is controlled by `config/study_session_config.yaml`.

Default behavior records all topics:

```yaml
rosbag:
  enabled: true
  record_all: true
```

To record only specific topics:

```yaml
rosbag:
  enabled: true
  record_all: false
  topics:
    - /heart_rate
    - /joint_angles
    - /pepper_text_request
    - /pepper_action_request
    - /pepper_camera/image_raw
```

If rosbag exits during a session, `study_session_pepper_adaptive.py` logs the failure and restarts recording when `restart_on_exit: true`. Restarted bags get a `_restart_<n>` suffix so the earlier bag is not overwritten.

## Heart-Rate Dropout Handling

Heart-rate data comes from `/heart_rate`.

If the heart-rate stream drops out, the session should continue. `ExerciseManager` uses:

1. The latest live heart-rate sample.
2. The last valid heart-rate sample if no new sample is available.
3. Resting heart rate if no sensor sample has ever arrived.

Fallback and stale-HR cases are logged. Per-frame heart-rate source labels are saved under each set as `heart_rate_sources`.

## Useful ROS Topics

- `/heart_rate`: `std_msgs/Int32`, published by `polar_hr_ros`.
- `/joint_angles`: joint-angle array from pose tracking.
- `/pepper_text_request`: text sent to Pepper speech/tablet.
- `/pepper_action_request`: action labels sent to Pepper movement controller.
- `/pepper_camera/image_raw`: Pepper camera image stream.

## Common Checks

Check whether the heart-rate monitor is publishing:

```bash
rostopic echo /heart_rate
```

Check whether pose tracking is publishing:

```bash
rostopic hz /joint_angles
```

Check Pepper speech/action requests:

```bash
rostopic echo /pepper_text_request
rostopic echo /pepper_action_request
```

Check active ROS nodes:

```bash
rosnode list
```

## Troubleshooting

If Pepper does not speak or move:

- Confirm `pepper_controller.py` is running in the Python 2/NAOqi terminal.
- Confirm the Pepper IP address in `scripts/pepper_controller.py`.
- Watch `/pepper_text_request` and `/pepper_action_request` to verify the study session is publishing.

If heart-rate data stops:

- The session should continue using fallback HR values.
- Check `/heart_rate` and the Polar Bluetooth connection.
- Review the session log for `No heart-rate samples` or `Heart-rate data is stale`.

If rosbag stops:

- The session log should show the exit code and restart attempt.
- Restarted bag files are written with `_restart_<n>` in the filename.
- If recording all topics is too heavy, set `record_all: false` and use the topic list in `study_session_config.yaml`.

If adaptive mode fails:

- `robot_style: 5` starts `scripts/adaptive_controller.py` as a subprocess.
- The session will keep the current robot style if the adaptive controller returns an invalid action.
- Adaptive models are saved in `models/` using the participant ID from `study_session_config.yaml`.

## Developer Notes

- Keep participant/session values in `config/study_session_config.yaml`; avoid reintroducing hardcoded study parameters in scripts.
- `study_session_pepper_adaptive.py` owns the session lifecycle and rosbag process.
- `exercise_manager.py` should remain tolerant of missing sensor data. Feedback and adaptive context should not assume heart-rate lists are non-empty.
- `pepper_controller.py` is Python 2 because it depends on NAOqi.
- Run a syntax check after edits:

```bash
python3 -m py_compile scripts/study_session_pepper_adaptive.py scripts/exercise_manager.py scripts/adaptive_controller.py
```
