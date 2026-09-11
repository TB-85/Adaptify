import os
from google import genai
from google.genai import types

# Load manually if .env exists
env_path = ".env"
if os.path.exists(env_path):
    with open(env_path, "r") as f:
        for line in f:
            if "GEMINI_API_KEY=" in line:
                os.environ["GEMINI_API_KEY"] = line.split("=", 1)[1].strip()

# Path to an uploaded image
image_path = r"C:\Users\Thomas\.gemini\antigravity\brain\1e5211d9-b4ca-486a-a2c1-fcce8e3f6665\.user_uploaded\media__1786611162163.png"

if not os.path.exists(image_path):
    print("Image not found at:", image_path)
    exit(1)

with open(image_path, "rb") as f:
    img_data = f.read()

client = genai.Client()

models = [
    'gemini-flash-latest',
    'gemini-2.5-flash-lite',
    'gemini-2.5-pro',
    'gemini-3.5-flash-lite',
    'gemini-3.5-flash'
]

part = types.Part.from_bytes(
    data=img_data,
    mime_type="image/png"
)

# Set a timeout/retry option so we don't hang on 503
from google.genai.errors import APIError

for m in models:
    try:
        print(f"\n--- Testing {m} ---")
        response = client.models.generate_content(
            model=m,
            contents=[part, "Describe this image in one short sentence."]
        )
        print(f"Success {m}:", response.text.strip())
    except Exception as e:
        print(f"Failed {m}:", str(e).split('\n')[0])
