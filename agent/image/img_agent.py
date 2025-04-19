from mistralai import Mistral
from dotenv import load_dotenv
import os
import mimetypes

load_dotenv()
api_key = os.environ["MISTRAL_KEY"]
client = Mistral(api_key=api_key)


def load_image(image_path):
  import base64
  mime_type, _ = mimetypes.guess_type(image_path)
  with open(image_path, "rb") as image_file:
    image_data = image_file.read()
  base64_encoded = base64.b64encode(image_data).decode('utf-8')
  base64_url = f"data:{mime_type};base64,{base64_encoded}"
  return base64_url


ocr_response = client.ocr.process(
  model="mistral-ocr-latest",
  document={
    "type": "image_url",
    "image_url": load_image(r"D:\PersonalProjects\ExpeBot\agent\image\gpay.jpg"),
  },
)

print(ocr_response)