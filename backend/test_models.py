import os
from google import genai

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))
models = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-2.5-flash', 'gemini-3.0-flash', 'gemini-pro', 'gemini-3.5-flash-lite']

for m in models:
    try:
        print(f"Trying {m}...")
        response = client.models.generate_content(model=m, contents='Hello')
        print(f"Success {m}:", response.text[:20].replace('\n', ' '))
    except Exception as e:
        print(f"Failed {m}:", str(e).split('\n')[0])
