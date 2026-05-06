import asyncio
import time

import sounddevice as sd
from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.handlers import TranscriptResultStreamHandler
from amazon_transcribe.model import TranscriptEvent


REGION = "us-east-2"
LANGUAGE_CODE = "en-US"
SAMPLE_RATE_HZ = 16000
SILENCE_THRESHOLD_SECONDS = 3


class SentenceEventHandler(TranscriptResultStreamHandler):
    """Collect final AWS transcript chunks until the speaker pauses."""

    def __init__(self, output_stream, silence_threshold=SILENCE_THRESHOLD_SECONDS):
        super().__init__(output_stream)
        self.partial_sentence = ""
        self.last_update_time = time.time()
        self.silence_threshold = silence_threshold

    async def handle_transcript_event(self, transcript_event: TranscriptEvent):
        for result in transcript_event.transcript.results:
            if result.is_partial:
                continue
            for alternative in result.alternatives:
                self.partial_sentence += alternative.transcript + " "
                self.last_update_time = time.time()

    async def wait_for_sentence(self):
        while True:
            silence_duration = time.time() - self.last_update_time
            if silence_duration >= self.silence_threshold and self.partial_sentence:
                sentence = self.partial_sentence.strip()
                self.partial_sentence = ""
                return sentence
            await asyncio.sleep(0.5)


async def microphone_chunks():
    loop = asyncio.get_event_loop()
    input_queue = asyncio.Queue()

    def callback(indata, frame_count, time_info, status):
        loop.call_soon_threadsafe(input_queue.put_nowait, (bytes(indata), status))

    stream = sd.RawInputStream(
        channels=1,
        samplerate=SAMPLE_RATE_HZ,
        callback=callback,
        blocksize=1024 * 2,
        dtype="int16",
    )
    with stream:
        while True:
            chunk, status = await input_queue.get()
            yield chunk, status


async def send_microphone_audio(stream, stop_event):
    async for chunk, status in microphone_chunks():
        if stop_event.is_set():
            break
        if chunk:
            await stream.input_stream.send_audio_event(audio_chunk=chunk)
    await stream.input_stream.end_stream()


async def start_transcription():
    """Return one user utterance after a short silence."""
    client = TranscribeStreamingClient(region=REGION)
    stream = await client.start_stream_transcription(
        language_code=LANGUAGE_CODE,
        media_sample_rate_hz=SAMPLE_RATE_HZ,
        media_encoding="pcm",
    )

    handler = SentenceEventHandler(stream.output_stream)
    stop_event = asyncio.Event()

    write_task = asyncio.create_task(send_microphone_audio(stream, stop_event))
    event_task = asyncio.create_task(handler.handle_events())
    sentence_task = asyncio.create_task(handler.wait_for_sentence())

    sentence = await sentence_task
    stop_event.set()
    await write_task
    await event_task
    return sentence


if __name__ == "__main__":
    asyncio.run(start_transcription())
