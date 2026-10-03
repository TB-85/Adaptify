# -*- coding: utf-8 -*-
import os
import re
with open('backend/ai_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Let's replace the whole try block contents that parse the file
old_block = '''        try:
            # Check if document is DOCX
            is_docx = (mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' 
                       or mime_type.endswith('document') 
                       or mime_type.endswith('docx'))
            
            if is_docx:
                extracted_text = extract_text_from_docx(file_content)
                logger.info("Successfully extracted text from DOCX locally.")
                contents = [
                    f"Hier ist der Text des hochgeladenen Word-Dokuments (.docx):\\n\\n{extracted_text}\\n\\n",
                    prompt
                ]
            else:
                part = types.Part.from_bytes(
                    data=file_content,
                    mime_type=mime_type
                )
                contents = [part, prompt]'''

new_block = '''        try:
            contents = []
            extracted_texts = []
            
            for f in files:
                fc = f['content']
                mt = f['mime_type']
                is_docx = (mt == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' 
                           or mt.endswith('document') 
                           or mt.endswith('docx'))
                
                if is_docx:
                    extracted_texts.append(extract_text_from_docx(fc))
                else:
                    contents.append(types.Part.from_bytes(
                        data=fc,
                        mime_type=mt
                    ))
            
            if extracted_texts:
                combined_text = "\\n\\n--- Nächste Datei ---\\n\\n".join(extracted_texts)
                contents.append(f"Hier ist der extrahierte Text aus den hochgeladenen Dokumenten:\\n\\n{combined_text}")
            
            contents.append(prompt)'''

if old_block in content:
    content = content.replace(old_block, new_block)
    with open('backend/ai_service.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Success")
else:
    print("Could not find the block to replace!")
