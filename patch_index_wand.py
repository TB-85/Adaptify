# -*- coding: utf-8 -*-
with open('frontend/www/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

old_btn = '''<button type="button" onclick="setAiAutoTopics()" class="px-2.5 py-1.5 bg-brand-50 hover:bg-brand-100 text-brand-700 border border-brand-200 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 shadow-sm">
                                <i class="fa-solid fa-wand-magic-sparkles text-brand-600"></i> KI automatisch wählen lassen
                            </button>'''
new_btn = '''<button type="button" onclick="setAiAutoTopics()" class="px-2.5 py-1.5 bg-brand-50 hover:bg-brand-100 text-brand-700 border border-brand-200 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 shadow-sm">
                                KI automatisch wählen lassen
                            </button>'''

if old_btn in content:
    content = content.replace(old_btn, new_btn)
    with open('frontend/www/index.html', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Success wand")
else:
    print("Could not find wand button")
