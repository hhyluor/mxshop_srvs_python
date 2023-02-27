import requests

headers = {"contentType": "application/json"}

rsp = requests.get("http://192.168.16.196:8022/health", headers=headers)
print(rsp)

print(rsp.text)