from dotenv import load_dotenv
import os
load_dotenv()

key = os.getenv('CEREBRAS_API_KEY')
print(f"Key found: {'YES' if key else 'NO'}")
print(f"Key starts with: {key[:8] if key else 'N/A'}...")

from cerebras.cloud.sdk import Cerebras
client = Cerebras(api_key=key)

try:
    response = client.chat.completions.create(
        model="llama3.1-8b",
        messages=[{"role": "user", "content": "Say hello"}],
        max_tokens=50
    )
    print("LLM response:", response.choices[0].message.content)
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
