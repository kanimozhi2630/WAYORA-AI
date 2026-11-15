import sys
import requests

url = 'http://127.0.0.1:8000/detect'
files = {'file': open('bus.jpg', 'rb')}
resp = requests.post(url, files=files)
print('Status:', resp.status_code)
print('Response:', resp.text)
