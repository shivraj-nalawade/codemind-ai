import os
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq

# Load environment variables
env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(env_path)

# Get API key and model
api_key = os.getenv("GROQ_API_KEY")
model = os.getenv("LEARNING_MODEL", "openai/gpt-oss-120b")

if not api_key:
    raise ValueError("GROQ_API_KEY not found in .env file")

# Initialize Groq client
client = Groq(api_key=api_key)

try:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are a programming tutor."
            },
            {
                "role": "user",
                "content": "Explain Python variables with a simple example."
            }
        ],
        temperature=0.2
    )

    print("\nGroq API connected successfully!")
    print("Model:", model)
    print("\nAI Response:\n")
    print(response.choices[0].message.content)

except Exception as e:
    print("Groq API Error:", e)