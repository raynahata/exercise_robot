#!/usr/bin/env python3
import argparse
import datetime
import json
import os
import sys

import yaml

from adaptive_social_coach.adaptive_policy_manager import RuleBasedAdaptivePolicy
from adaptive_social_coach.data_logger import DataLogger
from adaptive_social_coach.exercise_perception import ExercisePerceptionModule
from adaptive_social_coach.models import InteractionState
from adaptive_social_coach.session_state_estimator import SessionStateEstimator
from adaptive_social_coach.social_dialogue import SocialDialogueModule
from adaptive_social_coach.user_model_manager import UserModelManager


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CONFIG_PATH = os.path.join(ROOT, 'study_config.yaml')


def load_config(path):
    with open(path, 'r') as config_file:
        return yaml.safe_load(config_file) or {}


def require(config, *keys):
    current = config
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            raise KeyError('Missing study_config.yaml value: {}'.format('.'.join(keys)))
        current = current[key]
    return current


def clamp(value, min_value, max_value):
    if value < min_value:
        return min_value
    if value > max_value:
        return max_value
    return value


def map_level(value):
    mapping = {
        'low': 1,
        'medium': 2,
        'high': 3,
    }
    return mapping.get(str(value).lower(), 2)


def output_data_dir():
    output_dir = os.environ.get('EXERCISE_ROBOT_OUTPUT_DIR', '')
    if output_dir:
        return os.path.join(output_dir, 'data')
    return ''


def compute_decision(config):
    participant = require(config, 'participant')
    adaptive = config.get('adaptive_single_robot', {})
    signals = adaptive.get('signals', {})
    preferences = adaptive.get('user_model', {})
    session_inputs = adaptive.get('session_state', {})

    model_dir = os.path.join(output_data_dir() or os.path.join(ROOT, 'study_outputs'), 'user_models')
    user_model_manager = UserModelManager(model_dir)
    user_model = user_model_manager.load(str(participant.get('id', '0')), preferences)

    exercise_signals = ExercisePerceptionModule().build_signals(
        heart_rate_zone=signals.get('heart_rate_zone', 'medium'),
        movement_quality=signals.get('movement_quality', 'medium'),
        form_quality=session_inputs.get('form_quality'),
        rep_progress=session_inputs.get('rep_progress'),
    )
    social_signals = SocialDialogueModule().build_signals(
        social_engagement=signals.get('social_engagement', 'medium'),
        speech_responsiveness=session_inputs.get('speech_responsiveness'),
        current_mood=session_inputs.get('current_mood'),
        current_energy=session_inputs.get('current_energy'),
    )
    merged_signals = {}
    merged_signals.update(signals)
    merged_signals.update(session_inputs)
    merged_signals.update(exercise_signals)
    merged_signals.update(social_signals)

    session_state = SessionStateEstimator().estimate(merged_signals, user_model)
    interaction_state = adaptive.get('interaction_state', InteractionState.PRE_SESSION_CHECKIN.value)
    policy_decision = RuleBasedAdaptivePolicy().decide(interaction_state, session_state, user_model)

    if policy_decision.mode == 'balanced':
        policy_decision.session_flow = str(adaptive.get('session_flow', policy_decision.session_flow))

    return {
        'timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
        'participant_id': str(participant.get('id', '0')),
        'week_number': int(participant.get('week_number', 0)),
        'strategy': str(adaptive.get('strategy', 'rule_based_v1')),
        'interaction_state': str(interaction_state),
        'signals': {
            'heart_rate_zone': str(signals.get('heart_rate_zone', 'medium')).lower(),
            'movement_quality': str(signals.get('movement_quality', 'medium')).lower(),
            'social_engagement': str(signals.get('social_engagement', 'medium')).lower(),
        },
        'session_state': session_state.to_dict(),
        'user_model': user_model.to_dict(),
        'decision': policy_decision.to_dict(),
    }


def log_decision(decision, output_dir):
    DataLogger(os.path.join(output_dir, 'data') if output_dir else '').log_jsonl(
        'adaptive_decisions.jsonl',
        decision,
    )


def print_env(decision):
    chosen = decision['decision']
    print('export ADAPTIVE_MODE={}'.format(chosen['mode']))
    print('export ADAPTIVE_SESSION_FLOW={}'.format(chosen['session_flow']))
    print('export ADAPTIVE_COACH_INTENSITY={}'.format(chosen['coach_intensity']))
    print('export ADAPTIVE_SOCIAL_WARMTH={}'.format(chosen['social_warmth']))
    print('export ADAPTIVE_SOCIAL_VERBOSITY={}'.format(chosen['social_verbosity']))
    print('export ADAPTIVE_COACH_WEIGHT={}'.format(chosen['coach_weight']))
    print('export ADAPTIVE_SOCIAL_WEIGHT={}'.format(chosen['social_weight']))
    print('export ADAPTIVE_ROBOT_STYLE={}'.format(chosen['robot_style']))
    print('export ADAPTIVE_ACTION={}'.format(chosen['action']))
    print('export ADAPTIVE_MESSAGE_STRATEGY={}'.format(chosen['message_strategy']))
    print('export ADAPTIVE_CORRECTION_FREQUENCY={}'.format(chosen['correction_frequency']))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=CONFIG_PATH)
    parser.add_argument('--env', action='store_true')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()

    try:
        config = load_config(args.config)
        decision = compute_decision(config)
        log_decision(decision, os.environ.get('EXERCISE_ROBOT_OUTPUT_DIR', ''))
        if args.env:
            print_env(decision)
        if args.json:
            print(json.dumps(decision, indent=2, sort_keys=True))
        if not args.env and not args.json:
            print(json.dumps(decision, indent=2, sort_keys=True))
    except Exception as exc:
        print('single-robot policy error: {}'.format(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
