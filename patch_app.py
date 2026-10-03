# -*- coding: utf-8 -*-
import os
with open('frontend/www/app.js', 'r', encoding='utf-8') as f:
    content = f.read()

old_state = '''let appState = {
    selectedFile: null,
    generatedData: null,'''
new_state = '''let appState = {
    selectedFiles: [],
    selectedFile: null,
    generatedData: null,'''
content = content.replace(old_state, new_state)

old_reset = '''function resetFileSelection() {
    appState.selectedFile = null;
    appState.originalDataUrl = null;'''
new_reset = '''function resetFileSelection() {
    appState.selectedFile = null;
    appState.selectedFiles = [];
    appState.originalDataUrl = null;'''
content = content.replace(old_reset, new_reset)

old_submit = '''    // Prepare FormData
    const formData = new FormData();
    formData.append('file', appState.selectedFile);'''
new_submit = '''    // Prepare FormData
    const formData = new FormData();
    if (appState.selectedFiles && appState.selectedFiles.length > 1) {
        appState.selectedFiles.forEach((f, idx) => {
            if (idx === 0 && appState.selectedFile) {
                formData.append('files', appState.selectedFile);
            } else {
                formData.append('files', f);
            }
        });
    } else {
        formData.append('files', appState.selectedFile);
    }'''
content = content.replace(old_submit, new_submit)

old_handle = '''fileInput.addEventListener('change', () => {
    if (fileInput.files.length > 0) {
        handleFile(fileInput.files[0]);
    }
});'''
new_handle = '''fileInput.addEventListener('change', () => {
    if (fileInput.files.length > 0) {
        handleFiles(fileInput.files);
    }
});

async function handleFiles(filesList) {
    if (!filesList || filesList.length === 0) return;
    
    appState.selectedFiles = Array.from(filesList);
    const firstFile = appState.selectedFiles[0];
    await handleFile(firstFile);
    
    if (appState.selectedFiles.length > 1) {
        fileName.textContent = appState.selectedFiles.length + " Dateien ausgewählt";
        let totalSize = appState.selectedFiles.reduce((acc, f) => acc + f.size, 0);
        fileSize.textContent = totalSize > 1024 * 1024 ? (totalSize / (1024 * 1024)).toFixed(2) + " MB" : (totalSize / 1024).toFixed(0) + " KB";
        
        const btnCrop = document.getElementById('btn-crop-image');
        if (btnCrop) btnCrop.classList.add('hidden');
    }
}
'''
content = content.replace(old_handle, new_handle)

with open('frontend/www/app.js', 'w', encoding='utf-8') as f:
    f.write(content)
