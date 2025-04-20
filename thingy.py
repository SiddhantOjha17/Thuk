from pathlib import Path
from agents import Agent, Runner
from pydantic import BaseModel
from typing import Literal
import asyncio
import os

from openai import OpenAI
from mistralai import Mistral
import mimetypes


mistral_api_key = os.environ["MISTRAL_KEY"]
mistral_client = Mistral(api_key=mistral_api_key)

openai_api_key = os.getenv("OPENAI_API_KEY")
openai_client = OpenAI(api_key=openai_api_key)


def get_text_from_image(fp: Path):
    def load_image(image_path):
        import base64

        mime_type, _ = mimetypes.guess_type(image_path)
        with open(image_path, "rb") as image_file:
            image_data = image_file.read()
        base64_encoded = base64.b64encode(image_data).decode("utf-8")
        base64_url = f"data:{mime_type};base64,{base64_encoded}"
        return base64_url

    ocr_response = mistral_client.ocr.process(
        model="mistral-ocr-latest",
        document={
            "type": "image_url",
            "image_url": load_image(fp),
        },
    )
    return ocr_response


def get_text_from_audio(fp: Path):
    with open(fp, "rb") as audio_file:
        transcription = openai_client.audio.transcriptions.create(
            model="whisper-1", file=audio_file
        )
    return transcription.text


# TODO: Not sure to make this a filepath or wtv content wtv
# Filepath could be better for logging and testing and stuff,
def get_text_for_thing(fp: Path):
    ft = mimetypes.guess_type(fp)
    if "image" in ft or "video" in ft:
        text = get_text_from_image(fp)
    elif "audio" in ft:
        text = get_text_from_audio(fp=fp)
    else:
        with open(fp, "r") as f_in:
            text = f_in.read()
    return text


async def run_agent(input_text):
    class Transaction(BaseModel):
        amount: float
        description: str
        category: Literal["Travel", "Dining", "Shopping", "Misc"]

    finance_agent = Agent(
        name="Financial Agent",
        instructions="""You are a financial analyst agent. Your job is
        to extract entities from a given text related to
        a transaction. 
        As output, you must produce a
        structured output containing the relevant schema.
        """,
        output_type=Transaction,
    )

    result = await Runner.run(starting_agent=finance_agent, input=input_text)
    return result


if __name__ == "__main__":
    result = asyncio.run(run_agent("I Spent 5000 on alcohol today at 9 am"))
    print(result)
