import asyncio
import os
import string
import sys
import time
from datetime import datetime, timedelta, timezone

import openai
import rospy
import yaml
from std_msgs.msg import Bool, String

from AWS_STT import start_transcription
from conv_logger import log_conversation
from portable_paths import output_dir
from summary_generator import generate_summary_for_session


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_TIMEZONE = timezone(timedelta(hours=-5))
EXERCISE_LIST = ["bicep curls", "bicep curls", "lateral raises", "lateral raises"]
SET_SECONDS = 40
REST_SECONDS = 40
USER_RESPONSE_TIMEOUT_SECONDS = 50


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


class PepperExerciseSession:
    """Runs the exercise session and optional post-session summary."""

    def __init__(self):
        config = load_config()
        self.participant_number = int(config.get("participant_number", 0))
        self.week_number = int(config.get("week_number", 0))
        self.generate_summary_after_session = bool(config.get("generate_summary_after_session", False))
        self.summary_prompt_file = config.get("summary_prompt_file", "summaryPrompt.txt")
        self.summary_model = config.get("summary_model", "gpt-4o")
        self.summary_max_tokens = int(config.get("summary_max_tokens", 250))
        self.pepper_state = "listening"
        self.is_pepper_speaking = False
        self.client = openai.OpenAI(api_key=load_openai_key())

        rospy.init_node("robot_speech_publisher", anonymous=True)
        rospy.Subscriber("/pepper/tts_status", Bool, self.tts_status_callback)
        rospy.Subscriber("pepper_state", String, self.state_callback)

        self.speech_pub = rospy.Publisher("/gpt_speech", String, queue_size=10)
        self.display_pub = rospy.Publisher("/speech_display", String, queue_size=10)
        self.exercise_pub = rospy.Publisher("/exercise_command", String, queue_size=10)
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
        if self.week_number == 0:
            prompt_name = "conversational_prompt_0.txt"
        else:
            prompt_name = f"conversational_prompt_{self.participant_number}_week_{self.week_number}.txt"

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

    def send_display_only(self, text):
        print(f"Displaying on Pepper: {text}")
        self.display_pub.publish(text)

    def send_exercise_command(self, command):
        print(f"Sending exercise command: {command}")
        self.exercise_pub.publish(String(data=command))
        rospy.sleep(1)

    async def wait_until_done_speaking(self):
        rate = rospy.Rate(10)
        while self.is_pepper_speaking:
            rate.sleep()

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
        print("Robot:", text)
        log_conversation("Robot", text, csv_file=self.csv_history_file)
        return text

    async def listen_for_wake_word(self, wake_word, timeout_seconds=20):
        print("Listening for wake word...")
        last_detection_time = time.time()

        while True:
            transcription_task = asyncio.create_task(start_transcription())
            while not transcription_task.done():
                await asyncio.sleep(1)
                if time.time() - last_detection_time > timeout_seconds:
                    print("No speech detected. Shutting down.")
                    sys.exit(0)

            transcribed_text = transcription_task.result()
            if not transcribed_text:
                continue

            print("Transcript:", transcribed_text)
            last_detection_time = time.time()
            if wake_word in transcribed_text.lower():
                print("Wake word detected!")
                return

    async def listen_for_user_turn(self):
        await self.wait_until_done_speaking()
        print("Waiting for user response...")
        user_input = await asyncio.wait_for(
            start_transcription(), timeout=USER_RESPONSE_TIMEOUT_SECONDS
        )
        print("You:", user_input)
        log_conversation("User", user_input, csv_file=self.csv_history_file)

        if normalized_command(user_input) == "bye":
            await self.end_session_early()
            return "ended"

        self.messages.append({"role": "user", "content": user_input})
        return "user"

    async def maybe_generate_robot_turn(self):
        robot_response = await self.generate_robot_response()
        if not robot_response:
            return "robot"

        self.send_to_pepper(robot_response)
        self.messages.append({"role": "assistant", "content": robot_response})
        return "robot"

    async def run_conversation_window(self, duration_seconds, last_speaker):
        start_time = datetime.now(SESSION_TIMEZONE)
        while (datetime.now(SESSION_TIMEZONE) - start_time).total_seconds() < duration_seconds:
            if last_speaker == "robot":
                try:
                    last_speaker = await self.listen_for_user_turn()
                except asyncio.TimeoutError:
                    print("Timeout: no user response detected.")
                    last_speaker = "robot"
            else:
                last_speaker = await self.maybe_generate_robot_turn()

            if last_speaker == "ended":
                return "ended"

        return last_speaker

    async def end_session_early(self):
        print("Ending session.")
        self.send_to_pepper("Thank you for exercising with me.")
        self.send_exercise_command("rest")
        self.shutdown_pub.publish(Bool(data=True))

    def log_robot_system_message(self, message):
        log_conversation("Robot", message, csv_file=self.csv_history_file)
        self.messages.append({"role": "system", "content": message})

    async def run_exercise_set(self, exercise_name, set_number, last_speaker):
        if set_number == 0:
            message = (
                f"I'm super excited to exercise with you. Let's do some {exercise_name}. "
                "Do you have anything fun planned for the day?"
            )
            self.send_to_pepper(message)
        else:
            message = f"Let's do some {exercise_name}."
            self.send_display_only(message)

        self.messages.append({"role": "system", "content": message})
        self.send_exercise_command(exercise_name)

        last_speaker = await self.run_conversation_window(SET_SECONDS, last_speaker)
        if last_speaker == "ended":
            return last_speaker

        self.send_display_only("Done with the set.")
        self.send_exercise_command("rest")
        print("Done with the set.")
        self.log_robot_system_message("Done with the set.")
        return last_speaker

    async def run_rest_period(self, last_speaker):
        self.send_display_only("Let's take a rest for 40 seconds.")
        self.send_exercise_command("rest")
        rospy.sleep(1)
        print("Let's take a rest for 40 seconds.")
        log_conversation("Robot", "Take a rest for 40 seconds.", self.csv_history_file)
        return await self.run_conversation_window(REST_SECONDS, last_speaker)

    async def exercise_session(self, exercise_list):
        last_speaker = "robot"
        for index, exercise_name in enumerate(exercise_list):
            last_speaker = await self.run_exercise_set(exercise_name, index, last_speaker)
            if last_speaker == "ended":
                return

            if index < len(exercise_list) - 1:
                last_speaker = await self.run_rest_period(last_speaker)
                if last_speaker == "ended":
                    return

        final_message = "Great job completing this round! Please fill out the survey!"
        self.send_to_pepper(final_message)
        self.send_exercise_command("rest")
        print("Great job completing this round!")
        log_conversation("Robot", final_message, self.csv_history_file)
        await self.wait_until_done_speaking()
        self.shutdown_pub.publish(Bool(data=True))

    def maybe_generate_session_summary(self):
        if not self.generate_summary_after_session:
            print("Automatic summary generation is disabled.")
            return

        print("Generating automatic session summary...")
        summary_path = generate_summary_for_session(
            self.participant_number,
            self.week_number,
            csv_filepath=self.csv_history_file,
            prompt_filename=self.summary_prompt_file,
            model=self.summary_model,
            max_tokens=self.summary_max_tokens,
        )

        if summary_path:
            print(f"Automatic summary saved to {summary_path}")
        else:
            print("Automatic summary generation did not produce a file.")

    async def run(self):
        self.video_pub.publish(
            f"start recording;participant_{self.participant_number};week_{self.week_number};exercise"
        )
        self.send_display_only("When you are ready to exercise, please say 'ready'.")
        await self.listen_for_wake_word("ready")

        print("Starting the exercise session...")
        await self.exercise_session(EXERCISE_LIST)
        self.video_pub.publish("stop_video")
        self.maybe_generate_session_summary()


if __name__ == "__main__":
    session = PepperExerciseSession()
    asyncio.run(session.run())
