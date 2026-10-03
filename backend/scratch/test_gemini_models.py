import os
import sys
from google import genai

env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key and os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("GEMINI_API_KEY="):
                api_key = line.split("=", 1)[1].strip().strip('"\'')

print("API Key present:", bool(api_key))
if api_key:
    client = genai.Client(api_key=api_key)
    models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-2.5-flash-lite", "gemini-3.5-flash-lite"]
    for m in models:
        try:
            res = client.models.generate_content(model=m, contents="Hallo")
            print(f"[OK] {m}: SUCCESS")
        except Exception as e:
            print(f"[FAIL] {m}: {e}")
