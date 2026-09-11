import urllib.request
import json

url = "https://raw.githubusercontent.com/h5p/h5p-branching-scenario/master/semantics.json"
try:
    req = urllib.request.urlopen(url)
    data = json.loads(req.read().decode('utf-8'))
    fields = data[0]['fields']
    for f in fields:
        print("Field Name:", f['name'], "Type:", f['type'])
        if f['name'] == 'content':
            print("Content fields:")
            for inner in f['field']['fields']:
                print("  -", inner['name'], "Type:", inner['type'])
except Exception as e:
    print("Error:", e)
