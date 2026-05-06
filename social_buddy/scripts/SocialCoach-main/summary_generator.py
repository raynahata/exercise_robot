import os

import openai
import pandas as pd
import yaml

from portable_paths import output_dir

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_config():
    config_path = os.path.join(BASE_DIR, "config.yaml")
    with open(config_path, "r") as file:
        return yaml.safe_load(file) or {}


def get_openai_key():
    key_path = os.path.join(BASE_DIR, "chatGPT.key")
    if not os.path.exists(key_path):
        raise FileNotFoundError(f"API key file not found at {key_path}")

    with open(key_path, "r") as key_file:
        return key_file.read().strip()


def load_conversation(participant, week, csv_filepath=None):
    if csv_filepath is None:
        csv_filename = f"participant_{participant}_week_{week}.csv"
        csv_filepath = os.path.join(output_dir("social_buddy", "conversation_files"), csv_filename)

    try:
        dataframe = pd.read_csv(
            csv_filepath,
            encoding="utf-8",
            names=["timestamp", "speaker", "message"],
            skiprows=1,
        )
    except FileNotFoundError:
        print(f"Error: conversation CSV not found at {csv_filepath}.")
        return None
    except Exception as exc:
        print(f"Error reading conversation CSV: {exc}")
        return None

    dataframe = dataframe[["speaker", "message"]].dropna()
    conversation_text = "\n".join(
        f"{row['speaker']}: {row['message']}" for _, row in dataframe.iterrows()
    )

    if not conversation_text.strip():
        print(f"Error: conversation file for participant {participant} is empty.")
        return None

    return conversation_text


def load_prompt(prompt_filename):
    prompt_path = os.path.join(BASE_DIR, "prompts", prompt_filename)
    try:
        with open(prompt_path, "r", encoding="utf-8") as file:
            prompt = file.read().strip()
    except FileNotFoundError:
        print(f"Error: prompt file not found at {prompt_path}.")
        return None

    if not prompt:
        print(f"Error: prompt file is empty at {prompt_path}.")
        return None
    return prompt


def build_summary_prompt(prompt_template, conversation_text):
    return f"{prompt_template}\n\nConversation:\n{conversation_text}"


def generate_summary(final_prompt, model="gpt-4o", max_tokens=250):
    client = openai.OpenAI(api_key=get_openai_key())
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You summarize exercise-session conversations into concise paragraphs.",
                },
                {"role": "user", "content": final_prompt},
            ],
            max_tokens=max_tokens,
        )
    except Exception as exc:
        print(f"Error generating summary: {exc}")
        return None

    if not response or not response.choices:
        print(f"Error: {model} did not return a summary.")
        return None

    return response.choices[0].message.content.strip()


def save_summary(participant, week, summary):
    summaries_dir = output_dir("social_buddy", "summaries")

    summary_path = os.path.join(summaries_dir, f"summary_p{participant}_week{week}.txt")
    try:
        with open(summary_path, "w", encoding="utf-8") as file:
            file.write(summary)
    except Exception as exc:
        print(f"Error saving summary: {exc}")
        return None

    print(f"Summary saved to {summary_path}")
    return summary_path


def generate_summary_for_session(
    participant,
    week,
    csv_filepath=None,
    prompt_filename="summaryPrompt.txt",
    model="gpt-4o",
    max_tokens=250,
):
    conversation_text = load_conversation(participant, week, csv_filepath=csv_filepath)
    prompt_template = load_prompt(prompt_filename)
    if not conversation_text or not prompt_template:
        return None

    final_prompt = build_summary_prompt(prompt_template, conversation_text)
    summary = generate_summary(final_prompt, model=model, max_tokens=max_tokens)
    if not summary:
        return None

    return save_summary(participant, week, summary)


def main():
    config = load_config()
    generate_summary_for_session(
        participant=int(config.get("participant_number", 0)),
        week=int(config.get("week_number", 0)),
        prompt_filename=config.get("summary_prompt_file", "summaryPrompt.txt"),
        model=config.get("summary_model", "gpt-4o"),
        max_tokens=int(config.get("summary_max_tokens", 250)),
    )


if __name__ == "__main__":
    main()
