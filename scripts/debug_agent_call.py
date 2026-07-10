import requests
import json

API = "http://localhost:8000/chat"

payload = {
    "message": "I met Dr Rajesh Patel at Apollo Hospital today. Discussed CardioPlus, interest was high, followup next Monday.",
    "history": [],
    "model_override": None
}

try:
    r = requests.post(API, json=payload, timeout=10)
    print("Status:", r.status_code)
    try:
        print(json.dumps(r.json(), indent=2))
    except Exception:
        print('Response text:', r.text)
except Exception as e:
    print('Error calling agent:', str(e))
