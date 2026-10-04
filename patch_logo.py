# -*- coding: utf-8 -*-
with open('frontend/www/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

old_logo = '''            <div class="flex items-center gap-3">
                <img src="logo_icon.png" alt="Adaptify Logo" class="h-11 w-11 object-contain drop-shadow-sm shrink-0 -mt-1">
                <div>
                    <h1 class="text-xl font-extrabold tracking-tight text-slate-900 flex items-center gap-1.5">
                        <span>Adapt<span class="text-brand-500">ify</span></span>
                        <span class="text-[9px] font-bold bg-brand-50 border border-brand-200 text-brand-700 px-1.5 py-0.5 rounded-md uppercase tracking-wide">Beta</span>
                    </h1>
                    <p class="text-[10px] text-slate-400 font-bold flex items-center gap-1">
                        <span id="header-school-name">Testschullizenz Amperschule Olching</span>
                    </p>
                </div>
            </div>'''

new_logo = '''            <div class="flex items-center gap-3 shrink-0 min-w-0">
                <img src="logo_icon.png" alt="Adaptify Logo" class="h-11 w-11 object-contain drop-shadow-sm shrink-0 -mt-1">
                <div class="min-w-0">
                    <h1 class="text-xl font-extrabold tracking-tight text-slate-900 flex items-center gap-1.5 shrink-0">
                        <span>Adapt<span class="text-brand-500">ify</span></span>
                        <span class="text-[9px] font-bold bg-brand-50 border border-brand-200 text-brand-700 px-1.5 py-0.5 rounded-md uppercase tracking-wide shrink-0">Beta</span>
                    </h1>
                    <p class="text-[10px] text-slate-400 font-bold truncate w-full" title="Testschullizenz Amperschule Olching">
                        <span id="header-school-name" class="truncate">Testschullizenz Amperschule Olching</span>
                    </p>
                </div>
            </div>'''

if old_logo in content:
    content = content.replace(old_logo, new_logo)
    with open('frontend/www/index.html', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Success logo")
else:
    print("Failed to find logo block")
