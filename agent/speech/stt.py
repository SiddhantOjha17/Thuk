# import torch
# from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
# from datasets import load_dataset


# device = "cuda:0" if torch.cuda.is_available() else "cpu"
# torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

# model_id = "distil-whisper/distil-large-v3"

# model = AutoModelForSpeechSeq2Seq.from_pretrained(
#     model_id, torch_dtype=torch_dtype, low_cpu_mem_usage=True, use_safetensors=True
# )
# model.to(device)

# processor = AutoProcessor.from_pretrained(model_id)

# pipe = pipeline(
#     "automatic-speech-recognition",
#     model=model,
#     tokenizer=processor.tokenizer,
#     feature_extractor=processor.feature_extractor,
#     max_new_tokens=128,
#     torch_dtype=torch_dtype,
#     device=device,
# )

# # dataset = load_dataset("hf-internal-testing/librispeech_asr_dummy", "clean", split="validation")
# # sample = dataset[0]["audio"]
# audio_path = "sample.mp4"  
# from pathlib import Path

# if not Path(audio_path).exists():
#     raise FileNotFoundError(f"Audio file not found at {audio_path}")

# result = pipe(audio_path)
# print(result["text"])

# import torch
# from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
# from datasets import load_dataset


# device = "cuda:0" if torch.cuda.is_available() else "cpu"
# torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

# model_id = "distil-whisper/distil-large-v3"

# model = AutoModelForSpeechSeq2Seq.from_pretrained(
#     model_id, torch_dtype=torch_dtype, low_cpu_mem_usage=True, use_safetensors=True,
# )
# model.to(device)

# processor = AutoProcessor.from_pretrained(model_id)

# pipe = pipeline(
#     "automatic-speech-recognition",
#     model=model,
#     tokenizer=processor.tokenizer,
#     feature_extractor=processor.feature_extractor,
#     max_new_tokens=128,
#     torch_dtype=torch_dtype,
#     device=device,
    
# )

# audio_path = "sample.mp4"  
# from pathlib import Path

# if not Path(audio_path).exists():
#     raise FileNotFoundError(f"Audio file not found at {audio_path}")

# result = pipe(audio_path, return_timestamps=True)
# print(result)
import os 
from dotenv import load_dotenv
from openai import OpenAI
load_dotenv()
API_KEY=os.getenv('OPENAI_API_KEY')

client = OpenAI(api_key=API_KEY)
audio_file= open(r"D:\PersonalProjects\ExpeBot\agent\speech\sample.mp4", "rb")

transcription = client.audio.transcriptions.create(
    model="whisper-1", 
    file=audio_file
)

print(transcription.text)