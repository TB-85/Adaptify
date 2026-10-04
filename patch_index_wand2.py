# -*- coding: utf-8 -*-
import re
with open('frontend/www/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

pattern = r'<i class="fa-solid fa-wand-magic-sparkles text-brand-600"></i>\s*KI automatisch wählen lassen'
replacement = r'KI automatisch wählen lassen'
content = re.sub(pattern, replacement, content)

with open('frontend/www/index.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("Success wand 2")
