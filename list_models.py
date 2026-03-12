import os

import google.generativeai as genai
from dotenv import load_dotenv


load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("GEMINI_API_KEY not set in .env")

genai.configure(api_key=api_key)

print("Models that support generateContent:\n")
for model in genai.list_models():
    methods = getattr(model, "supported_generation_methods", [])
    if "generateContent" in methods:
        print(model.name)
