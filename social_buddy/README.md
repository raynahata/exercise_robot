# Social Buddy

This folder contains the social-buddy condition used by the portable study
runner. The full participant workflow starts from the repository root with
`prepare_participant.sh`, `setup_study_folder.sh`, and `run_study.sh`; see
`../README_PORTABLE_STUDY.md` for the study instructions.

The active social-buddy code intentionally keeps the Python 3 session scripts
separate from the Python 2.7 Pepper controller:

- Python 3 runs the intro/social session logic, AWS speech-to-text, OpenAI
  replies, conversation logging, and summary generation.
- Python 2.7 runs the Pepper NAOqi controller.
- ROS Noetic connects the two sides with topics.

## Active Files

```text
scripts/SocialCoach-main/
|-- AWS_STT.py             # AWS Transcribe streaming speech-to-text
|-- conv_logger.py         # Conversation text logging
|-- pepper_controller.py   # Pepper ROS/NAOqi controller, Python 2.7
|-- pepper_intro.py        # Intro conversation, Python 3
|-- pepper_social.py       # Social-buddy session, Python 3
|-- portable_paths.py      # Participant/week output folder helper
`-- summary_generator.py   # Optional conversation summary generation
```

Runtime outputs are routed through `EXERCISE_ROBOT_OUTPUT_DIR`, which is set by
the top-level runner. For real participants this becomes:

```text
study_outputs/participants/participant_<id>/week_<n>/social_buddy/
```

For test participants this becomes:

```text
study_outputs/test_participants/participant_<id>/week_<n>/social_buddy/
```

## Local Files

The following files are intentionally local and ignored by git:

- `scripts/SocialCoach-main/chatGPT.key`
- `scripts/SocialCoach-main/prompts/`
- generated config files
- recordings, conversation CSVs, logs, and summaries

Use `study_config.example.yaml` from the repository root as the committed
template. Participant-specific YAML files stay local under
`participant_configs/`.
