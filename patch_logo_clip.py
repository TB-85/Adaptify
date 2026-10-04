# -*- coding: utf-8 -*-
with open('frontend/www/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

old_logo = '''            <div class="flex items-center gap-2.5 shrink-0 min-w-0">
                <img src="logo_icon.png" alt="Adaptify Logo" class="h-9 w-9 object-contain drop-shadow-sm shrink-0 -mt-2">
                <div class="min-w-0">'''

new_logo = '''            <div class="flex items-center gap-3 shrink-0 min-w-0">
                <img src="logo_icon.png" alt="Adaptify Logo" class="h-10 w-10 object-contain drop-shadow-sm shrink-0">
                <div class="min-w-0 pt-1">'''

if old_logo in content:
    content = content.replace(old_logo, new_logo)
    with open('frontend/www/index.html', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Success clip")
else:
    print("Failed to find clip block")
