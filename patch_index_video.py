# -*- coding: utf-8 -*-
with open('frontend/www/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

old_yt = '''                    <!-- Optional YouTube Video -->
                    <div class="space-y-1.5 bg-red-50/30 border border-red-100 rounded-2xl p-3.5 shadow-sm mb-4">
                        <label class="block text-xs font-bold text-slate-800">
                            <i class="fa-brands fa-youtube text-red-500 mr-1"></i> Einstiegsvideo (Optional)
                        </label>
                        <input type="text" id="input-youtube-url" placeholder="YouTube-Link einfügen (z.B. https://youtu.be/...)" class="w-full px-3 py-2.5 border border-slate-200 bg-white rounded-xl text-xs font-medium text-slate-800 focus:outline-none focus:ring-2 focus:ring-red-500 transition-all shadow-sm">
                        <p class="text-[10px] text-slate-500 font-medium">Wird automatisch als erste Folie in das Branching Scenario eingebaut.</p>
                    </div>'''

new_yt = '''                    <!-- Optional Einstiegsvideo -->
                    <div class="space-y-3 bg-red-50/30 border border-red-100 rounded-2xl p-3.5 shadow-sm mb-4">
                        <label class="block text-xs font-bold text-slate-800">
                            <i class="fa-solid fa-play text-red-500 mr-1"></i> Einstiegsvideo (Optional)
                        </label>
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                            <div class="space-y-1.5">
                                <label class="block text-[10px] font-bold text-slate-600">Option 1: YouTube Link</label>
                                <input type="text" id="input-youtube-url" placeholder="z.B. https://youtu.be/..." class="w-full px-3 py-2 border border-slate-200 bg-white rounded-xl text-xs font-medium text-slate-800 focus:outline-none focus:ring-2 focus:ring-red-500 transition-all shadow-sm">
                            </div>
                            <div class="space-y-1.5">
                                <label class="block text-[10px] font-bold text-slate-600">Option 2: MP4 Video hochladen</label>
                                <input type="file" id="input-video-file" accept="video/mp4" class="w-full px-3 py-1.5 border border-slate-200 bg-white rounded-xl text-xs font-medium text-slate-800 focus:outline-none focus:ring-2 focus:ring-red-500 transition-all shadow-sm file:mr-3 file:py-1 file:px-3 file:rounded-lg file:border-0 file:text-[10px] file:font-bold file:bg-red-50 file:text-red-700 hover:file:bg-red-100 cursor-pointer">
                            </div>
                        </div>
                        <p class="text-[10px] text-slate-500 font-medium">Das Video wird automatisch als allererste Folie in dein H5P-Paket eingebaut.</p>
                    </div>'''

if old_yt in content:
    content = content.replace(old_yt, new_yt)
    with open('frontend/www/index.html', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Success index patch")
else:
    print("Failed to find youtube block in index.html")
