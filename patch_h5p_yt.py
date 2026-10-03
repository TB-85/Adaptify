# -*- coding: utf-8 -*-
with open('backend/h5p_generator.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_setup = '''        # Setup level node IDs
        if num_questions == 2:
            level_b_id = 3
            level_a_id = 4
        elif num_questions >= 3:
            level_b_id = 6
            level_a_id = 7
        else:
            level_b_id = 1
            level_a_id = 2'''

new_setup = '''        # Setup level node IDs
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
            
content = content.replace(old_setup, new_setup)

old_nodes = '''        # 1. Diagnostic Questions (Branching)
        for i, q in enumerate(questions):'''

new_nodes = '''        # 0. Optional Video Node
        if yt_url:
            video_node = make_node(
                library_str="H5P.CoursePresentation 1.25",
                params_dict={
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
                                        "sources": [{"path": yt_url, "mime": "video/YouTube"}],
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
                content_type_title="Video",
                title_str="Einstiegsvideo",
                next_content_id=1
            )
            content_nodes.append(video_node)

        # 1. Diagnostic Questions (Branching)
        for i, q in enumerate(questions):'''

content = content.replace(old_nodes, new_nodes)

old_deps = '''            {"machineName": "H5P.CoursePresentation", "majorVersion": 1, "minorVersion": 25},
            {"machineName": "H5P.AdvancedText", "majorVersion": 1, "minorVersion": 1}'''
new_deps = '''            {"machineName": "H5P.CoursePresentation", "majorVersion": 1, "minorVersion": 25},
            {"machineName": "H5P.AdvancedText", "majorVersion": 1, "minorVersion": 1},
            {"machineName": "H5P.Video", "majorVersion": 1, "minorVersion": 6}'''
content = content.replace(old_deps, new_deps)

with open('backend/h5p_generator.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Success h5p_generator.py")
