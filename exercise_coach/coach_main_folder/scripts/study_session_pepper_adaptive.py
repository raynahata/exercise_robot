#!/usr/bin/env python3

#general imports
import copy
import os
import signal
import time
import pickle
import logging
import subprocess
import numpy as np
from pytz import timezone
from pynput import keyboard ##fix this import
from datetime import datetime
import matplotlib.pyplot as plt
import yaml

#ros imports
import rospy
from rospkg import RosPack
from std_msgs.msg import Int32, String

#package imports
from exercise_manager import ExerciseManager
from portable_paths import output_dir as portable_output_dir, output_path

rp = RosPack()

DEFAULT_CONFIG = {
    'participant': {
        'id': '0',
        'age': 26,
        'resting_hr': 97,
        'week_number': 1,
    },
    'session': {
        'round_num': 1,
        'robot_style': 5,
        'set_length': 40,
        'rest_time': 40,
        'exercise_list': ['bicep_curls', 'bicep_curls', 'lateral_raises', 'lateral_raises'],
        'verbal_cadence': 2,
        'nonverbal_cadence': 2,
    },
    'rosbag': {
        'enabled': True,
        'record_all': True,
        'topics': [],
        'output_dir': 'bags',
        'restart_on_exit': True,
        'restart_delay_sec': 5,
    },
}


def deep_update(base, override):
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_update(base[key], value)
        else:
            base[key] = value
    return base


def load_study_config():
    config = copy.deepcopy(DEFAULT_CONFIG)
    config_path = os.path.join(rp.get_path('pepper_exercise_coach'), 'config', 'study_session_config.yaml')
    if os.path.exists(config_path):
        with open(config_path, 'r') as file:
            loaded_config = yaml.safe_load(file) or {}
        config = deep_update(config, loaded_config)
    return config

class StudySession:
    def __init__(self):
        self.config = load_study_config()
        self.participant_config = self.config['participant']
        self.session_config = self.config['session']
        self.rosbag_config = self.config['rosbag']
        self.participant_id = str(self.participant_config['id'])
        self.age = int(self.participant_config['age'])
        self.resting_hr = int(self.participant_config['resting_hr'])
        self.week_number = int(self.participant_config.get('week_number', 1))
        self.round_num = int(self.session_config['round_num'])
        self.robot_style = int(self.session_config['robot_style'])
        self.set_length = int(self.session_config['set_length'])
        self.rest_time = int(self.session_config['rest_time'])
        self.exercise_list = list(self.session_config['exercise_list'])
        self.max_hr = int(self.participant_config.get('max_hr', 220 - self.age))
        #init data storage
        self.intake_heart_rates = []
        self.rosbag_process = None
        self.last_rosbag_restart = 0
        self.rosbag_start_count = 0
        self.timestamp = datetime.now().strftime("%Y-%m-%d--%H-%M-%S")
        #init filenames
        self.log_filename = 'Participant_{}_Week_{}_Style_{}_Round_{}_{}.log'.format(self.participant_id, self.week_number, self.robot_style, self.round_num, self.timestamp)
        self.data_filename = 'Participant_{}_Week_{}_Style_{}_Round_{}_{}.pickle'.format(self.participant_id, self.week_number, self.robot_style, self.round_num, self.timestamp)
        portable_output_dir('exercise_coach', 'logs')
        portable_output_dir('exercise_coach', 'data')

    def intake_heart_rate_callback(self, msg):
        self.intake_heart_rates.append(msg.data)

    def build_rosbag_command(self):
        rosbag_config = self.rosbag_config
        if not rosbag_config.get('enabled', False):
            return None

        output_dir = rosbag_config.get('output_dir', 'bags')
        if not os.path.isabs(output_dir):
            output_dir = portable_output_dir('exercise_coach', output_dir)
        os.makedirs(output_dir, exist_ok=True)

        bag_filename = 'Participant_{}_Week_{}_Style_{}_Round_{}_{}'.format(
            self.participant_id,
            self.week_number,
            self.robot_style,
            self.round_num,
            self.timestamp,
        )
        if self.rosbag_start_count > 0:
            bag_filename = '{}_restart_{}'.format(bag_filename, self.rosbag_start_count)
        output_path = os.path.join(output_dir, bag_filename)
        command = ['rosbag', 'record', '-O', output_path]

        if rosbag_config.get('record_all', True):
            command.append('-a')
        else:
            topics = rosbag_config.get('topics', [])
            if not topics:
                rospy.logwarn('Rosbag recording is enabled but no topics are configured.')
                return None
            command.extend(topics)

        return command

    def start_rosbag(self, logger=None):
        command = self.build_rosbag_command()
        if command is None:
            return

        try:
            self.rosbag_process = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid,
                text=True,
            )
            self.last_rosbag_restart = time.time()
            self.rosbag_start_count += 1
            message = 'Started rosbag recording with command: {}'.format(' '.join(command))
            if logger:
                logger.info(message)
            else:
                rospy.loginfo(message)
        except OSError as exc:
            self.rosbag_process = None
            message = 'Failed to start rosbag recording: {}'.format(exc)
            if logger:
                logger.warning(message)
            else:
                rospy.logwarn(message)

    def check_rosbag(self, logger):
        if not self.rosbag_config.get('enabled', False):
            return
        if self.rosbag_process is None:
            restart_delay = float(self.rosbag_config.get('restart_delay_sec', 5))
            if (
                self.rosbag_config.get('restart_on_exit', True)
                and self.last_rosbag_restart > 0
                and time.time() - self.last_rosbag_restart >= restart_delay
            ):
                logger.warning('Restarting rosbag recording.')
                self.start_rosbag(logger)
            return
        return_code = self.rosbag_process.poll()
        if return_code is None:
            return

        logger.warning('Rosbag process exited with code {}'.format(return_code))
        self.rosbag_process = None

    def stop_rosbag(self, logger=None):
        if self.rosbag_process is None:
            return
        if self.rosbag_process.poll() is not None:
            self.rosbag_process = None
            return
        try:
            os.killpg(os.getpgid(self.rosbag_process.pid), signal.SIGINT)
            self.rosbag_process.wait(timeout=10)
        except Exception as exc:
            if logger:
                logger.warning('Failed to stop rosbag gracefully: {}'.format(exc))
            self.rosbag_process.terminate()
        finally:
            self.rosbag_process = None

    def main(self):
        rospy.init_node('pepper_study_session', anonymous=True)
        rate = rospy.Rate(10)

        #publisher
        pepper_action_pub = rospy.Publisher("/pepper_action_request", String, queue_size=10)

        #subscribers
        heart_rate_sub = rospy.Subscriber("/heart_rate", Int32, self.intake_heart_rate_callback, queue_size=3000)

        #init controller
        controller = ExerciseManager(False, self.log_filename, self.robot_style, self.resting_hr, self.max_hr, self.participant_id)
        controller.verbal_cadence = int(self.session_config.get('verbal_cadence', controller.verbal_cadence))
        controller.nonverbal_cadence = int(self.session_config.get('nonverbal_cadence', controller.nonverbal_cadence))
        controller.set_data_dict['session_metadata'] = {
            'participant_id': self.participant_id,
            'age': self.age,
            'resting_hr': self.resting_hr,
            'max_hr': self.max_hr,
            'week_number': self.week_number,
            'round_num': self.round_num,
            'robot_style': self.robot_style,
            'set_length': self.set_length,
            'rest_time': self.rest_time,
            'exercise_list': self.exercise_list,
            'verbal_cadence': controller.verbal_cadence,
            'nonverbal_cadence': controller.nonverbal_cadence,
        }
        self.start_rosbag(controller.logger)
        rospy.on_shutdown(lambda: self.stop_rosbag(controller.logger))
        rospy.sleep(5)
        self.check_rosbag(controller.logger)

        #Note from refactor: no round 0. All rounds should be > 0
        input("Press Enter to to start exercise session...")
        self.check_rosbag(controller.logger)
        controller.message('Let us start Round {} now. Please pick up the dumbbells if you want to use them'.format(self.round_num))
        input("Press Enter to to start exercise session...")
        self.check_rosbag(controller.logger)

        #For each exercise
        for set_num, exercise_name in enumerate(self.exercise_list):
                    
            #Start a new set
            controller.start_new_set(exercise_name, set_num+1, len(self.exercise_list))
            
            controller.logger.info('-------------------Recording!')
            start_message = False
            halfway_message = False

            #publish neutral action to pepper
            pepper_action = 'positive_neutral'
            pepper_action_pub.publish(pepper_action)
            
            inittime = datetime.now(timezone('EST'))
            
            #Stop between minimum and maximum time and minimum reps
            while (datetime.now(timezone('EST')) - inittime).total_seconds() < self.set_length and not rospy.is_shutdown():
                self.check_rosbag(controller.logger)
                        
                #Robot says starting set
                if not start_message:
                    robot_message = "Start %s now" % (exercise_name.replace("_", " " ))
                    controller.message(robot_message)
                    start_message = True

                controller.flag = True

                if (datetime.now(timezone('EST')) - inittime).total_seconds() > self.set_length/2 and not halfway_message:
                    robot_message = "You are halfway"
                    controller.message(robot_message)
                    halfway_message = True 

                if (datetime.now(timezone('EST')) - inittime).total_seconds() > self.set_length:
                    break 
                rate.sleep()

            controller.flag = False
            controller.logger.info('-------------------Done with exercise')

            robot_message = "Almost done."
            controller.message(robot_message)
            rospy.sleep(3)

            rest_start = datetime.now(timezone('EST'))

            robot_message = "Time to rest."
            controller.message(robot_message)

            #publish neutral action to pepper
            pepper_action = 'positive_neutral'
            pepper_action_pub.publish(pepper_action)
            
            if set_num + 1 < len(self.exercise_list):
                halfway_message = False
                while (datetime.now(timezone('EST')) - rest_start).total_seconds() < self.rest_time and not rospy.is_shutdown():
                    self.check_rosbag(controller.logger)
                    
                    #Print halfway done with rest here
                    if (datetime.now(timezone('EST')) - rest_start).total_seconds() > self.rest_time/2 and not halfway_message:
                        halfway_message = True
                        robot_message = "Rest for {} more seconds.".format(int(self.rest_time/2))
                        controller.message(robot_message)
                    rate.sleep()
            else:
                robot_message = "Round complete. Please take a seat in the chair and complete a survey about this round on the laptop next to you."
                controller.message(robot_message)

        if controller.adaptive:
            try:
                controller.process.stdin.write('exit\n')
                controller.process.stdin.flush()
            except (BrokenPipeError, AttributeError):
                controller.logger.warning('Adaptive controller was already stopped.')

            if controller.process.stdin:
                controller.process.stdin.close()
            if controller.process.stdout:
                controller.process.stdout.close()

        #dump dictionary into pickle
        with open(output_path('exercise_coach', 'data', self.data_filename), 'wb') as f:
            pickle.dump(controller.set_data_dict, f)

        controller.logger.info('Saved file {}'.format(self.data_filename))
        self.stop_rosbag(controller.logger)
        controller.logger.handlers.clear()
        logging.shutdown()
        print('Done!')

if __name__ == '__main__':
    session = StudySession()
    session.main()
    

##TODO: record video from user
