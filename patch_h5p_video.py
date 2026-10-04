# -*- coding: utf-8 -*-
with open('backend/h5p_generator.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update zip writing
old_zip = '''        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr("h5p.json", json.dumps(h5p_json, indent=2, ensure_ascii=False))
            zip_file.writestr("content/content.json", json.dumps(content_json, indent=2, ensure_ascii=False))
            
        zip_buffer.seek(0)'''
new_zip = '''        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr("h5p.json", json.dumps(h5p_json, indent=2, ensure_ascii=False))
            zip_file.writestr("content/content.json", json.dumps(content_json, indent=2, ensure_ascii=False))
            
            if "video_bytes" in data and "video_filename" in data:
                zip_file.writestr(f"content/videos/{data['video_filename']}", data["video_bytes"])
            
        zip_buffer.seek(0)'''
content = content.replace(old_zip, new_zip)

# 2. Update level node IDs and offset
old_offset = '''        # Setup level node IDs
        yt_url = data.get('youtube_url')
        offset = 1 if yt_url else 0
        if num_questions == 2:
            level_b_id = 3 + offset
            level_a_id = 4 + offset
        elif num_questions >= 3:
            level_b_id = 6 + offset
            level_a_id = 7 + offset
        else:
            level_b_id = 1 + offset
            level_a_id = 2 + offset'''
new_offset = '''        # Setup level node IDs
        yt_url = data.get('youtube_url')
        video_filename = data.get('video_filename')
        offset = 1 if (yt_url or video_filename) else 0
        if num_questions == 2:
            level_b_id = 3 + offset
            level_a_id = 4 + offset
        elif num_questions >= 3:
            level_b_id = 6 + offset
            level_a_id = 7 + offset
        else:
            level_b_id = 1 + offset
            level_a_id = 2 + offset'''
content = content.replace(old_offset, new_offset)

# 3. Add video node injection
old_nodes = '''            node["feedback"] = {
                "title": "",
                "subtitle": ""
            }
            return node

        # 1. Build Diagnostic Branching Tree Nodes (BranchingQuestions)
        if num_questions == 2:'''
new_nodes = '''            node["feedback"] = {
                "title": "",
                "subtitle": ""
            }
            return node

        # 0. Optional Video Node
        if yt_url or video_filename:
            source = {"path": yt_url, "mime": "video/YouTube"} if yt_url else {"path": f"videos/{video_filename}", "mime": "video/mp4"}
            video_node = make_node(
                "H5P.CoursePresentation 1.25",
                {
                    "presentation": {
                        "slides": [{
                            "elements": [{
                                "x": 10,
                                "y": 10,
                                "width": 80,
                                "height": 80,
                                "action": {
                                    "library": "H5P.Video 1.6",
                                    "params": {
                                        "sources": [source],
                                        "visuals": {"fit": False, "controls": True},
                                        "playback": {"autoplay": False, "loop": False}
                                    },
                                    "subContentId": "yt-video",
                                    "metadata": {"contentType": "Video", "license": "U", "title": "Einstiegsvideo"}
                                },
                                "alwaysDisplayComments": False,
                                "backgroundOpacity": 0,
                                "displayAsButton": False,
                                "invisible": False,
                                "solution": ""
                            }]
                        }],
                        "keywordListEnabled": False,
                        "globalBackgroundSelector": {"imageSlideBackground": {"path": ""}},
                        "keywordListAlwaysShow": False,
                        "keywordListAutoHide": False,
                        "keywordListOpacity": 90
                    },
                    "override": {
                        "activeSurface": False,
                        "hideSummarySlide": True,
                        "showSolutionButton": "",
                        "retryButton": "",
                        "summarySlideSolutionButton": False,
                        "summarySlideRetryButton": False,
                        "enablePrintButton": False,
                        "social": {"showFacebookShare": False, "showTwitterShare": False, "showGoogleShare": False}
                    },
                    "l10n": {"startScreenButtonText": "Start", "endScreenButtonText": "Restart", "backButtonText": "Zurück", "disableProceedButtonText": "Bitte warte", "replayButtonText": "Replay", "scoreText": "Score:", "fullscreenAria": "Vollbild"}
                },
                "Video", "Einstiegsvideo", 1
            )
            content_nodes.append(video_node)

        # 1. Build Diagnostic Branching Tree Nodes (BranchingQuestions)
        if num_questions == 2:'''
content = content.replace(old_nodes, new_nodes)

# 4. Inject H5P.Video dependency if yt_url or mp4
old_deps = '''        dependencies = [
            {"machineName": "H5P.BranchingQuestion", "majorVersion": 1, "minorVersion": 0},
            {"machineName": "FontAwesome", "majorVersion": 4, "minorVersion": 5},
            {"machineName": "H5P.CoursePresentation", "majorVersion": 1, "minorVersion": 25},
            {"machineName": "H5P.AdvancedText", "majorVersion": 1, "minorVersion": 1}
        ]'''
new_deps = '''        dependencies = [
            {"machineName": "H5P.BranchingQuestion", "majorVersion": 1, "minorVersion": 0},
            {"machineName": "FontAwesome", "majorVersion": 4, "minorVersion": 5},
            {"machineName": "H5P.CoursePresentation", "majorVersion": 1, "minorVersion": 25},
            {"machineName": "H5P.AdvancedText", "majorVersion": 1, "minorVersion": 1}
        ]
        
        if data.get("youtube_url") or data.get("video_filename"):
            dependencies.append({"machineName": "H5P.Video", "majorVersion": 1, "minorVersion": 6})'''
content = content.replace(old_deps, new_deps)


with open('backend/h5p_generator.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Success patch h5p video")
