# Portable Study Runner

This folder is now the study bundle. Put this whole `exercise_robot` folder on the study computer and run everything from here.

## One-Time Setup

```bash
cd /path/to/exercise_robot
chmod +x setup_study_folder.sh run_study.sh scripts/portable_env.sh
./setup_study_folder.sh --build
```

`setup_study_folder.sh` creates `runtime_ws/`, links the two ROS packages into it, and creates one output area:

```text
study_outputs/
  participants/
    participant_24/
      week_0/
        exercise_coach/
          bags/
          data/
          logs/
          models/
        social_buddy/
          conversation_files/
          recordings/
          summaries/
  test_participants/
    participant_9001/
      week_0/
        ...
```

## Configure

The runner still consumes one active file:

```text
study_config.yaml
```

You usually do not edit it by hand. Use `prepare_participant.sh` to create or activate a saved participant YAML under `participant_configs/`. If `study_config.yaml` does not exist yet, the helper starts from `study_config.example.yaml`.

Create a first visit for a real participant:

```bash
./prepare_participant.sh new 24 --group A --age 71 --resting-hr 78
```

Activate a returning participant:

```bash
./prepare_participant.sh use 24
```

The helper updates `study_config.yaml` and saves the participant's copy at:

```text
participant_configs/24.yaml
```

By default, real participants use automatic week numbers:

```text
week_number = floor((session_date - start_date) / 7 days)
```

Use a manual session date when entering data for a different day:

```bash
./prepare_participant.sh use 24 --date 2026-05-13
```

Override or reset a week manually:

```bash
./prepare_participant.sh use 24 --week-number 2 --manual-week
./prepare_participant.sh use 24 --start-date 2026-04-29 --auto-week
```

Create test data that will not auto-advance weeks:

```bash
./prepare_participant.sh new 9001 --test --group A --week-number 0
./prepare_participant.sh use 9001 --week-number 0 --manual-week
```

Real participant outputs are written under:

```text
study_outputs/participants/participant_<id>/week_<week_number>/
```

Test outputs are written separately under:

```text
study_outputs/test_participants/participant_<id>/week_<week_number>/
```

Important active fields:

```yaml
participant:
  id: "21"
  age: 26
  resting_hr: 97
  week_number: 3
  group: A
  test: false
  start_date: "2026-04-15"
  last_session_date: "2026-05-06"
  week_mode: auto
  week_interval_days: 7

pepper:
  ip: "192.168.8.107"
  port: 9559

study_order:
  groups:
    A:
      - exercise_coach
      - social_buddy
    B:
      - social_buddy
      - exercise_coach
```

The runner copies `study_config.yaml` into the old project-specific files automatically:

```text
exercise_coach/coach_main_folder/config/study_session_config.yaml
social_buddy/scripts/SocialCoach-main/config.yaml
```

You still need the social buddy key and prompt files here:

```text
social_buddy/scripts/SocialCoach-main/chatGPT.key
social_buddy/scripts/SocialCoach-main/prompts/
```

Exercise coach thresholds and Pepper movement definitions still live here because they are not participant/session fields:

```text
exercise_coach/coach_main_folder/config/computer_config.yaml
exercise_coach/coach_main_folder/config/pepper_controller_config.yaml
```

## Run The Full Study

This runs:

1. Social intro
2. The group A or B order from `study_config.yaml`

```bash
./run_study.sh full
```

For group `A`, the default order is:

```text
intro -> exercise_coach -> social_buddy
```

For group `B`, the default order is:

```text
intro -> social_buddy -> exercise_coach
```

## Run One Part

Adaptive exercise coach:

```bash
./run_study.sh coach
```

Social buddy intro plus social exercise session:

```bash
./run_study.sh intro
./run_study.sh social
```

Social buddy exercise session only:

```bash
./run_study.sh social
```

## Python 2 And Python 3

The runner keeps the split that the projects need:

- Python 2 runs Pepper/NAOqi controllers.
- Python 3 runs ROS session logic, OpenAI/AWS social logic, pose tracking, heart rate, and adaptive control.

The vendored NAOqi SDK is loaded from:

```text
dependencies/pynaoqi-python2.7-2.8.6.23-linux64-20191127_152327/
```

The runner adds this SDK only to the Python 2 controller process, so Python 3 scripts do not accidentally import Python 2 packages.

## Existing Outputs

Older files are still in their original copied project folders. New runs go to a participant/week folder under `study_outputs/`.

To place the whole `study_outputs/` tree somewhere else:

```bash
export EXERCISE_ROBOT_OUTPUT_BASE=/some/other/output/folder
```
