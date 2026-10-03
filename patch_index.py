# -*- coding: utf-8 -*-
with open('frontend/www/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

old_block = '''                    <!-- Detaillierte Einstellungen Form -->
                    <h3 class="text-sm font-black text-slate-800 border-b border-slate-200/50 pb-2 flex items-center gap-2">
                        <i class="fa-solid fa-sliders text-brand-500"></i> Didaktische Steuerung
                    </h3>'''

new_block = '''                    <!-- Detaillierte Einstellungen Form -->
                    <h3 class="text-sm font-black text-slate-800 border-b border-slate-200/50 pb-2 flex items-center gap-2">
                        <i class="fa-solid fa-sliders text-brand-500"></i> Didaktische Steuerung
                    </h3>

                    <!-- Optional YouTube Video -->
                    <div class="space-y-1.5 bg-slate-50 border border-slate-200 rounded-2xl p-3.5 shadow-sm">
                        <label class="block text-xs font-bold text-slate-800">
                            <i class="fa-brands fa-youtube text-red-500 mr-1"></i> Einstiegsvideo (Optional)
                        </label>
                        <input type="text" id="input-youtube-url" placeholder="YouTube-Link einfügen (z.B. https://youtu.be/...)" class="w-full px-3 py-2.5 border border-slate-200 bg-white rounded-xl text-xs font-medium text-slate-800 focus:outline-none focus:ring-2 focus:ring-red-500 transition-all shadow-sm">
                    </div>'''

if old_block in content:
    content = content.replace(old_block, new_block)
    with open('frontend/www/index.html', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Success index")
else:
    print("Failed to find index block")
