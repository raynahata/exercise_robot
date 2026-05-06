#!/usr/bin/env python3
import argparse
import copy
from datetime import date, datetime
from datetime import timedelta
import os
import re
import sys

import yaml


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ACTIVE_CONFIG = os.path.join(ROOT, 'study_config.yaml')
EXAMPLE_CONFIG = os.path.join(ROOT, 'study_config.example.yaml')
PARTICIPANT_DIR = os.path.join(ROOT, 'participant_configs')


def today_iso():
    return date.today().isoformat()


def parse_date(value):
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        raise ValueError('Dates must use YYYY-MM-DD, got {}'.format(value))


def safe_id(participant_id):
    return re.sub(r'[^A-Za-z0-9_.-]+', '_', str(participant_id)).strip('_') or 'participant'


def participant_path(participant_id):
    return os.path.join(PARTICIPANT_DIR, '{}.yaml'.format(safe_id(participant_id)))


def load_yaml(path):
    with open(path, 'r') as config_file:
        return yaml.safe_load(config_file) or {}


def write_yaml(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as config_file:
        yaml.safe_dump(data, config_file, default_flow_style=False, sort_keys=False)


def load_active():
    if not os.path.exists(ACTIVE_CONFIG):
        return load_yaml(EXAMPLE_CONFIG)
    return load_yaml(ACTIVE_CONFIG)


def save_active(config):
    write_yaml(ACTIVE_CONFIG, config)


def set_if_present(target, key, value):
    if value is not None:
        target[key] = value


def calculate_week(participant, session_date):
    if participant.get('test', False):
        return int(participant.get('week_number', 0))
    if participant.get('week_mode', 'auto') != 'auto':
        return int(participant.get('week_number', 0))

    start_date = participant.get('start_date') or session_date.isoformat()
    interval = int(participant.get('week_interval_days', 7))
    if interval <= 0:
        interval = 7
    days = (session_date - parse_date(start_date)).days
    return max(0, days // interval)


def refresh_config(config, session_date, explicit_week=None):
    participant = config.setdefault('participant', {})
    if 'week_interval_days' not in participant:
        participant['week_interval_days'] = 7
    if 'week_mode' not in participant:
        participant['week_mode'] = 'manual' if participant.get('test', False) else 'auto'

    interval = int(participant.get('week_interval_days', 7))
    if interval <= 0:
        interval = 7
    if 'start_date' not in participant or not participant['start_date']:
        existing_week = int(participant.get('week_number', 0))
        participant['start_date'] = (session_date - timedelta(days=existing_week * interval)).isoformat()

    if explicit_week is not None:
        participant['week_number'] = int(explicit_week)
        if participant.get('week_mode') != 'auto':
            participant['week_mode'] = 'manual'
    else:
        participant['week_number'] = calculate_week(participant, session_date)

    participant['last_session_date'] = session_date.isoformat()
    return config


def update_participant_fields(config, args, creating=False):
    participant = config.setdefault('participant', {})
    if creating:
        participant['id'] = str(args.participant_id)
    set_if_present(participant, 'group', args.group.upper() if args.group else None)
    set_if_present(participant, 'age', args.age)
    set_if_present(participant, 'resting_hr', args.resting_hr)
    set_if_present(participant, 'max_hr', args.max_hr)
    set_if_present(participant, 'start_date', args.start_date)

    if args.test:
        participant['test'] = True
        participant['week_mode'] = 'manual'
    if args.real:
        participant['test'] = False
        if participant.get('week_mode') == 'manual' and args.week_number is None:
            participant['week_mode'] = 'auto'
    if args.auto_week:
        participant['week_mode'] = 'auto'
    if args.manual_week:
        participant['week_mode'] = 'manual'

    pepper = config.setdefault('pepper', {})
    set_if_present(pepper, 'ip', args.pepper_ip)
    set_if_present(pepper, 'port', args.pepper_port)


def new_profile(args):
    config = copy.deepcopy(load_active())
    update_participant_fields(config, args, creating=True)
    participant = config.setdefault('participant', {})
    participant.setdefault('test', bool(args.test))
    participant.setdefault('week_interval_days', 7)
    participant['start_date'] = args.start_date or args.date
    if args.test:
        participant['week_mode'] = 'manual'
    else:
        participant.setdefault('week_mode', 'auto')
    refresh_config(config, parse_date(args.date), explicit_week=args.week_number)
    save_profile_and_active(config)
    print_summary(config, 'Created')


def use_profile(args):
    path = participant_path(args.participant_id)
    if not os.path.exists(path):
        raise FileNotFoundError('No saved participant config at {}'.format(path))
    config = load_yaml(path)
    update_participant_fields(config, args)
    refresh_config(config, parse_date(args.date), explicit_week=args.week_number)
    save_profile_and_active(config)
    print_summary(config, 'Activated')


def refresh_active(args):
    config = load_active()
    refresh_config(config, parse_date(args.date), explicit_week=args.week_number)
    save_profile_and_active(config)
    if not args.quiet:
        print_summary(config, 'Refreshed')


def save_profile_and_active(config):
    participant = config.get('participant', {})
    save_active(config)
    write_yaml(participant_path(participant.get('id', 'participant')), config)


def list_profiles(_args):
    os.makedirs(PARTICIPANT_DIR, exist_ok=True)
    for filename in sorted(os.listdir(PARTICIPANT_DIR)):
        if filename.endswith('.yaml'):
            print(os.path.splitext(filename)[0])


def print_summary(config, action):
    participant = config.get('participant', {})
    print('{} participant {}: group {}, week {}, test {}, date {}'.format(
        action,
        participant.get('id'),
        participant.get('group'),
        participant.get('week_number'),
        participant.get('test', False),
        participant.get('last_session_date'),
    ))


def add_common_options(parser):
    parser.add_argument('--date', default=os.environ.get('STUDY_SESSION_DATE', today_iso()),
                        help='Session date in YYYY-MM-DD. Defaults to today or STUDY_SESSION_DATE.')
    parser.add_argument('--start-date', help='First real session date in YYYY-MM-DD.')
    parser.add_argument('--week-number', type=int,
                        help='Week override. This sets week_mode to manual unless --auto-week is also set.')
    parser.add_argument('--auto-week', action='store_true',
                        help='Calculate week_number from start_date and session date.')
    parser.add_argument('--manual-week', action='store_true',
                        help='Keep week_number manual.')
    parser.add_argument('--group', choices=['A', 'B', 'a', 'b'])
    parser.add_argument('--age', type=int)
    parser.add_argument('--resting-hr', type=int)
    parser.add_argument('--max-hr', type=int)
    parser.add_argument('--pepper-ip')
    parser.add_argument('--pepper-port', type=int)
    parser.add_argument('--test', action='store_true', help='Mark as test data and keep week manual.')
    parser.add_argument('--real', action='store_true', help='Mark as real participant data.')


def main():
    parser = argparse.ArgumentParser(description='Create, activate, and refresh study YAML profiles.')
    subparsers = parser.add_subparsers(dest='command', required=True)

    new_parser = subparsers.add_parser('new', help='Create a saved participant YAML and activate it.')
    new_parser.add_argument('participant_id')
    add_common_options(new_parser)
    new_parser.set_defaults(func=new_profile)

    use_parser = subparsers.add_parser('use', help='Activate an existing participant YAML.')
    use_parser.add_argument('participant_id')
    add_common_options(use_parser)
    use_parser.set_defaults(func=use_profile)

    refresh_parser = subparsers.add_parser('refresh', help='Refresh active study_config.yaml week/date.')
    add_common_options(refresh_parser)
    refresh_parser.add_argument('--quiet', action='store_true')
    refresh_parser.set_defaults(func=refresh_active)

    list_parser = subparsers.add_parser('list', help='List saved participant YAML profiles.')
    list_parser.set_defaults(func=list_profiles)

    args = parser.parse_args()
    try:
        args.func(args)
    except Exception as exc:
        print('participant config error: {}'.format(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
