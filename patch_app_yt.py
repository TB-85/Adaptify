# -*- coding: utf-8 -*-
with open('frontend/www/app.js', 'r', encoding='utf-8') as f:
    content = f.read()

old_block = '''const inputTaskCount = document.getElementById('input-task-count');
const inputPromoCode = document.getElementById('input-promo-code');'''

new_block = '''const inputTaskCount = document.getElementById('input-task-count');
const inputPromoCode = document.getElementById('input-promo-code');
const inputYoutubeUrl = document.getElementById('input-youtube-url');'''

if old_block in content:
    content = content.replace(old_block, new_block)
else:
    print("Could not find variables block")

old_append = '''    formData.append('promo_code', promoCodeVal);'''
new_append = '''    formData.append('promo_code', promoCodeVal);
    formData.append('youtube_url', (typeof inputYoutubeUrl !== 'undefined' && inputYoutubeUrl) ? inputYoutubeUrl.value : '');'''

if old_append in content:
    content = content.replace(old_append, new_append)
else:
    print("Could not find append block")

# Let's fix the multi-file append for Camera button to append instead of overwrite
old_handleFiles = '''async function handleFiles(filesList) {
    if (!filesList || filesList.length === 0) return;
    
    appState.selectedFiles = Array.from(filesList);'''
new_handleFiles = '''async function handleFiles(filesList) {
    if (!filesList || filesList.length === 0) return;
    
    // Append instead of overwrite so multiple camera shots work
    if (!appState.selectedFiles) appState.selectedFiles = [];
    appState.selectedFiles = appState.selectedFiles.concat(Array.from(filesList));'''

if old_handleFiles in content:
    content = content.replace(old_handleFiles, new_handleFiles)
else:
    print("Could not find handleFiles block")


with open('frontend/www/app.js', 'w', encoding='utf-8') as f:
    f.write(content)
print("Success app.js")
