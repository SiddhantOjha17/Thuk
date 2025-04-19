import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=API_KEY)
audio_file = open(r"D:\PersonalProjects\ExpeBot\agent\speech\sample.mp4", "rb")

transcription = client.audio.transcriptions.create(model="whisper-1", file=audio_file)

print(transcription.text)

