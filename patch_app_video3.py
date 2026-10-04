# -*- coding: utf-8 -*-
with open('frontend/www/app.js', 'r', encoding='utf-8') as f:
    content = f.read()

import re

pattern = r"btnDownloadH5P\.addEventListener\('click', async \(\) => \{\s*const payload = getEditedData\(\);\s*try \{\s*const response = await fetch\(\$\{API_BASE\}/api/export/h5p, \{\s*method: 'POST',\s*headers: \{\s*'Content-Type': 'application/json',\s*\},\s*body: JSON\.stringify\(payload\),\s*\}\);"

replacement = '''btnDownloadH5P.addEventListener('click', async () => {
    const payload = getEditedData();
    
    try {
        const videoInput = document.getElementById('input-video-file');
        const videoFile = (videoInput && videoInput.files.length > 0) ? videoInput.files[0] : null;
        
        let formData = new FormData();
        formData.append('data', JSON.stringify(payload));
        if (videoFile) formData.append('video_file', videoFile);
        
        const response = await fetch(${API_BASE}/api/export/h5p, {
            method: 'POST',
            body: formData
        });'''

if re.search(pattern, content):
    content = re.sub(pattern, replacement.replace('', '$' + '{API_BASE}'), content)
    with open('frontend/www/app.js', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Success app patch 3")
else:
    print("Failed app patch 3")
