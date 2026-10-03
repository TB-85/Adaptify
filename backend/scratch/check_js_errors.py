import re

with open('frontend/www/app.js', 'r', encoding='utf-8') as f:
    js = f.read()

lines = js.split('\n')
for i, l in enumerate(lines):
    if 'topic' in l.lower() or 'focus' in l.lower():
        print(f"{i+1}: {l[:120]}")
