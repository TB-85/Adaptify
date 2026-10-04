# -*- coding: utf-8 -*-
import os
import re

files_to_check = [
    'frontend/www/app.js',
    'frontend/www/index.html'
]

replacements = [
    (r'(?i)oder Moodle-Textfeld', 'Textfeld'),
    (r'(?i)Mit Moodle-Notenübermittlung', 'Mit Notenübermittlung'),
    (r'(?i)Moodle / ByCS / Canvas', 'ByCS'),
    (r'(?i)und Moodle-Plattformen', '')
]

for filepath in files_to_check:
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        for old, new in replacements:
            content = re.sub(old, new, content)
            
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {filepath}")
