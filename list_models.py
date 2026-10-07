import os
import json
import urllib.request
from dotenv import load_dotenv

load_dotenv()

req = urllib.request.Request(
    "https://api.groq.com/openai/v1/models",
    headers={
        "Authorization": f"Bearer {os.environ['GROQ_API_KEY']}",
        "User-Agent": "Mozilla/5.0",
    },
)

with urllib.request.urlopen(req) as response:
    for model in json.load(response)["data"]:
        print(model["id"])