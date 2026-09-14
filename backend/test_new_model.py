from google import genai
import os

key = os.environ.get("GEMINI_API_KEY", "")
client = genai.Client(api_key=key)

for model_name in ['gemini-2.0-flash', 'gemini-3.5-flash']:
    print(f"\nTeste Modell: {model_name}...")
    try:
        response = client.models.generate_content(
            model=model_name,
            contents='Say hello in German',
        )
        print(f"Erfolg mit {model_name}:", response.text.strip())
        break
    except Exception as e:
        print(f"Fehler mit {model_name}:", e)
