import json
import zipfile
import io
import re
import os
import uuid

class H5PGenerator:
    @staticmethod
    def parse_multiple_choice_text(text):
        """
        Parses text in format:
        Frage: Was ist ...?
        [ ] Option A
        [X] Option B (Richtig)
        [ ] Option C
        """
        questions = []
        blocks = re.split(r"Frage:\s*", text)
        for block in blocks:
            if not block.strip():
                continue
            lines = block.strip().split("\n")
            q_text = lines[0].strip()
            answers = []
            for line in lines[1:]:
                line = line.strip()
                if line.startswith("[ ]") or line.startswith("[X]") or line.startswith("[x]"):
                    is_correct = line.startswith("[X]") or line.startswith("[x]")
                    ans_text = line[3:].strip()
                    answers.append({
                        "text": ans_text,
                        "correct": is_correct,
                        "tipsAndFeedback": {
                            "tip": "",
                            "chosenFeedback": "",
                            "notChosenFeedback": ""
                        }
                    })
            if q_text and answers:
                questions.append({
                    "question": f"<p>{q_text}</p>\n",
                    "answers": answers
                })
        return questions

    @staticmethod
    def parse_dialogcards_text(text):
        """
        Parses text in format:
        Vorderseite: ...
        Rückseite: ...
        """
        cards = []
        blocks = text.split("---")
        for block in blocks:
            lines = [l.strip() for l in block.strip().split("\n") if l.strip()]
            front = ""
            back = ""
            for line in lines:
                if line.startswith("Vorderseite:"):
                    front = line[12:].strip()
                elif line.lower().startswith("rückseite:"):
                    back = line[10:].strip()
            if front and back:
                cards.append({
                    "text": front,
                    "answer": back
                })
        return cards

    @staticmethod
    def parse_true_false_text(text):
        """
        Parses text in format:
        Aussage: [Hier die Behauptung]
        Antwort: [Wahr oder Falsch]
        """
        statements = []
        blocks = text.split("---")
        for block in blocks:
            lines = [l.strip() for l in block.strip().split("\n") if l.strip()]
            statement = ""
            answer = True
            for line in lines:
                if line.lower().startswith("aussage:"):
                    statement = line[8:].strip()
                elif line.lower().startswith("antwort:"):
                    ans_str = line[8:].strip().lower()
                    answer = "wahr" in ans_str or "true" in ans_str or "richtig" in ans_str
            
            # Fallback: if no "Aussage:" prefix was used, take the first line (that isn't an answer)
            if not statement and lines:
                for line in lines:
                    if not line.lower().startswith("antwort:"):
                        statement = line
                        break
                        
            if statement:
                statements.append({
                    "question": f"<p>{statement}</p>\n",
                    "correct": answer
                })
        return statements

    @staticmethod
    def clean_slashes_for_drag_text(text):
        """
        Removes alternative options (synonyms) separated by slashes within blanks
        for Drag the Words, keeping only the first option.
        Example: *3,14/3.14* -> *3,14*
        Example: *Kreisumfang/Umfang:hint* -> *Kreisumfang:hint*
        """
        def repl(match):
            content = match.group(1)
            hint = ""
            if ":" in content:
                content, hint = content.split(":", 1)
                hint = ":" + hint
            if "/" in content:
                content = content.split("/", 1)[0]
            return f"*{content}{hint}*"
        
        return re.sub(r"\*([^*]+)\*", repl, text)

    @staticmethod
    def create_content_json(data):
        title = data.get("title", "Differenzierte Übung")
        target_format = data.get("target_format", "Lückentext")
        questions = data.get("diagnostic", {}).get("questions", [])
        level_a = data.get("level_a", {})
        level_b = data.get("level_b", {})

        content_nodes = []
        num_questions = len(questions)
        
        # Setup level node IDs
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
            level_a_id = 2 + offset

        # Helper for creating node compliant with ByCS BranchingScenario
        def make_node(library_str, params_dict, content_type_title, title_str, next_content_id=None):
            node = {
                "contentId": len(content_nodes),
                "type": {
                    "library": library_str,
                    "params": params_dict,
                    "subContentId": str(uuid.uuid4()),
                    "metadata": {
                        "contentType": content_type_title,
                        "license": "U",
                        "title": title_str
                    }
                },
                "showContentTitle": False,
                "proceedButtonText": "Weiter",
                "forceContentFinished": True if "CoursePresentation" in library_str else "useBehavioural",
                "feedback": {"title": "", "subtitle": ""},
                "contentBehaviour": "useBehavioural"
            }
            if next_content_id is not None:
                node["nextContentId"] = next_content_id
            return node

        def wrap_in_course_presentation(slides_data, title_str, next_content_id=None):
            slides_list = []
            for slide in slides_data:
                slides_list.append({
                    "elements": [
                        {
                            "x": 3.125,
                            "y": 6.172,
                            "width": 93.75,
                            "height": 87.65,
                            "action": {
                                "library": slide["library"],
                                "params": slide["params"],
                                "subContentId": str(uuid.uuid4()),
                                "metadata": {
                                    "contentType": "Text",
                                    "license": "U",
                                    "title": slide.get("title", "Aufgabe")
                                }
                            },
                            "alwaysDisplayComments": False,
                            "backgroundOpacity": 0,
                            "displayAsButton": False,
                            "invisible": False,
                            "solution": ""
                        }
                    ]
                })
            
            cp_params = {
                "presentation": {
                    "slides": slides_list,
                    "keywordListEnabled": True,
                    "globalBackgroundSelector": {
                        "fillGlobalBackground": ""
                    },
                    "keywordListAlwaysShow": False,
                    "keywordListAutoHide": False,
                    "keywordListOpacity": 90
                },
                "l10n": {
                    "slide": "Folie",
                    "score": "Punktzahl",
                    "yourScore": "Deine Punktzahl",
                    "maxScore": "Maximale Punktzahl",
                    "total": "Summe",
                    "totalScore": "Gesamtpunktzahl",
                    "showSolutions": "Lösungen anzeigen",
                    "retry": "Wiederholen",
                    "exportAnswers": "Text exportieren",
                    "hideKeywords": "Stichwortliste verbergen",
                    "showKeywords": "Stichwortliste anzeigen",
                    "fullscreen": "Vollbild",
                    "exitFullscreen": "Vollbild beenden",
                    "prevSlide": "Vorherige Folie",
                    "nextSlide": "Nächste Folie",
                    "currentSlide": "Aktuelle Folie",
                    "lastSlide": "Letzte Folie",
                    "solutionModeTitle": "Lösungsmodus beenden",
                    "solutionModeText": "Lösungsmodus",
                    "summaryMultipleTaskText": "Mehrere Aufgaben",
                    "scoreMessage": "Du hast erreicht:",
                    "shareFacebook": "Auf Facebook teilen",
                    "shareTwitter": "Auf Twitter teilen",
                    "shareGoogle": "Auf Google+ teilen",
                    "summary": "Zusammenfassung",
                    "solutionsButtonTitle": "Kommentare anzeigen",
                    "printTitle": "Drucken",
                    "printIngress": "Wie möchtest du diese Präsentation drucken?",
                    "printAllSlides": "Alle Folien drucken",
                    "printCurrentSlide": "Aktuelle Folie drucken",
                    "noTitle": "Kein Titel",
                    "accessibilitySlideNavigationExplanation": "Verwende die linke oder rechte Cursortaste, um zur Folie in der jeweiligen Richtung zu blättern, wenn der Präsentationsbereich ausgewählt ist.",
                    "accessibilityCanvasLabel": "Präsentationsbereich. Verwende die linke oder rechte Cursortaste, um zwischen den Folien zu navigieren.",
                    "accessibilityProgressBarLabel": "Wähle das zu zeigende Schaubild",
                    "containsNotCompleted": "@slideName enthält eine nicht abgeschlossene Interaktion",
                    "containsCompleted": "@slideName wurde abgeschlossen",
                    "slideCount": "Folie @index von @total",
                    "containsOnlyCorrect": "@slideName enthält nur richtige Antworten",
                    "containsIncorrectAnswers": "@slideName enthält falsche Antworten",
                    "shareResult": "Ergebnis teilen",
                    "accessibilityTotalScore": "Du hast insgesamt @score von @maxScore Punkten erreicht.",
                    "accessibilityEnteredFullscreen": "Vollbild aktiviert",
                    "accessibilityExitedFullscreen": "Vollbild deaktiviert",
                    "confirmDialogHeader": "Antworten übermitteln",
                    "confirmDialogText": "Damit werden deine Ergebnisse übermittelt. Möchtest du fortfahren?",
                    "confirmDialogConfirmText": "Senden und Ergebnisse ansehen",
                    "slideshowNavigationLabel": "Schaubild-Navigation",
                    "confirmDialogConfirmLabel": "Confirm",
                    "confirmDialogCancelLabel": "Cancel"
                },
                "override": {
                    "activeSurface": False,
                    "hideSummarySlide": False,
                    "showSolutionButton": "",
                    "retryButton": "",
                    "summarySlideSolutionButton": True,
                    "summarySlideRetryButton": True,
                    "enablePrintButton": False,
                    "social": {
                        "showFacebookShare": False,
                        "facebookShare": {
                            "url": "@currentpageurl",
                            "quote": "Ich habe @score von @maxScore Punkten bei der Aufgabe @currentpageurl erreicht."
                        },
                        "showTwitterShare": False,
                        "twitterShare": {
                            "statement": "Ich habe @score von @maxScore Punkten bei der Aufgabe @currentpageurl erreicht.",
                            "url": "@currentpageurl",
                            "hashtags": "h5p, Kurs"
                        },
                        "showGoogleShare": False,
                        "googleShareUrl": "@currentpageurl"
                    }
                }
            }
            node = make_node("H5P.CoursePresentation 1.25", cp_params, "Course Presentation", title_str, next_content_id)
            node["feedback"] = {
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
                                    "library": "H5P.Video 1.5",
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
                        "social": {
                        "showFacebookShare": False,
                        "facebookShare": {
                            "url": "@currentpageurl",
                            "quote": "Ich habe @score von @maxScore Punkten bei der Aufgabe @currentpageurl erreicht."
                        },
                        "showTwitterShare": False,
                        "twitterShare": {
                            "statement": "Ich habe @score von @maxScore Punkten bei der Aufgabe @currentpageurl erreicht.",
                            "url": "@currentpageurl",
                            "hashtags": "h5p, Kurs"
                        },
                        "showGoogleShare": False,
                        "googleShareUrl": "@currentpageurl"
                    }
                    },
                    "l10n": {"startScreenButtonText": "Start", "endScreenButtonText": "Restart", "backButtonText": "Zurück", "disableProceedButtonText": "Bitte warte", "replayButtonText": "Replay", "scoreText": "Score:", "fullscreenAria": "Vollbild"}
                },
                "Video", "Einstiegsvideo", 1
            )
            content_nodes.append(video_node)

        # 1. Build Diagnostic Branching Tree Nodes (BranchingQuestions)
        if num_questions == 2:
            q1 = questions[0]
            correct_idx_1 = q1.get("correct", 0)
            content_nodes.append(make_node(
                "H5P.BranchingQuestion 1.0",
                {
                    "branchingQuestion": {
                        "question": f"<p>{q1.get('question')}</p>\n",
                        "alternatives": [
                            {
                                "text": q1.get("options")[i],
                                "nextContentId": 1 if i == correct_idx_1 else 2,
                                "feedback": {"title": "", "subtitle": ""}
                            } for i in range(len(q1.get("options", [])))
                        ]
                    }
                },
                "Branching Question", "Einstiegsfrage 1"
            ))
            
            q2 = questions[1]
            correct_idx_2 = q2.get("correct", 0)
            content_nodes.append(make_node(
                "H5P.BranchingQuestion 1.0",
                {
                    "branchingQuestion": {
                        "question": f"<p>{q2.get('question')}</p>\n",
                        "alternatives": [
                            {
                                "text": q2.get("options")[i],
                                "nextContentId": level_b_id,
                                "feedback": {"title": "", "subtitle": ""}
                            } for i in range(len(q2.get("options", [])))
                        ]
                    }
                },
                "Branching Question", "Einstiegsfrage 2 (Pfad 1)"
            ))
            
            content_nodes.append(make_node(
                "H5P.BranchingQuestion 1.0",
                {
                    "branchingQuestion": {
                        "question": f"<p>{q2.get('question')}</p>\n",
                        "alternatives": [
                            {
                                "text": q2.get("options")[i],
                                "nextContentId": level_b_id if i == correct_idx_2 else level_a_id,
                                "feedback": {"title": "", "subtitle": ""}
                            } for i in range(len(q2.get("options", [])))
                        ]
                    }
                },
                "Branching Question", "Einstiegsfrage 2 (Pfad 2)"
            ))
            
        elif num_questions >= 3:
            q1 = questions[0]
            correct_idx_1 = q1.get("correct", 0)
            content_nodes.append(make_node(
                "H5P.BranchingQuestion 1.0",
                {
                    "branchingQuestion": {
                        "question": f"<p>{q1.get('question')}</p>\n",
                        "alternatives": [
                            {
                                "text": q1.get("options")[i],
                                "nextContentId": 1 if i == correct_idx_1 else 2,
                                "feedback": {"title": "", "subtitle": ""}
                            } for i in range(len(q1.get("options", [])))
                        ]
                    }
                },
                "Branching Question", "Einstiegsfrage 1"
            ))
            
            q2 = questions[1]
            correct_idx_2 = q2.get("correct", 0)
            content_nodes.append(make_node(
                "H5P.BranchingQuestion 1.0",
                {
                    "branchingQuestion": {
                        "question": f"<p>{q2.get('question')}</p>\n",
                        "alternatives": [
                            {
                                "text": q2.get("options")[i],
                                "nextContentId": 3 if i == correct_idx_2 else 4,
                                "feedback": {"title": "", "subtitle": ""}
                            } for i in range(len(q2.get("options", [])))
                        ]
                    }
                },
                "Branching Question", "Einstiegsfrage 2 (Oben)"
            ))
            
            content_nodes.append(make_node(
                "H5P.BranchingQuestion 1.0",
                {
                    "branchingQuestion": {
                        "question": f"<p>{q2.get('question')}</p>\n",
                        "alternatives": [
                            {
                                "text": q2.get("options")[i],
                                "nextContentId": 4 if i == correct_idx_2 else 5,
                                "feedback": {"title": "", "subtitle": ""}
                            } for i in range(len(q2.get("options", [])))
                        ]
                    }
                },
                "Branching Question", "Einstiegsfrage 2 (Unten)"
            ))
            
            q3 = questions[2]
            correct_idx_3 = q3.get("correct", 0)
            content_nodes.append(make_node(
                "H5P.BranchingQuestion 1.0",
                {
                    "branchingQuestion": {
                        "question": f"<p>{q3.get('question')}</p>\n",
                        "alternatives": [
                            {
                                "text": q3.get("options")[i],
                                "nextContentId": level_b_id,
                                "feedback": {"title": "", "subtitle": ""}
                            } for i in range(len(q3.get("options", [])))
                        ]
                    }
                },
                "Branching Question", "Einstiegsfrage 3 (Stark)"
            ))
            
            content_nodes.append(make_node(
                "H5P.BranchingQuestion 1.0",
                {
                    "branchingQuestion": {
                        "question": f"<p>{q3.get('question')}</p>\n",
                        "alternatives": [
                            {
                                "text": q3.get("options")[i],
                                "nextContentId": level_b_id if i == correct_idx_3 else level_a_id,
                                "feedback": {"title": "", "subtitle": ""}
                            } for i in range(len(q3.get("options", [])))
                        ]
                    }
                },
                "Branching Question", "Einstiegsfrage 3 (Mitte)"
            ))
            
            content_nodes.append(make_node(
                "H5P.BranchingQuestion 1.0",
                {
                    "branchingQuestion": {
                        "question": f"<p>{q3.get('question')}</p>\n",
                        "alternatives": [
                            {
                                "text": q3.get("options")[i],
                                "nextContentId": level_a_id,
                                "feedback": {"title": "", "subtitle": ""}
                            } for i in range(len(q3.get("options", [])))
                        ]
                    }
                },
                "Branching Question", "Einstiegsfrage 3 (Basis)"
            ))
        else:
            q1 = questions[0] if questions else {"question": "Bist du bereit?", "options": ["Ja", "Nein"], "correct": 0}
            correct_idx_1 = q1.get("correct", 0)
            content_nodes.append(make_node(
                "H5P.BranchingQuestion 1.0",
                {
                    "branchingQuestion": {
                        "question": f"<p>{q1.get('question')}</p>\n",
                        "alternatives": [
                            {
                                "text": q1.get("options")[i],
                                "nextContentId": level_b_id if i == correct_idx_1 else level_a_id,
                                "feedback": {"title": "", "subtitle": ""}
                            } for i in range(len(q1.get("options", [])))
                        ]
                    }
                },
                "Branching Question", "Einstiegsfrage 1"
            ))

        # Determine Expert Zone Node ID
        zusatzaufgaben = data.get("zusatzaufgaben", [])
        has_experts = len(zusatzaufgaben) > 0
        expert_node_id = (level_a_id + 1) if has_experts else -1

        # 2. Build Level A and Level B content nodes based on tasks
        for node_id, level_data, node_title in [
            (level_b_id, level_b, "Level B - Vertiefung"),
            (level_a_id, level_a, "Level A - Grundlagen")
        ]:
            tasks = level_data.get("tasks", [])
            if not tasks:
                # Fallback if no tasks list is found
                tasks = [{"title": level_data.get("title", node_title), "text": level_data.get("text", ""), "format": target_format}]
            
            slides_data = []
            
            # Add Slide 1: Merkkasten / Hefteintrag if available
            hefteintrag = data.get("hefteintrag", {})
            notes = hefteintrag.get("level_a_notes" if "Level A" in node_title else "level_b_notes") or hefteintrag.get("summary")
            if notes and notes.strip():
                formatted_notes = notes.replace("\n", "<br/>")
                slides_data.append({
                    "library": "H5P.AdvancedText 1.1",
                    "params": {
                        "text": f"<h3 style='color:#0f766e; margin-top:0;'>📌 Merkkasten / Hefteintrag</h3><div style='background-color:#fef3c7; border-left:4px solid #f59e0b; padding:12px 14px; border-radius:8px; font-size:14px; line-height:1.6; color:#78350f;'>{formatted_notes}</div>"
                    },
                    "title": "📌 Merkkasten / Hefteintrag"
                })
            
            for task in tasks:
                task_format = task.get("format", target_format)
                raw_text = task.get("text", "")
                task_title = task.get("title", node_title)
                
                task_hint = task.get("hint", "").strip()
                task_exp = task.get("explanation", "").strip()
                
                # Format text with embedded gap hint for Level A if hint exists
                formatted_blanks_text = raw_text
                if task_hint:
                    # Replace *word* with *word:hint* if no colon is present
                    formatted_blanks_text = re.sub(r'\*([^*:]+)\*', r'*\1:' + task_hint.replace(':', ' ') + r'*', raw_text)

                overall_fb = [
                    {"from": 0, "to": 99, "feedback": f"💬 Hinweis / Erklärung: {task_exp}" if task_exp else "Überprüfe deine Antworten noch einmal."},
                    {"from": 100, "to": 100, "feedback": "🎉 Hervorragend! Du hast alle Aufgaben richtig gelöst."}
                ]

                if task_format == "Multiple Choice":
                    mc_questions = H5PGenerator.parse_multiple_choice_text(raw_text)
                    first_q = mc_questions[0] if mc_questions else {
                        "question": f"<p>{task_title} Frage</p>\n",
                        "answers": [{"text": "Option 1", "correct": True, "tipsAndFeedback": {"tip": "", "chosenFeedback": "", "notChosenFeedback": ""}}]
                    }
                    if task_exp and first_q.get("answers"):
                        for ans in first_q["answers"]:
                            if not ans.get("correct"):
                                ans["tipsAndFeedback"]["chosenFeedback"] = f"💬 {task_exp}"

                    slides_data.append({
                        "title": task_title,
                        "library": "H5P.MultiChoice 1.16",
                        "params": {
                            "question": first_q.get("question"),
                            "answers": first_q.get("answers"),
                            "overallFeedback": overall_fb,
                            "behaviour": {
                                "enableRetry": True, "enableSolutionsButton": True, "singleAnswer": True, 
                                "singlePoint": True, "randomAnswers": False, "showSolutionsRequiresInput": True, 
                                "confirmCheckDialog": False, "confirmRetryDialog": False, "autoCheck": False, 
                                "passPercentage": 80, "type": "auto"
                            },
                            "UI": {
                                "checkAnswerButton": "Prüfen", "submitAnswerButton": "Absenden", "tryAgainButton": "Wiederholen", 
                                "showSolutionButton": "Lösung anzeigen", "correctText": "Richtig!", "almostText": "Fast!", 
                                "wrongText": "Falsch", "tipsLabel": "Hinweis anzeigen", "scoreBarLabel": "Sie haben :num von :total Punkten erreicht.", 
                                "tipAvailable": "Hinweis verfügbar", "feedbackAvailable": "Feedback verfügbar", "readFeedback": "Feedback lesen", 
                                "wrongAnswer": "Falsche Antwort", "correctAnswer": "Richtige Antwort", "shouldCheck": "Sollte markiert sein", 
                                "shouldNotCheck": "Sollte nicht markiert sein", "noInput": "Bitte antworte, bevor du die Lösung ansiehst", 
                                "feedback": "Du hast @score von @total Punkten erreicht"
                            },
                            "confirmCheck": {"header": "Prüfen ?", "body": "Möchtest du prüfen ?", "cancelLabel": "Abbrechen", "confirmLabel": "Prüfen"},
                            "confirmRetry": {"header": "Wiederholen ?", "body": "Möchtest du es noch einmal versuchen ?", "cancelLabel": "Abbrechen", "confirmLabel": "Ja"}
                        }
                    })
                    
                elif task_format == "Vokabelkarten":
                    cards = H5PGenerator.parse_dialogcards_text(raw_text)
                    # Keine Platzhalter-Karten: ohne echte Karten wird die Folie weggelassen
                    if cards:
                        slides_data.append({
                            "title": task_title,
                            "library": "H5P.Dialogcards 1.9",
                            "params": {
                                "title": task_title,
                                "description": "Präge dir die Begriffe ein.",
                                "dialogs": cards,
                                "behaviour": {"enableRetry": True, "randomise": False, "scaleTextNotCard": False},
                                "progressText": "Karte :num von :total", "next": "Weiter", "prev": "Zurück", 
                                "check": "Prüfen", "gotIt": "Gewusst", "incorrect": "Falsch", "showAnswer": "Antwort anzeigen"
                            }
                        })
                    
                elif task_format == "Drag the Words":
                    drag_text_field = H5PGenerator.clean_slashes_for_drag_text(formatted_blanks_text)
                    slides_data.append({
                        "title": task_title,
                        "library": "H5P.DragText 1.10",
                        "params": {
                            "taskDescription": "Ziehe die passenden Wörter in die Lücken.",
                            "textField": drag_text_field,
                            "overallFeedback": overall_fb,
                            "checkAnswer": "Prüfen", "tryAgain": "Wiederholen", "showSolution": "Lösung anzeigen", 
                            "score": "Du hast @score von @total Lücken richtig ausgefüllt.", "scoreBarLabel": "Punkte",
                            "behaviour": {"enableRetry": True, "enableSolutionsButton": True, "instantFeedback": False, "enableCheckButton": True}
                        }
                    })

                elif task_format == "Wahr/Falsch":
                    tf_statements = H5PGenerator.parse_true_false_text(raw_text)
                    if not tf_statements:
                        tf_statements = [{"question": f"<p>{task_title} Aussage</p>\n", "correct": True}]
                    first_tf = tf_statements[0]
                    slides_data.append({
                        "title": task_title,
                        "library": "H5P.TrueFalse 1.8",
                        "params": {
                            "question": first_tf.get("question"),
                            "correct": "true" if first_tf.get("correct") else "false",
                            "feedback": f"💬 {task_exp}" if task_exp else "",
                            "l10n": {
                                "trueText": "Wahr", "falseText": "Falsch", "score": "Punkte", "checkAnswer": "Prüfen", 
                                "showSolutionButton": "Lösung", "tryAgain": "Wiederholen", "wrongAnswer": "Falsche Antwort", 
                                "correctAnswer": "Richtige Antwort", "feedback": "Du hast @score von @total Punkten erreicht."
                            },
                            "behaviour": {"enableRetry": True, "enableSolutionsButton": True, "enableCheckButton": True, "confirmCheckDialog": False, "confirmRetryDialog": False, "autoCheck": False},
                            "confirmCheck": {"header": "Prüfen ?", "body": "Möchtest du prüfen ?", "cancelLabel": "Abbrechen", "confirmLabel": "Prüfen"},
                            "confirmRetry": {"header": "Wiederholen ?", "body": "Möchtest du es noch einmal versuchen ?", "cancelLabel": "Abbrechen", "confirmLabel": "Ja"}
                        }
                    })

                elif task_format == "Wörter markieren":
                    cleaned_mark_text = H5PGenerator.clean_slashes_for_drag_text(formatted_blanks_text)
                    slides_data.append({
                        "title": task_title,
                        "library": "H5P.MarkTheWords 1.0",
                        "params": {
                            "taskDescription": "Klicke auf die gesuchten (markierten) Wörter im Text.",
                            "textField": cleaned_mark_text,
                            "overallFeedback": overall_fb,
                            "checkAnswerButton": "Prüfen",
                            "tryAgainButton": "Wiederholen",
                            "showSolutionButton": "Lösung anzeigen",
                            "scoreBarLabel": "Du hast @score von @total Wörtern richtig markiert.",
                            "behaviour": {
                                "enableRetry": True,
                                "enableSolutionsButton": True,
                                "enableCheckButton": True,
                                "showScorePoints": True
                            }
                        }
                    })

                else: # Default: Lückentext (H5P.Blanks)
                    slides_data.append({
                        "title": task_title,
                        "library": "H5P.Blanks 1.14",
                        "params": {
                            "text": "Bitte fülle die Lücken im Text aus.",
                            "questions": [f"<p>{formatted_blanks_text}</p>"],
                            "overallFeedback": overall_fb,
                            "title": task_title,
                            "score": "Du hast @score von @total Lücken richtig ausgefüllt.",
                            "showSolutions": "Lösung anzeigen", "tryAgain": "Wiederholen", "checkAnswer": "Prüfen", 
                            "notFilledOut": "Bitte fülle alle Lücken aus.", "answerIsCorrect": "\":ans\" ist richtig", 
                            "answerIsWrong": "\":ans\" ist falsch", "answeredCorrectly": "Richtig beantwortet", 
                            "answeredIncorrectly": "Falsch beantwortet", "solutionLabel": "Richtige Antwort:", 
                            "inputLabel": "Lücke @num von @total", "inputHasTipLabel": "Hinweis verfügbar", "tipLabel": "Hinweis",
                            "behaviour": {"enableRetry": True, "enableSolutionsButton": True, "enableCheckButton": True, "autoCheck": False, "caseSensitive": False, "showSolutionsRequiresInput": True, "separateLines": False, "confirmCheckDialog": False, "confirmRetryDialog": False},
                            "confirmCheck": {"header": "Prüfen ?", "body": "Möchtest du prüfen ?", "cancelLabel": "Abbrechen", "confirmLabel": "Prüfen"},
                            "confirmRetry": {"header": "Wiederholen ?", "body": "Möchtest du es noch einmal versuchen ?", "cancelLabel": "Abbrechen", "confirmLabel": "Ja"}
                        }
                    })

            # Append the completed Course Presentation node for this level, linking to expert_node_id
            content_nodes.append(wrap_in_course_presentation(
                slides_data=slides_data, 
                title_str=node_title, 
                next_content_id=expert_node_id
            ))

        # 3. Append Experten-Zone (Bonus Level) node if present
        if has_experts:
            expert_slides = []
            for z_idx, z in enumerate(zusatzaufgaben):
                z_title = z.get("title", f"Experten-Aufgabe {z_idx+1}")
                z_task = z.get("task", "")
                expert_slides.append({
                    "title": z_title,
                    "library": "H5P.AdvancedText 1.1",
                    "params": {
                        "text": f"<div style='background-color:#eff6ff; border-left:4px solid #3b82f6; padding:15px; border-radius:8px;'><h3 style='color:#1d4ed8; margin-top:0;'>🚀 {z_title}</h3><p style='font-size:16px; color:#1e3a8a; line-height:1.6;'>{z_task}</p></div>"
                    }
                })
            content_nodes.append(wrap_in_course_presentation(
                slides_data=expert_slides,
                title_str="🚀 Experten-Zone (Bonus-Level)",
                next_content_id=-1
            ))

        content_json_data = {
            "branchingScenario": {
                "title": title,
                "content": content_nodes,
                "endScreens": [
                    {
                        "endScreenTitle": "Fertig!",
                        "endScreenSubtitle": "Du hast die Übung erfolgreich abgeschlossen.",
                        "contentId": -1,
                        "endScreenScore": 0
                    }
                ],
                "scoringOptionGroup": {
                    "scoringOption": "no-score",
                    "includeInteractionsScores": True
                },
                "startScreen": {
                    "startScreenTitle": title,
                    "startScreenSubtitle": "Beantworte zuerst die Einstiegsfragen."
                },
                "behaviour": {
                    "enableBackwardsNavigation": False,
                    "forceContentFinished": False,
                    "randomizeBranchingQuestions": False
                },
                "l10n": {
                    "startScreenButtonText": "Kurs starten",
                    "endScreenButtonText": "Kurs neu starten",
                    "backButtonText": "Zurück",
                    "disableProceedButtonText": "Nötig, um das aktuelle Modul abzuschließen",
                    "replayButtonText": "Video wiederholen",
                    "scoreText": "Deine Punktzahl:",
                    "fullscreenAria": "Vollbild"
                }
            }
        }
        return content_json_data

    @staticmethod
    def extract_hefteintrag_point(item, idx, full_hefteintrag=""):
        """
        Extracts a clean, didactic bullet point for this specific step of the growing notebook entry.
        Works dynamically for any number of tasks.
        """
        import re

        # 1. Direct point field
        if item.get("hefteintrag_point") and item["hefteintrag_point"].strip():
            return item["hefteintrag_point"].strip()

        # 2. Extract from full_hefteintrag if it contains numbered items (e.g. "1. ...\n2. ...")
        if full_hefteintrag:
            lines = [line.strip() for line in full_hefteintrag.split("\n") if line.strip()]
            for line in lines:
                m = re.match(rf"^(?:{idx+1}\.|\({idx+1}\)|-\s*|•\s*)(.+)$", line)
                if m:
                    clean = m.group(1).strip()
                    if len(clean) > 5:
                        return clean

        # 3. From hefteintrag_step
        step_str = item.get("hefteintrag_step") or ""
        if step_str:
            matches = re.findall(rf"(?:{idx+1}\.|\({idx+1}\))\s*([^\n]+)", step_str)
            if matches:
                return matches[-1].strip()

        # 4. From Infobox text
        if item.get("text") and item["text"].strip():
            txt = item["text"].strip()
            txt = re.sub(r'^(?:💡\s*)?(?:Merke dir:\s*|Merksatz:\s*)', '', txt, flags=re.IGNORECASE)
            first_sentence = txt.split("\n")[0].strip()
            if len(first_sentence) > 10:
                return first_sentence

        # 5. From explanation
        if item.get("explanation") and item["explanation"].strip():
            exp = item["explanation"].strip()
            cleaned_exp = re.sub(r'^(?:Richtig!\s*|Genau(?:\s+richtig)?!\s*|Sehr gut!\s*|Ausgezeichnet!\s*)', '', exp, flags=re.IGNORECASE)
            cleaned_exp = re.sub(r'^Wie im Video[^,]+,\s*', '', cleaned_exp, flags=re.IGNORECASE)
            if len(cleaned_exp) > 15:
                return cleaned_exp.split("\n")[0].strip()

        # 6. Fallback based on title and question
        title = item.get("title") or f"Kernpunkt {idx+1}"
        q = item.get("question", "").strip()
        return f"{title}: {q[:70]}"

    @staticmethod
    def build_growing_hefteintrag_html(topic_title, all_points, current_idx, is_final=False):
        """
        Renders the progressive digital Tafelbild (growing notebook entry).
        Can be displayed inside question feedback or as a standalone poster.
        """
        import re
        total_count = len(all_points)
        step_num = current_idx + 1

        clean_title = re.sub(r'^(?:🎬|📖|💡|Informatik:\s*|Biologie:\s*|\w+:\s*)', '', topic_title).strip()

        points_html_parts = []
        for i in range(step_num):
            pt_text = all_points[i]
            pt_num = i + 1
            if not is_final and i == current_idx:
                # Newly added point in this step (highlighted!)
                points_html_parts.append(
                    f"<div style='color:#0f172a; font-size:13.5px; font-weight:600; line-height:1.5; margin-bottom:7px; "
                    f"background:#eff6ff; border-left:4px solid #0284c7; padding:7px 10px; border-radius:5px;'>"
                    f"<b>{pt_num}.</b> {pt_text} "
                    f"<span style='background:#0284c7; color:#ffffff; font-size:9.5px; font-weight:800; padding:1px 6px; "
                    f"border-radius:8px; margin-left:6px; vertical-align:middle; text-transform:uppercase;'>Neu ins Heft</span>"
                    f"</div>"
                )
            else:
                # Normal established point
                points_html_parts.append(
                    f"<div style='color:#475569; font-size:13px; line-height:1.45; margin-bottom:6px; padding-left:4px;'>"
                    f"<b>{pt_num}.</b> {pt_text}"
                    f"</div>"
                )

        points_html = "".join(points_html_parts)

        if is_final:
            badge_text = "Gesamttafelbild"
            notebook_task = "✍️ <b>Aufgabe für dein Heft:</b> Vergleiche deinen fertigen Hefteintrag im Schulheft mit diesem vollständigen Tafelbild und hake alle Punkte ab!"
            continue_notice = "▶️ Klicke auf <b>Play ▶</b> oder das <b>✕</b>, um das Video abzuschließen."
        elif step_num == 1:
            badge_text = f"Schritt 1 von {total_count}"
            notebook_task = "✍️ <b>Aufgabe für dein Heft:</b> Schreibe Datum, Thema und <b>Punkt 1</b> jetzt sauber in dein Schulheft!"
            continue_notice = "▶️ Sobald du fertig geschrieben hast: Klicke unten auf <b>„Video fortsetzen“</b> oder Play ▶!"
        elif step_num == total_count:
            badge_text = f"Schritt {step_num} von {total_count}"
            notebook_task = f"✍️ <b>Aufgabe für dein Heft:</b> Ergänze den letzten <b>Punkt {step_num}</b> jetzt sauber in deinem Schulheft!"
            continue_notice = "▶️ Sobald du fertig geschrieben hast: Klicke unten auf <b>„Video fortsetzen“</b> oder Play ▶!"
        else:
            badge_text = f"Schritt {step_num} von {total_count}"
            notebook_task = f"✍️ <b>Aufgabe für dein Heft:</b> Ergänze <b>Punkt {step_num}</b> jetzt sauber in deinem Schulheft!"
            continue_notice = "▶️ Sobald du fertig geschrieben hast: Klicke unten auf <b>„Video fortsetzen“</b> oder Play ▶!"

        return (
            f"<div style='background:#ffffff; border:2px solid #0284c7; border-radius:12px; padding:14px; margin-top:8px; "
            f"font-family:sans-serif; box-shadow:0 6px 18px rgba(0,0,0,0.08); text-align:left;'>"
            f"<div style='display:flex; align-items:center; justify-content:space-between; border-bottom:2px solid #e0f2fe; padding-bottom:6px; margin-bottom:10px;'>"
            f"<div style='display:flex; align-items:center; gap:6px;'>"
            f"<span style='font-size:18px;'>📖</span>"
            f"<span style='font-size:14px; font-weight:800; color:#0369a1; text-transform:uppercase; letter-spacing:0.5px;'>Wachsender Hefteintrag</span>"
            f"</div>"
            f"<span style='background:#e0f2fe; color:#0369a1; font-size:11px; font-weight:700; padding:3px 8px; border-radius:10px;'>{badge_text}</span>"
            f"</div>"
            f"<div style='color:#0f172a; font-size:14.5px; font-weight:800; margin:0 0 8px 0;'>Thema: {clean_title}</div>"
            f"<div style='background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:10px 12px; margin-bottom:10px;'>"
            f"{points_html}"
            f"</div>"
            f"<div style='background:#fef3c7; border-left:4px solid #f59e0b; padding:8px 12px; border-radius:6px; margin-bottom:10px; color:#92400e; font-size:13px; font-weight:700; line-height:1.4;'>"
            f"{notebook_task}"
            f"</div>"
            f"<div style='padding-top:8px; border-top:1px dashed #cbd5e1; font-size:11.5px; color:#64748b; font-weight:600;'>"
            f"{continue_notice}"
            f"</div>"
            f"</div>"
        )

    @staticmethod
    def create_interactive_video_h5p_zip(data):
        title = data.get("title", "Interaktives Video")
        video_filename = data.get("video_filename")
        youtube_url = data.get("youtube_url")

        # 1. Sources
        if video_filename:
            files_source = [{
                "path": f"videos/{video_filename}",
                "mime": "video/mp4",
                "copyright": {"license": "U"}
            }]
        elif youtube_url:
            files_source = [{
                "path": youtube_url,
                "mime": "video/YouTube",
                "copyright": {"license": "U"}
            }]
        else:
            files_source = []

        # 2. Build interactions & digital growing Hefteintrag
        interactions_list = []
        bookmarks_list = []
        used_libraries = set()

        raw_interactions = data.get("interactions", [])
        total_count = len(raw_interactions)
        full_hefteintrag = data.get("full_hefteintrag") or ""

        # Pre-extract all points for the progressive Hefteintrag (independent of task count)
        all_points = [
            H5PGenerator.extract_hefteintrag_point(it, i, full_hefteintrag)
            for i, it in enumerate(raw_interactions)
        ]

        for idx, item in enumerate(raw_interactions):
            t_sec = int(item.get("time_seconds", 30 * (idx + 1)))
            label = item.get("title", f"Haltepunkt {idx + 1}")
            fmt = item.get("format", "Multiple Choice")
            sub_id = str(uuid.uuid4())
            hefteintrag_html = H5PGenerator.build_growing_hefteintrag_html(title, all_points, idx)
            explanation_text = (item.get("explanation") or "").strip()

            # Duration from == to guarantees pop-up disappears immediately on resume!
            interaction_obj = {
                "x": 10,
                "y": 8,
                "width": 80,
                "height": 84,
                "duration": {
                    "from": t_sec,
                    "to": t_sec
                },
                "pause": True,
                "displayType": "poster",
                "buttonOnMobile": False,
                "label": label,
                "visuals": {
                    "backgroundColor": "rgba(255, 255, 255, 0.98)",
                    "boxShadow": True
                }
            }

            if fmt == "Multiple Choice":
                used_libraries.add("H5P.MultiChoice")
                # Growing Hefteintrag embedded directly in feedback on correct answer!
                # Zero video playback between correct answer and Hefteintrag.
                if explanation_text:
                    feedback_content = f"<div style='font-size:14px; font-weight:600; color:#15803d; margin-bottom:10px;'>Klasse! {explanation_text}</div>{hefteintrag_html}"
                else:
                    feedback_content = f"<div style='font-size:14px; font-weight:600; color:#15803d; margin-bottom:10px;'>Klasse! Das ist vollkommen richtig!</div>{hefteintrag_html}"

                answers = []
                for ans in item.get("answers", []):
                    is_ans_correct = bool(ans.get("correct", False))
                    answers.append({
                        "text": f"<div>{ans.get('text', '')}</div>\n",
                        "correct": is_ans_correct,
                        "tipsAndFeedback": {
                            "tip": "",
                            "chosenFeedback": feedback_content if is_ans_correct else "",
                            "notChosenFeedback": ""
                        }
                    })
                interaction_obj["action"] = {
                    "library": "H5P.MultiChoice 1.16",
                    "params": {
                        "question": f"<p>{item.get('question', '')}</p>\n",
                        "answers": answers,
                        "behaviour": {
                            "enableRetry": True,
                            "enableSolutionsButton": True,
                            "singlePoint": True,
                            "randomAnswers": True,
                            "showSolutionsRequiresInput": True,
                            "type": "auto",
                            "confirmCheckDialog": False,
                            "confirmRetryDialog": False,
                            "autoCheck": False,
                            "passPercentage": 80,
                            "showScorePoints": True
                        },
                        "UI": {
                            "checkAnswerButton": "Prüfen",
                            "showSolutionButton": "Lösung anzeigen",
                            "tryAgainButton": "Wiederholen",
                            "tipsLabel": "Hinweis anzeigen",
                            "scoreBarLabel": "Sie haben :num von :total Punkten erreicht."
                        }
                    },
                    "subContentId": sub_id,
                    "metadata": {
                        "contentType": "Multiple Choice",
                        "license": "U",
                        "title": label
                    }
                }
            elif fmt in ["Wahr/Falsch", "Wahr / Falsch"]:
                used_libraries.add("H5P.TrueFalse")
                is_correct = str(item.get("correct", "true")).lower() in ["true", "wahr", "1"]
                if explanation_text:
                    feedback_content = f"<div style='font-size:14px; font-weight:600; color:#15803d; margin-bottom:10px;'>Klasse! {explanation_text}</div>{hefteintrag_html}"
                else:
                    feedback_content = f"<div style='font-size:14px; font-weight:600; color:#15803d; margin-bottom:10px;'>Klasse! Das ist vollkommen richtig!</div>{hefteintrag_html}"

                interaction_obj["action"] = {
                    "library": "H5P.TrueFalse 1.8",
                    "params": {
                        "question": f"<p>{item.get('question', '')}</p>\n",
                        "correct": "true" if is_correct else "false",
                        "l10n": {
                            "trueText": "Wahr",
                            "falseText": "Falsch",
                            "feedback": feedback_content
                        },
                        "behaviour": {
                            "enableRetry": True,
                            "enableSolutionsButton": True,
                            "confirmCheckDialog": False,
                            "confirmRetryDialog": False
                        }
                    },
                    "subContentId": sub_id,
                    "metadata": {
                        "contentType": "True/False",
                        "license": "U",
                        "title": label
                    }
                }
            elif fmt in ["Lückentext", "Lueckentext"]:
                used_libraries.add("H5P.Blanks")
                text_with_blanks = item.get("text_with_blanks", item.get("question", ""))
                formatted_blanks = H5PGenerator.format_blanks_text(text_with_blanks) if hasattr(H5PGenerator, "format_blanks_text") else text_with_blanks
                if explanation_text:
                    feedback_content = f"<div style='font-size:14px; font-weight:600; color:#15803d; margin-bottom:10px;'>Klasse! {explanation_text}</div>{hefteintrag_html}"
                else:
                    feedback_content = f"<div style='font-size:14px; font-weight:600; color:#15803d; margin-bottom:10px;'>Klasse! Das ist vollkommen richtig!</div>{hefteintrag_html}"

                interaction_obj["action"] = {
                    "library": "H5P.Blanks 1.14",
                    "params": {
                        "text": f"<p>{item.get('question', 'Fülle die Lücken aus:')}</p>",
                        "questions": [f"<p>{formatted_blanks}</p>"],
                        "score": "Du hast @score von @total Punkten erreicht.",
                        "overallFeedback": [
                            {
                                "from": 100,
                                "to": 100,
                                "feedback": feedback_content
                            }
                        ],
                        "checkAnswer": "Prüfen",
                        "tryAgain": "Wiederholen",
                        "showSolution": "Lösung anzeigen",
                        "behaviour": {
                            "enableRetry": True,
                            "enableSolutionsButton": True,
                            "autoCheck": False,
                            "caseSensitive": False,
                            "showSolutionsRequiresInput": True,
                            "separateLines": False
                        }
                    },
                    "subContentId": sub_id,
                    "metadata": {
                        "contentType": "Fill in the Blanks",
                        "license": "U",
                        "title": label
                    }
                }
            else:
                # Infobox (Merkkasten) -> Renders the progressive Tafelbild directly!
                used_libraries.add("H5P.Text")
                interaction_obj["action"] = {
                    "library": "H5P.Text 1.1",
                    "params": {
                        "text": hefteintrag_html
                    },
                    "subContentId": sub_id,
                    "metadata": {
                        "contentType": "Text",
                        "license": "U",
                        "title": f"📖 Hefteintrag {idx+1}"
                    }
                }

            # Adaptivity & Rewind: strictly capped to max 30 seconds rewind
            raw_rewind = int(item.get("rewind_seconds") or item.get("explanation_start_seconds") or (t_sec - 15))
            rewind_sec = max(t_sec - 30, raw_rewind)
            rewind_sec = min(rewind_sec, max(0, t_sec - 5))

            if fmt in ["Multiple Choice", "Wahr/Falsch", "Wahr / Falsch", "Lückentext", "Lueckentext"]:
                bookmarks_list.append({
                    "time": t_sec,
                    "label": f"❓ Frage {idx+1}: {label}"
                })
                interaction_obj["adaptivity"] = {
                    "wrong": {
                        "seekTo": rewind_sec,
                        "allowOptOut": True,
                        "message": "<div>Das war leider noch nicht ganz richtig. Schau dir die Erklärung im Video noch einmal genau an!</div>",
                        "seekLabel": "Zurück zur Erklärung"
                    },
                    "requireCompletion": True
                }
            else:
                bookmarks_list.append({
                    "time": t_sec,
                    "label": f"📖 Hefteintrag {idx+1}: {label}"
                })

            interactions_list.append(interaction_obj)

        # Final Summary Poster: Complete Tafelbild for all points
        if total_count >= 2:
            last_t = max(int(it.get("time_seconds", 30)) for it in raw_interactions)
            final_time = last_t + 8
            final_poster_html = H5PGenerator.build_growing_hefteintrag_html(title, all_points, len(all_points) - 1, is_final=True)
            final_id = str(uuid.uuid4())
            used_libraries.add("H5P.Text")
            final_obj = {
                "x": 10,
                "y": 8,
                "width": 80,
                "height": 84,
                "duration": {
                    "from": final_time,
                    "to": final_time
                },
                "pause": True,
                "displayType": "poster",
                "buttonOnMobile": False,
                "label": "📖 Vollständiges Tafelbild",
                "visuals": {
                    "backgroundColor": "rgba(255, 255, 255, 0.98)",
                    "boxShadow": True
                },
                "action": {
                    "library": "H5P.Text 1.1",
                    "params": {
                        "text": final_poster_html
                    },
                    "subContentId": final_id,
                    "metadata": {
                        "contentType": "Text",
                        "license": "U",
                        "title": "📖 Vollständiger Hefteintrag"
                    }
                }
            }
            interactions_list.append(final_obj)
            bookmarks_list.append({
                "time": final_time,
                "label": "📖 Vollständiges Tafelbild"
            })

        # Ensure bookmarks and interactions are sorted strictly by time
        bookmarks_list.sort(key=lambda b: b["time"])
        interactions_list.sort(key=lambda it: it["duration"]["from"])

        # 3. Build content.json
        content_json = {
            "interactiveVideo": {
                "video": {
                    "files": files_source,
                    "startScreenOptions": {
                        "title": title,
                        "hideStartTitle": False
                    }
                },
                "assets": {
                    "interactions": interactions_list,
                    "bookmarks": bookmarks_list
                },
                "summary": {
                    "task": {
                        "library": "H5P.Summary 1.10",
                        "params": {
                            "intro": "Wähle die richtige Aussage:",
                            "summaries": []
                        },
                        "subContentId": str(uuid.uuid4())
                    },
                    "displayAt": 3
                }
            },
            "override": {
                "showBookmarksmenuOnLoad": False,
                "showRewind10": True,
                "preventSkipping": True,
                "deactivateSound": False
            },
            "l10n": {
                "interaction": "Interaktion",
                "play": "Abspielen",
                "pause": "Pausieren",
                "mute": "Stummschalten",
                "unmute": "Ton an",
                "quality": "Videoqualität",
                "captions": "Untertitel",
                "close": "Schließen",
                "fullscreen": "Vollbild",
                "exitFullscreen": "Vollbild beenden",
                "summary": "Zusammenfassung",
                "bookmarks": "Lesezeichen",
                "defaultAdaptivitySeekLabel": "Fortfahren",
                "continueWithVideo": "Video fortsetzen",
                "more": "Mehr",
                "playbackRate": "Wiedergabegeschwindigkeit",
                "rewind10": "10 Sekunden zurückspringen",
                "navDisabled": "Navigation ist deaktiviert",
                "requiresCompletionWarning": "Du musst alle Fragen beantworten, bevor du weitermachst."
            }
        }

        # 4. Build dependencies
        dependencies = [
            {"machineName": "FontAwesome", "majorVersion": 4, "minorVersion": 5},
            {"machineName": "jQuery.ui", "majorVersion": 1, "minorVersion": 10},
            {"machineName": "H5P.DragNBar", "majorVersion": 1, "minorVersion": 5},
            {"machineName": "H5P.Components", "majorVersion": 1, "minorVersion": 0},
            {"machineName": "H5P.InteractiveVideo", "majorVersion": 1, "minorVersion": 22},
            {"machineName": "H5P.Video", "majorVersion": 1, "minorVersion": 6},
            {"machineName": "H5P.Summary", "majorVersion": 1, "minorVersion": 10}
        ]

        lib_map = {
            "H5P.MultiChoice": {"machineName": "H5P.MultiChoice", "majorVersion": 1, "minorVersion": 16},
            "H5P.TrueFalse": {"machineName": "H5P.TrueFalse", "majorVersion": 1, "minorVersion": 8},
            "H5P.Blanks": {"machineName": "H5P.Blanks", "majorVersion": 1, "minorVersion": 14},
            "H5P.Text": {"machineName": "H5P.Text", "majorVersion": 1, "minorVersion": 1}
        }
        for lib_name in used_libraries:
            if lib_name in lib_map and lib_map[lib_name] not in dependencies:
                dependencies.append(lib_map[lib_name])

        h5p_json = {
            "title": title,
            "language": "de",
            "mainLibrary": "H5P.InteractiveVideo",
            "embedTypes": ["div"],
            "license": "U",
            "defaultLanguage": "de",
            "preloadedDependencies": dependencies
        }

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr("h5p.json", json.dumps(h5p_json, indent=2, ensure_ascii=False))
            zip_file.writestr("content/content.json", json.dumps(content_json, indent=2, ensure_ascii=False))
            if "video_bytes" in data and "video_filename" in data:
                zip_file.writestr(f"content/videos/{data['video_filename']}", data["video_bytes"])

        zip_buffer.seek(0)
        return zip_buffer.getvalue()

    @staticmethod
    def create_h5p_zip(data):
        if data.get("video_mode") == "interactive_video" or data.get("is_interactive_video"):
            return H5PGenerator.create_interactive_video_h5p_zip(data)

        title = data.get("title", "Differenzierte Übung")
        target_format = data.get("target_format", "Lückentext")
        
        # 1. Generate content/content.json
        content_json = H5PGenerator.create_content_json(data)
        
        # 2. Determine and generate h5p.json preloadedDependencies based on actual formats used
        dependencies = [
            {"machineName": "H5P.BranchingQuestion", "majorVersion": 1, "minorVersion": 0},
            {"machineName": "FontAwesome", "majorVersion": 4, "minorVersion": 5},
            {"machineName": "H5P.BranchingScenario", "majorVersion": 1, "minorVersion": 8},
            {"machineName": "H5P.CoursePresentation", "majorVersion": 1, "minorVersion": 25},
            {"machineName": "H5P.AdvancedText", "majorVersion": 1, "minorVersion": 1}
        ]
        
        if data.get("youtube_url") or data.get("video_filename"):
            dependencies.append({"machineName": "H5P.Video", "majorVersion": 1, "minorVersion": 5})
        
        # Collect all formats actually used in the tasks
        used_formats = set()
        for level in ["level_a", "level_b"]:
            for task in data.get(level, {}).get("tasks", []):
                used_formats.add(task.get("format", target_format))
                
        # Also consider target_format in case it's specifically required
        used_formats.add(target_format)
        
        # Mapping of format names to H5P library dependencies
        library_map = {
            "Multiple Choice": {"machineName": "H5P.MultiChoice", "majorVersion": 1, "minorVersion": 16},
            "Vokabelkarten": {"machineName": "H5P.Dialogcards", "majorVersion": 1, "minorVersion": 9},
            "Drag the Words": {"machineName": "H5P.DragText", "majorVersion": 1, "minorVersion": 10},
            "Wahr/Falsch": {"machineName": "H5P.TrueFalse", "majorVersion": 1, "minorVersion": 8},
            "Wörter markieren": {"machineName": "H5P.MarkTheWords", "majorVersion": 1, "minorVersion": 0},
            "Lückentext": {"machineName": "H5P.Blanks", "majorVersion": 1, "minorVersion": 14}
        }
        
        for fmt in used_formats:
            if fmt in library_map:
                if library_map[fmt] not in dependencies:
                    dependencies.append(library_map[fmt])
            elif fmt == "KI-Mix":
                # For KI-Mix fallback, include all just to be safe
                for lib in library_map.values():
                    if lib not in dependencies:
                        dependencies.append(lib)
                        
        # Ensure H5P.Blanks is always included because expert tasks (Zusatzaufgaben) 
        # and fallbacks always use it.
        if library_map["Lückentext"] not in dependencies:
            dependencies.append(library_map["Lückentext"])
            
        h5p_json = {
            "title": title,
            "language": "und",
            "mainLibrary": "H5P.BranchingScenario",
            "embedTypes": ["div"],
            "license": "U",
            "defaultLanguage": "de",
            "preloadedDependencies": dependencies
        }

        # Create zip in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr("h5p.json", json.dumps(h5p_json, indent=2, ensure_ascii=False))
            zip_file.writestr("content/content.json", json.dumps(content_json, indent=2, ensure_ascii=False))
            
            if "video_bytes" in data and "video_filename" in data:
                zip_file.writestr(f"content/videos/{data['video_filename']}", data["video_bytes"])
            
        zip_buffer.seek(0)
        return zip_buffer.getvalue()
