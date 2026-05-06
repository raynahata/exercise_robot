import asyncio
import os
import re
import string

import openai
import rospy
import yaml
from std_msgs.msg import Bool, String

from AWS_STT import start_transcription
from conv_logger import log_conversation
from portable_paths import output_dir


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_config():
    config_path = os.path.join(BASE_DIR, "config.yaml")
    with open(config_path, "r") as file:
        return yaml.safe_load(file) or {}


def load_openai_key():
    key_path = os.path.join(BASE_DIR, "chatGPT.key")
    with open(key_path, "r") as key_file:
        return key_file.read().strip()


def normalized_command(text):
    return text.lower().replace(" ", "").strip(string.punctuation)


class PepperIntroSession:
    """Runs the pre-exercise conversation until the participant is ready."""

    def __init__(self):
        config = load_config()
        self.participant_number = int(config.get("participant_number", 0))
        self.week_number = int(config.get("week_number", 0))
        self.pepper_state = "listening"
        self.is_pepper_speaking = False
        self.client = openai.OpenAI(api_key=load_openai_key())

        rospy.init_node("robot_intro_session", anonymous=True)
        rospy.Subscriber("/pepper/tts_status", Bool, self.tts_status_callback)
        rospy.Subscriber("pepper_state", String, self.state_callback)

        self.speech_pub = rospy.Publisher("/gpt_speech", String, queue_size=10)
        self.video_pub = rospy.Publisher("/pepper_video_control", String, queue_size=10)
        self.shutdown_pub = rospy.Publisher("/controller_shutdown", Bool, queue_size=10)

        self.csv_history_file = self.initialize_csv()
        self.messages = [{"role": "system", "content": self.load_prompt()}]

    def initialize_csv(self):
        conversation_dir = output_dir("social_buddy", "conversation_files")

        filename = f"participant_{self.participant_number}_week_{self.week_number}.csv"
        csv_path = os.path.join(conversation_dir, filename)
        if not os.path.isfile(csv_path):
            log_conversation("System", "Conversation log initialized", csv_file=csv_path)
        return csv_path

    def load_prompt(self):
        prompt_name = "intro_prompt" if self.week_number == 0 else "intro_prompt_reccuring"
        with open(os.path.join(BASE_DIR, "prompts", prompt_name), "r") as file:
            return file.read()

    def tts_status_callback(self, msg):
        self.is_pepper_speaking = msg.data
        print(f"[ROS FLAG] is_pepper_speaking = {msg.data}")

    def state_callback(self, msg):
        self.pepper_state = msg.data
        rospy.loginfo(f"Received state: {msg.data}")

    def send_to_pepper(self, text):
        print(f"Sending to Pepper: {text}")
        self.is_pepper_speaking = True
        self.speech_pub.publish(text)
        self.pepper_state = "speaking"

    def parse_robot_response(self, response):
        """Expected prompt format: {spoken response, true|false}."""
        if not response:
            return "", False

        match = re.match(r'^\{(.+?),\s*(true|false)\}$', response, re.IGNORECASE)
        if not match:
            return response.strip(), False

        spoken_response, ready_flag = match.groups()
        return spoken_response.strip().strip('"'), ready_flag.strip().lower() == "true"

    async def generate_robot_response(self):
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=self.messages,
                max_tokens=100,
                temperature=0.7,
                n=1,
            )
        except Exception as exc:
            print(f"OpenAI Error: {exc}")
            return None

        text = response.choices[0].message.content.strip()
        log_conversation("Robot", text, csv_file=self.csv_history_file)
        print("Robot:", text)
        return text

    async def handle_user_turn(self):
        print("Waiting for user response...")
        user_message = await asyncio.wait_for(start_transcription(), timeout=40)
        log_conversation("User", user_message, self.csv_history_file)
        print("You:", user_message)

        if normalized_command(user_message) == "bye":
            print("Ending conversation.")
            self.shutdown_pub.publish(Bool(data=True))
            return True

        self.messages.append({"role": "user", "content": user_message})
        robot_response = await self.generate_robot_response()
        spoken_response, ready_to_start = self.parse_robot_response(robot_response)

        if spoken_response:
            self.send_to_pepper(spoken_response)
            self.messages.append({"role": "assistant", "content": spoken_response})

        if ready_to_start:
            print("User is ready to start exercise session.")
            self.shutdown_pub.publish(Bool(data=True))
            return True

        return False

    async def run_intro_session(self):
        print("Generating initial response...")
        initial_response = await self.generate_robot_response()
        spoken_response, ready_to_start = self.parse_robot_response(initial_response)

        self.send_to_pepper(spoken_response)
        log_conversation("Robot", spoken_response, self.csv_history_file)
        self.messages.append({"role": "assistant", "content": spoken_response})

        if ready_to_start:
            self.shutdown_pub.publish(Bool(data=True))
            return

        try:
            while not rospy.is_shutdown():
                if self.pepper_state == "listening" and not self.is_pepper_speaking:
                    done = await self.handle_user_turn()
                    if done:
                        return
                await asyncio.sleep(0.1)
        except asyncio.TimeoutError:
            print("Intro section timeout: no user response detected.")

    async def run(self):
        self.video_pub.publish(
            f"start recording;participant_{self.participant_number};week_{self.week_number};intro"
        )
        await self.run_intro_session()
        self.video_pub.publish("stop_video")


if __name__ == "__main__":
    session = PepperIntroSession()
    asyncio.run(session.run())
