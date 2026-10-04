# -*- coding: utf-8 -*-
with open('frontend/www/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

old_logo = '''<img src="logo_icon.png" alt="Adaptify Logo" class="h-10 w-10 object-contain drop-shadow-sm shrink-0">'''
new_logo = '''<img src="logo_icon.png" alt="Adaptify Logo" class="h-10 w-auto shrink-0" style="max-height: 40px; display: block;">'''

if old_logo in content:
    content = content.replace(old_logo, new_logo)
    with open('frontend/www/index.html', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Success logo fix")
else:
    print("Failed to find logo")
