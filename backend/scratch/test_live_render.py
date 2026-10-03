import urllib.request
import io
import time
from PIL import Image

url = 'https://adaptify-xpym.onrender.com/api/generate'
boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
body = []

def add_field(name, val):
    body.append(f'--{boundary}'.encode())
    body.append(f'Content-Disposition: form-data; name="{name}"'.encode())
    body.append(b'')
    body.append(str(val).encode())

def add_file(name, filename, content):
    body.append(f'--{boundary}'.encode())
    body.append(f'Content-Disposition: form-data; name="{name}"; filename="{filename}"'.encode())
    body.append(b'Content-Type: image/jpeg')
    body.append(b'')
    body.append(content)

img = Image.new('RGB', (100, 100), color = 'blue')
img_byte_arr = io.BytesIO()
img.save(img_byte_arr, format='JPEG')

add_file('file', 'test_nocache.jpg', img_byte_arr.getvalue())
add_field('subject', 'Mathematik')
add_field('school_type', 'Mittelschule')
add_field('focus_topic', f'Prozentrechnung {int(time.time())}')
add_field('hefteintrag_topic', '')
add_field('context', 'Einzigartiger Test ohne Cache')
add_field('target_format', 'Lückentext')
add_field('task_count', '1')
add_field('promo_code', 'SCHULE2026')

body.append(f'--{boundary}--\r\n'.encode())
payload = b'\r\n'.join(body)

req = urllib.request.Request(url, data=payload, headers={'Content-Type': f'multipart/form-data; boundary={boundary}'})

start = time.time()
print("Sending unique request to live Render service...")
try:
    with urllib.request.urlopen(req, timeout=60) as resp:
        print('Status:', resp.status)
        print('Time taken:', round(time.time() - start, 2), 's')
        data = resp.read().decode()
        print('Is Demo Mode:', '[DEMO-MODUS]' in data)
        print('Response preview:', data[:300])
except Exception as e:
    print('Error:', e)
    if hasattr(e, 'read'):
        print('Error details:', e.read().decode())
