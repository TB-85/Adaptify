from google import genai
import os

# Load manually if .env exists
env_path = ".env"
if os.path.exists(env_path):
    with open(env_path, "r") as f:
        for line in f:
            if "GEMINI_API_KEY=" in line:
                os.environ["GEMINI_API_KEY"] = line.split("=", 1)[1].strip()

key = os.environ.get("GEMINI_API_KEY")
print("Key length:", len(key) if key else 0)

try:
    client = genai.Client()
    # List models
    print("Listing models...")
    for model in client.models.list():
        print("Model:", model.name)
        
    for m in ['gemini-3.7-flash', 'gemini-3.1-flash-lite']:
        print("Testing model:", m)
        try:
            response = client.models.generate_content(
                model=m,
                contents='Hi',
            )
            print(f"Success {m}:", response.text)
            break
        except Exception as e:
            print(f"Failed {m}:", e)
    print("Ergebnis:", response.text)
except Exception as e:
    print("Fehlermeldung:", e)
