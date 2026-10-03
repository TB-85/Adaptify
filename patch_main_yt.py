# -*- coding: utf-8 -*-
with open('backend/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_sig = '''    task_count: int = Form(1),
    api_key: Optional[str] = Form(None),
    promo_code: Optional[str] = Form(None)
):'''
new_sig = '''    task_count: int = Form(1),
    api_key: Optional[str] = Form(None),
    promo_code: Optional[str] = Form(None),
    youtube_url: Optional[str] = Form(None)
):'''

content = content.replace(old_sig, new_sig)

old_ret = '''    result = await asyncio.to_thread(
        ai_service.generate_differentiated_content,
        files=file_items,
        context=context,
        target_format=target_format,
        task_count=task_count,
        subject=subject,
        school_type=school_type,
        focus_topic=focus_topic,
        hefteintrag_topic=hefteintrag_topic,
        api_key=effective_api_key
    )
    
    return result'''
new_ret = '''    result = await asyncio.to_thread(
        ai_service.generate_differentiated_content,
        files=file_items,
        context=context,
        target_format=target_format,
        task_count=task_count,
        subject=subject,
        school_type=school_type,
        focus_topic=focus_topic,
        hefteintrag_topic=hefteintrag_topic,
        api_key=effective_api_key
    )
    
    if youtube_url and youtube_url.strip():
        result['youtube_url'] = youtube_url.strip()
        
    return result'''

if old_ret in content:
    content = content.replace(old_ret, new_ret)
else:
    print("Failed ret")

with open('backend/main.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Success main.py")
