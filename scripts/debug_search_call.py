import requests, json
API='http://localhost:8000/chat'
payload={'message':'search for previous visits to Apollo Hospital','history':[], 'model_override': None}
try:
    r=requests.post(API,json=payload,timeout=10)
    print('Status:',r.status_code)
    print(json.dumps(r.json(),indent=2))
except Exception as e:
    print('Err',e)
