# -*- coding: utf-8 -*-
with open('backend/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_h5p = '''@app.post("/api/export/h5p")
async def export_h5p(data: ExportData):
    \"\"\"
    Takes the structured task JSON and builds the H5P Branching Scenario zip file.
    \"\"\"
    try:
        h5p_bytes = H5PGenerator.create_h5p_zip(data.dict())
        disposition = make_content_disposition(data.title, "differenziert.h5p")
        
        return Response(
            content=h5p_bytes,
            media_type="application/zip",
            headers={
                "Content-Disposition": disposition
            }
        )'''

new_h5p = '''@app.post("/api/export/h5p")
async def export_h5p(data: str = Form(...), video_file: UploadFile = File(None)):
    \"\"\"
    Takes the structured task JSON and builds the H5P Branching Scenario zip file.
    \"\"\"
    import json
    try:
        json_data = json.loads(data)
        if video_file and video_file.filename:
            json_data["video_bytes"] = await video_file.read()
            json_data["video_filename"] = video_file.filename
            
        h5p_bytes = H5PGenerator.create_h5p_zip(json_data)
        disposition = make_content_disposition(json_data.get("title", "Export"), "differenziert.h5p")
        
        return Response(
            content=h5p_bytes,
            media_type="application/zip",
            headers={
                "Content-Disposition": disposition
            }
        )'''

if old_h5p in content:
    content = content.replace(old_h5p, new_h5p)
    with open('backend/main.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Success main h5p upload 2")
else:
    print("Failed to find main h5p upload block 2")
