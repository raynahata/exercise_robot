#!/usr/bin/env python3
import argparse
import os
import re
import shlex
import sys

import yaml


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CONFIG_PATH = os.path.join(ROOT, 'study_config.yaml')
EXERCISE_CONFIG_PATH = os.path.join(
    ROOT, 'exercise_coach', 'coach_main_folder', 'config', 'study_session_config.yaml'
)
SOCIAL_CONFIG_PATH = os.path.join(
    ROOT, 'social_buddy', 'scripts', 'SocialCoach-main', 'config.yaml'
)


def load_config():
    with open(CONFIG_PATH, 'r') as config_file:
        return yaml.safe_load(config_file) or {}


def require(config, *keys):
    current = config
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            raise KeyError('Missing study_config.yaml value: {}'.format('.'.join(keys)))
        current = current[key]
    return current


def participant_number(participant):
    try:
        return int(str(participant.get('id', '0')))
    except ValueError:
        return 0


def safe_path_part(value):
    cleaned = re.sub(r'[^A-Za-z0-9_.-]+', '_', str(value)).strip('_')
    return cleaned or 'unknown'


def participant_output_dir(config):
    participant = require(config, 'participant')
    participant_id = safe_path_part(participant.get('id', '0'))
    week_number = int(participant.get('week_number', 0))
    participant_root = 'test_participants' if participant.get('test', False) else 'participants'
    output_base = os.environ.get('EXERCISE_ROBOT_OUTPUT_BASE', os.path.join(ROOT, 'study_outputs'))
    return os.path.join(
        output_base,
        participant_root,
        'participant_{}'.format(participant_id),
        'week_{}'.format(week_number),
    )


def build_exercise_config(config):
    participant = require(config, 'participant')
    exercise = config.get('exercise_coach', {})
    rosbag = exercise.get('rosbag', {})

    participant_config = {
        'id': str(participant.get('id', '0')),
        'age': int(participant.get('age', 26)),
        'resting_hr': int(participant.get('resting_hr', 97)),
        'week_number': int(participant.get('week_number', 1)),
    }
    if 'max_hr' in participant:
        participant_config['max_hr'] = int(participant['max_hr'])

    return {
        'participant': participant_config,
        'session': {
            'robot_style': int(exercise.get('robot_style', 5)),
            'round_num': int(exercise.get('round_num', 1)),
            'set_length': int(exercise.get('set_length', 40)),
            'rest_time': int(exercise.get('rest_time', 40)),
            'exercise_list': list(exercise.get(
                'exercise_list',
                ['bicep_curls', 'bicep_curls', 'lateral_raises', 'lateral_raises'],
            )),
            'verbal_cadence': int(exercise.get('verbal_cadence', 2)),
            'nonverbal_cadence': int(exercise.get('nonverbal_cadence', 2)),
        },
        'rosbag': {
            'enabled': bool(rosbag.get('enabled', True)),
            'record_all': bool(rosbag.get('record_all', True)),
            'topics': list(rosbag.get('topics', [])),
            'output_dir': rosbag.get('output_dir', 'bags'),
            'restart_on_exit': bool(rosbag.get('restart_on_exit', True)),
            'restart_delay_sec': int(rosbag.get('restart_delay_sec', 5)),
        },
    }


def build_social_config(config):
    participant = require(config, 'participant')
    pepper = require(config, 'pepper')
    social = config.get('social_buddy', {})

    return {
        'pepper_ip': str(pepper.get('ip', '127.0.0.1')),
        'pepper_port': int(pepper.get('port', 9559)),
        'participant_number': participant_number(participant),
        'week_number': int(participant.get('week_number', 0)),
        'generate_summary_after_session': bool(social.get('generate_summary_after_session', False)),
        'summary_prompt_file': social.get('summary_prompt_file', 'summaryPrompt.txt'),
        'summary_model': social.get('summary_model', 'gpt-4o'),
        'summary_max_tokens': int(social.get('summary_max_tokens', 250)),
    }


def write_yaml(path, data):
    with open(path, 'w') as config_file:
        yaml.safe_dump(data, config_file, default_flow_style=False, sort_keys=False)


def apply_config(config):
    write_yaml(EXERCISE_CONFIG_PATH, build_exercise_config(config))
    write_yaml(SOCIAL_CONFIG_PATH, build_social_config(config))


def print_env(config):
    pepper = require(config, 'pepper')
    env = {
        'PEPPER_IP': str(pepper.get('ip', '127.0.0.1')),
        'PEPPER_PORT': str(int(pepper.get('port', 9559))),
        'EXERCISE_ROBOT_OUTPUT_DIR': participant_output_dir(config),
    }
    for key, value in env.items():
        print('export {}={}'.format(key, shlex.quote(value)))


def print_order(config):
    participant = require(config, 'participant')
    group = str(participant.get('group', 'A')).upper()
    groups = require(config, 'study_order', 'groups')
    if group not in groups:
        raise KeyError('Group {} is not defined under study_order.groups'.format(group))
    for step in groups[group]:
        print(step)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--env', action='store_true')
    parser.add_argument('--order', action='store_true')
    args = parser.parse_args()

    config = load_config()
    try:
        if args.apply:
            apply_config(config)
        if args.env:
            print_env(config)
        if args.order:
            print_order(config)
    except Exception as exc:
        print('study_config.yaml error: {}'.format(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
