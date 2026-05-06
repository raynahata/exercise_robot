import os


def bundle_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))


def output_root():
    return os.environ.get('EXERCISE_ROBOT_OUTPUT_DIR', os.path.join(bundle_root(), 'study_outputs'))


def output_dir(*parts):
    path = os.path.join(output_root(), *parts)
    os.makedirs(path, exist_ok=True)
    return path


def output_path(*parts):
    return os.path.join(output_dir(*parts[:-1]), parts[-1])
