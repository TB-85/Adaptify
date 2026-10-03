import os
with open('backend/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('file: UploadFile = File(...)', 'files: List[UploadFile] = File(...)')
content = content.replace('logger.info(f\"Received file: {file.filename}', 'logger.info(f\"Received files: {[f.filename for f in files]}')

old_file_read = '''    # Read file content
    contents = await file.read()
    
    # Determine MIME type
    mime_type = file.content_type
    if not mime_type:
        # Fallback based on extension
        ext = os.path.splitext(file.filename)[1].lower()
        if ext in ['.jpg', '.jpeg']:
            mime_type = 'image/jpeg'
        elif ext == '.png':
            mime_type = 'image/png'
        elif ext == '.pdf':
            mime_type = 'application/pdf'
        else:
            mime_type = 'image/jpeg'
            
    # Call Gemini API
    result = await asyncio.to_thread(
        ai_service.generate_differentiated_content,
        contents,
        mime_type,
        context,
        target_format,
        task_count,
        subject,
        school_type,
        focus_topic,
        hefteintrag_topic,
        effective_api_key
    )'''

new_file_read = '''    file_items = []
    for uploaded_file in files:
        contents = await uploaded_file.read()
        mime_type = uploaded_file.content_type
        if not mime_type:
            ext = os.path.splitext(uploaded_file.filename)[1].lower()
            if ext in ['.jpg', '.jpeg']:
                mime_type = 'image/jpeg'
            elif ext == '.png':
                mime_type = 'image/png'
            elif ext == '.pdf':
                mime_type = 'application/pdf'
            else:
                mime_type = 'image/jpeg'
        file_items.append({'content': contents, 'mime_type': mime_type})
            
    # Call Gemini API
    result = await asyncio.to_thread(
        ai_service.generate_differentiated_content,
        file_items,
        context,
        target_format,
        task_count,
        subject,
        school_type,
        focus_topic,
        hefteintrag_topic,
        effective_api_key
    )'''

content = content.replace(old_file_read, new_file_read)

with open('backend/main.py', 'w', encoding='utf-8') as f:
    f.write(content)
