# -*- coding: utf-8 -*-
import os
import re

files_to_check = [
    'backend/main.py',
    'backend/test_alltagstauglichkeit.py',
    'frontend/www/app.js',
    'frontend/www/index.html'
]

replacements = [
    (r'(?i)mebis / ByCS', 'ByCS'),
    (r'(?i)ByCS / mebis', 'ByCS'),
    (r'(?i)ByCS & mebis', 'ByCS'),
    (r'(?i)mebis & Moodle', 'Moodle'),
    (r'(?i)mebis, ByCS', 'ByCS'),
    (r'(?i)mebis-, ByCS-', 'ByCS-'),
    (r'(?i)mebis-', 'ByCS-'),
    (r'(?i)ByCS-, mebis-', 'ByCS-'),
    (r'(?i)mebis/Moodle', 'Moodle'),
    (r'(?i)mebis und Moodle', 'Moodle'),
    (r'(?i)ByCS, Moodle- und mebis', 'ByCS und Moodle'),
    (r'(?i)Moodle, mebis, ByCS', 'Moodle, ByCS'),
    (r'(?i)mebis, ByCS und Moodle', 'ByCS und Moodle'),
    (r'(?i)in dein mebis- oder Moodle-Textfeld', 'in dein ByCS- oder Moodle-Textfeld'),
    (r'(?i)\bmebis\b', 'ByCS')
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
