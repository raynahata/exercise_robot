# Run this file with Python 2.7 because NAOqi uses Python 2.

import atexit
import math
import os
import subprocess
import sys
import threading
import time
from datetime import datetime

import rospy
import yaml
from naoqi import ALProxy
from sensor_msgs.msg import Image
from std_msgs.msg import Bool, String

from portable_paths import output_dir

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


EXERCISE_COMMANDS = {
    "bicep curls": "bicep_curls",
    "lateral raises": "lateral_raises",
}


def load_config():
    config_path = os.path.join(BASE_DIR, "config.yaml")
    with open(config_path, "r") as config_file:
        return yaml.safe_load(config_file) or {}


def degrees_to_radians(angles_in_degrees):
    return [angle * math.pi / 180.0 for angle in angles_in_degrees]


class PepperController(object):
    """ROS bridge between the Python 3 session code and Pepper's NAOqi APIs."""

    def __init__(self):
        config = load_config()
        self.ip = config.get("pepper_ip", "127.0.0.1")
        self.port = int(config.get("pepper_port", 9559))
        self.participant_number = str(config.get("participant_number", 0))
        self.week_number = str(config.get("week_number", 0))
        self.timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        self.state = ""
        self.current_text = ""
        self.current_exercise = None
        self.exercise_running = False
        self.is_resting = False
        self.recording_audio = False
        self.audio_process = None
        self.rosbag_process = None

        self.recordings_dir = output_dir("social_buddy", "recordings")

        self.connect_pepper_services()
        self.setup_ros()
        self.setup_camera()
        self.start_recordings()

    def connect_pepper_services(self):
        self.tts = ALProxy("ALTextToSpeech", self.ip, self.port)
        self.motion = ALProxy("ALMotion", self.ip, self.port)
        self.posture = ALProxy("ALRobotPosture", self.ip, self.port)
        self.life = ALProxy("ALAutonomousLife", self.ip, self.port)
        self.tablet = ALProxy("ALTabletService", self.ip, self.port)
        self.memory = ALProxy("ALMemory", self.ip, self.port)
        self.leds = ALProxy("ALLeds", self.ip, self.port)

        self.life.setAutonomousAbilityEnabled("All", True)
        self.tts.setParameter("defaultVoiceSpeed", 70)
        self.tts.setParameter("pitchShift", 1)

    def setup_ros(self):
        rospy.init_node("pepper_controller", anonymous=True)

        self.state_pub = rospy.Publisher("pepper_state", String, queue_size=10)
        self.text_pub = rospy.Publisher("chat_text", String, queue_size=10)
        self.exercise_pub = rospy.Publisher("/exercise_command", String, queue_size=10)
        self.tts_status_pub = rospy.Publisher("/pepper/tts_status", Bool, queue_size=1)
        self.image_pub = rospy.Publisher("/pepper_camera/image_raw", Image, queue_size=10)

        rospy.Subscriber("pepper_state", String, self.state_callback)
        rospy.Subscriber("gpt_speech", String, self.gpt_speech_callback)
        rospy.Subscriber("speech_display", String, self.display_callback)
        rospy.Subscriber("exercise_command", String, self.exercise_callback)
        rospy.Subscriber("controller_shutdown", Bool, self.shutdown_callback)

        rospy.loginfo("Pepper controller subscribed to session topics.")

    def setup_camera(self):
        resolution = 2  # 640x480
        color_space = 11  # RGB
        fps = 5
        self.video_service = ALProxy("ALVideoDevice", self.ip, self.port)
        self.camera_subscriber_id = self.video_service.subscribeCamera(
            "video_stream", 0, resolution, color_space, fps
        )

    def start_recordings(self):
        self.start_system_audio_recording()
        self.start_rosbag_video_recording()
        atexit.register(self.stop_system_audio_recording)
        atexit.register(self.stop_rosbag_video_recording)

    def shutdown_callback(self, msg):
        if msg.data:
            rospy.loginfo("Shutting down controller node.")
            self.stop_system_audio_recording()
            self.stop_rosbag_video_recording()
            rospy.signal_shutdown("Shutdown requested by social session")
            sys.exit(0)

    def state_callback(self, msg):
        self.state = msg.data
        rospy.loginfo("Received state: {}".format(msg.data))

    def gpt_speech_callback(self, msg):
        rospy.loginfo("Received GPT speech: {}".format(msg.data))
        self.current_text = msg.data
        self.set_state("speaking")
        self.display_text(self.current_text)

        self.tts_status_pub.publish(True)
        self.tts.say(self.current_text)
        while self.memory.getData("ALTextToSpeech/Status")[1] != "done":
            time.sleep(0.1)

        self.tts_status_pub.publish(False)
        self.set_state("listening")

    def display_callback(self, msg):
        rospy.loginfo("Received display text: {}".format(msg.data))
        self.current_text = msg.data
        self.display_text(self.current_text)

    def set_state(self, state):
        self.state = state
        self.state_pub.publish(state)

    def clear_screen(self):
        rospy.loginfo("Clearing Pepper tablet.")
        js_script = "document.body.innerHTML = `<style>body{background:#f0f0f0;margin:0;}</style>`;"
        self.tablet.executeJS(js_script)

    def display_text(self, message):
        rospy.loginfo("Displaying text on tablet: {}".format(message))
        js_script = (
            "document.body.innerHTML = `<style>"
            "body{font-family:Arial,sans-serif;text-align:center;background:#f0f0f0;"
            "display:flex;justify-content:center;align-items:center;height:100vh;"
            "width:100vw;margin:0;padding:20px;overflow:hidden;}"
            ".text{font-size:10vh;color:#333;width:90vw;height:100vh;"
            "word-wrap:break-word;overflow-wrap:break-word;display:flex;"
            "align-items:center;justify-content:center;text-align:center;"
            "white-space:normal;line-height:1.5;}</style><div class='text'>"
            + message +
            "</div>`;"
        )
        self.tablet.executeJS(js_script)

    def set_eye_color(self, rgb):
        red, green, blue = rgb
        hex_color = (red << 16) | (green << 8) | blue
        self.leds.fadeRGB("FaceLeds", hex_color, 1.0)

    def exercise_callback(self, msg):
        command = msg.data.lower()
        rospy.loginfo("Received exercise command: {}".format(command))

        if command == "rest":
            self.enter_rest_state()
            return

        method_name = EXERCISE_COMMANDS.get(command)
        if not method_name:
            rospy.logwarn("Unknown exercise command: {}".format(command))
            return

        if self.exercise_running:
            rospy.loginfo("{} is already running.".format(command))
            return

        self.exercise_running = True
        self.is_resting = False
        self.current_exercise = command
        self.set_eye_color((255, 255, 255))

        target = getattr(self, method_name)
        threading.Thread(target=target).start()

    def enter_rest_state(self):
        if not self.exercise_running:
            rospy.loginfo("Already in rest phase.")
            return

        rospy.loginfo("Stopping exercise and entering rest phase.")
        self.exercise_running = False
        self.current_exercise = None
        self.is_resting = True
        self.set_eye_color((0, 0, 255))
        self.stop_exercise_motion()

    def stop_exercise_motion(self):
        self.motion.stopMove()
        self.motion.setStiffnesses("Body", 0.0)

    def move_arm(self, side, angles, speed=0.2):
        if side == "R":
            joint_names = ["RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll", "RWristYaw"]
        elif side == "L":
            joint_names = ["LShoulderPitch", "LShoulderRoll", "LElbowYaw", "LElbowRoll", "LWristYaw"]
        else:
            rospy.logerr("Invalid arm side '{}'. Use 'R' or 'L'.".format(side))
            return

        if len(angles) != len(joint_names):
            rospy.logerr("Number of angles does not match number of joints.")
            return

        self.motion.setAngles(joint_names, angles, speed)

    def move_both_arms(self, right_degrees, left_degrees, speed):
        self.move_arm("R", degrees_to_radians(right_degrees), speed=speed)
        self.move_arm("L", degrees_to_radians(left_degrees), speed=speed)

    def lateral_arm_motion_up(self):
        self.move_both_arms(
            right_degrees=[101.2, -89.4, 97.3, 5.8, -1.0],
            left_degrees=[101.2, 89.4, -97.3, -5.8, 1.0],
            speed=0.2,
        )

    def lateral_arm_motion_down(self):
        self.move_both_arms(
            right_degrees=[101.2, -0.5, 97.3, 5.8, -1.0],
            left_degrees=[101.2, 2.3, -98, -6, 1.9],
            speed=0.2,
        )

    def bicep_arm_motion_up(self):
        self.move_both_arms(
            right_degrees=[76.0, -23.0, 83.0, 89.0, 104.5],
            left_degrees=[76.0, 23.0, -83.0, -89.0, -104.5],
            speed=0.1,
        )

    def bicep_arm_motion_down(self):
        self.move_both_arms(
            right_degrees=[76.0, -23.0, 83.0, 0.7, 104.5],
            left_degrees=[76.0, 23.0, -83.0, -0.7, -104.5],
            speed=0.1,
        )

    def run_repeating_motion(self, exercise_name, move_up, move_down):
        rospy.loginfo("Pepper is performing {}.".format(exercise_name))
        try:
            while self.exercise_running and not rospy.is_shutdown():
                move_up()
                rospy.sleep(2)
                move_down()
                rospy.sleep(2)

            rospy.loginfo("{} stopped. Entering rest phase.".format(exercise_name))
            self.exercise_running = False
            self.current_exercise = None
            self.is_resting = True
            self.exercise_pub.publish("rest")
        except rospy.ROSInterruptException:
            rospy.loginfo("{} interrupted.".format(exercise_name))

    def bicep_curls(self):
        self.run_repeating_motion(
            "bicep curls", self.bicep_arm_motion_up, self.bicep_arm_motion_down
        )

    def lateral_raises(self):
        self.run_repeating_motion(
            "lateral raises", self.lateral_arm_motion_up, self.lateral_arm_motion_down
        )

    def publish_camera_frame(self):
        image = self.video_service.getImageRemote(self.camera_subscriber_id)
        if not image:
            return

        width = image[0]
        height = image[1]

        ros_image = Image()
        ros_image.header.stamp = rospy.Time.now()
        ros_image.width = width
        ros_image.height = height
        ros_image.encoding = "rgb8"
        ros_image.step = width * 3
        ros_image.data = image[6]
        self.image_pub.publish(ros_image)

    def start_rosbag_video_recording(self):
        filename = "video_only_p{}_week{}_{}.bag".format(
            self.participant_number, self.week_number, self.timestamp
        )
        save_path = os.path.join(self.recordings_dir, filename)
        rospy.loginfo("Starting rosbag video recording: {}".format(save_path))
        self.rosbag_process = subprocess.Popen(
            ["rosbag", "record", "-O", save_path, "/pepper_camera/image_raw"]
        )

    def stop_rosbag_video_recording(self):
        if self.rosbag_process:
            rospy.loginfo("Stopping rosbag video recording.")
            self.rosbag_process.terminate()
            self.rosbag_process.wait()
            self.rosbag_process = None

    def start_system_audio_recording(self):
        filename = "local_audio_p{}_week{}_{}.wav".format(
            self.participant_number, self.week_number, self.timestamp
        )
        self.audio_file = os.path.join(self.recordings_dir, filename)
        command = ["arecord", "-f", "cd", "-t", "wav", self.audio_file]

        try:
            rospy.loginfo("Starting system audio recording: {}".format(self.audio_file))
            self.audio_process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            self.recording_audio = True
            return True
        except Exception as exc:
            rospy.logerr("Failed to start system audio recording: {}".format(exc))
            return False

    def stop_system_audio_recording(self):
        if self.audio_process and self.recording_audio:
            rospy.loginfo("Stopping system audio recording.")
            self.audio_process.terminate()
            self.audio_process.wait()
            self.audio_process = None
            self.recording_audio = False

    def run(self):
        rate = rospy.Rate(5)
        while not rospy.is_shutdown():
            self.publish_camera_frame()
            rate.sleep()


if __name__ == "__main__":
    controller = PepperController()
    controller.run()
