# -*- coding: utf-8 -*-
with open('frontend/www/app.js', 'r', encoding='utf-8') as f:
    content = f.read()

old_fetch = '''btnDownloadH5P.addEventListener('click', async () => {
    const payload = getEditedData();
    
    try {
        const response = await fetch(${API_BASE}/api/export/h5p, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
        });'''

new_fetch = '''btnDownloadH5P.addEventListener('click', async () => {
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

if old_fetch in content:
    content = content.replace(old_fetch, new_fetch)
    with open('frontend/www/app.js', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Success app patch 2")
else:
    print("Failed app patch 2")
