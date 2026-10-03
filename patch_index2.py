# -*- coding: utf-8 -*-
with open('frontend/www/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

old_block = '''                    <!-- School Type & Target Format Grid -->'''

new_block = '''                    <!-- Optional YouTube Video -->
                    <div class="space-y-1.5 bg-red-50/30 border border-red-100 rounded-2xl p-3.5 shadow-sm mb-4">
                        <label class="block text-xs font-bold text-slate-800">
                            <i class="fa-brands fa-youtube text-red-500 mr-1"></i> Einstiegsvideo (Optional)
                        </label>
                        <input type="text" id="input-youtube-url" placeholder="YouTube-Link einfügen (z.B. https://youtu.be/...)" class="w-full px-3 py-2.5 border border-slate-200 bg-white rounded-xl text-xs font-medium text-slate-800 focus:outline-none focus:ring-2 focus:ring-red-500 transition-all shadow-sm">
                        <p class="text-[10px] text-slate-500 font-medium">Wird automatisch als erste Folie in das Branching Scenario eingebaut.</p>
                    </div>

                    <!-- School Type & Target Format Grid -->'''

if old_block in content:
    content = content.replace(old_block, new_block)
    with open('frontend/www/index.html', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Success index")
else:
    print("Failed to find index block")
