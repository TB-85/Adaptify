import urllib.request
import json

url = "https://raw.githubusercontent.com/h5p/h5p-branching-scenario/master/semantics.json"
try:
    req = urllib.request.urlopen(url)
    data = json.loads(req.read().decode('utf-8'))
    content_field = [f for f in data[0]['fields'] if f['name'] == 'content'][0]
    print(json.dumps(content_field, indent=2))
except Exception as e:
    print("Error:", e)
