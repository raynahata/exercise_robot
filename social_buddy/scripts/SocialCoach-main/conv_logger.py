import csv
import logging
import os
from datetime import datetime

from portable_paths import output_dir

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEXT_LOG_PATH = os.path.join(output_dir("social_buddy", "conversation_files"), "conversation_log.txt")
CSV_HEADER = ["timestamp", "speaker", "message"]


logging.basicConfig(
    filename=TEXT_LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def log_conversation(speaker, message, csv_file="conversation_history.csv"):
    """Append one conversation turn to the text log and the session CSV."""
    logging.info("%s: %s", speaker, message)

    file_exists = os.path.isfile(csv_file)
    with open(csv_file, mode="a", newline="") as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(CSV_HEADER)
        writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), speaker, message])


def load_conversation_history(csv_file="conversation_history.csv"):
    """Load a conversation CSV into OpenAI-style message dictionaries."""
    messages = []
    try:
        with open(csv_file, newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                speaker = row.get("speaker") or row.get("role")
                message = row.get("message") or row.get("content")
                if speaker and message:
                    messages.append({"role": speaker, "content": message})
                else:
                    print("Warning: Row missing speaker/message fields.")
    except FileNotFoundError:
        print(f"Warning: CSV file '{csv_file}' not found. Starting with an empty history.")
    return messages
