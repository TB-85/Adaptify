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
                    "answer": back,
                    "image": None,
                    "audio": None
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
        if num_questions == 2:
            level_b_id = 3
            level_a_id = 4
        elif num_questions >= 3:
            level_b_id = 6
            level_a_id = 7
        else:
            level_b_id = 1
            level_a_id = 2

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
                "feedback": {},
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
                                "feedback": {}
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
                                "feedback": {}
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
                                "feedback": {}
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
                                "feedback": {}
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
                                "feedback": {}
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
                                "feedback": {}
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
                                "feedback": {}
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
                                "feedback": {}
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
                                "feedback": {}
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
                                "feedback": {}
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
                                "passPercentage": 100, "type": "auto"
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
                    if not cards:
                        cards = [{"text": "Front", "answer": "Back", "image": None, "audio": None}]
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
                    "library": "H5P.Blanks 1.14",
                    "params": {
                        "text": f"<b>🚀 {z_title}</b><br/>{z_task}",
                        "questions": [f"<p>Schreibe hier deine Idee/Lösung: *Lösung*</p>"],
                        "title": z_title,
                        "score": "Punkte",
                        "showSolutions": "Lösung anzeigen", "tryAgain": "Wiederholen", "checkAnswer": "Prüfen",
                        "notFilledOut": "Bitte fülle das Feld aus.", "answerIsCorrect": "Richtig", "answerIsWrong": "Falsch",
                        "solutionLabel": "Musterlösung:", "inputLabel": "Lösung", "inputHasTipLabel": "Hinweis", "tipLabel": "Hinweis",
                        "behaviour": {"enableRetry": True, "enableSolutionsButton": True, "enableCheckButton": True, "autoCheck": False, "caseSensitive": False, "showSolutionsRequiresInput": False, "separateLines": False, "confirmCheckDialog": False, "confirmRetryDialog": False},
                        "confirmCheck": {"header": "Prüfen ?", "body": "Prüfen ?", "cancelLabel": "Abbrechen", "confirmLabel": "Prüfen"},
                        "confirmRetry": {"header": "Wiederholen ?", "body": "Wiederholen ?", "cancelLabel": "Abbrechen", "confirmLabel": "Ja"}
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
    def create_h5p_zip(data):
        title = data.get("title", "Differenzierte Übung")
        target_format = data.get("target_format", "Lückentext")
        
        # 1. Generate content/content.json
        content_json = H5PGenerator.create_content_json(data)
        
        # 2. Determine and generate h5p.json preloadedDependencies based on actual formats used
        dependencies = [
            {"machineName": "H5P.BranchingQuestion", "majorVersion": "1", "minorVersion": "0"},
            {"machineName": "FontAwesome", "majorVersion": "4", "minorVersion": "5"},
            {"machineName": "H5P.BranchingScenario", "majorVersion": "1", "minorVersion": "8"},
            {"machineName": "H5P.CoursePresentation", "majorVersion": "1", "minorVersion": "25"},
            {"machineName": "H5P.AdvancedText", "majorVersion": "1", "minorVersion": "1"}
        ]
        
        # Collect all formats actually used in the tasks
        used_formats = set()
        for level in ["level_a", "level_b"]:
            for task in data.get(level, {}).get("tasks", []):
                used_formats.add(task.get("format", target_format))
                
        # Also consider target_format in case it's specifically required
        used_formats.add(target_format)
        
        # Mapping of format names to H5P library dependencies
        library_map = {
            "Multiple Choice": {"machineName": "H5P.MultiChoice", "majorVersion": "1", "minorVersion": "16"},
            "Vokabelkarten": {"machineName": "H5P.Dialogcards", "majorVersion": "1", "minorVersion": "9"},
            "Drag the Words": {"machineName": "H5P.DragText", "majorVersion": "1", "minorVersion": "10"},
            "Wahr/Falsch": {"machineName": "H5P.TrueFalse", "majorVersion": "1", "minorVersion": "8"},
            "Wörter markieren": {"machineName": "H5P.MarkTheWords", "majorVersion": "1", "minorVersion": "0"},
            "Lückentext": {"machineName": "H5P.Blanks", "majorVersion": "1", "minorVersion": "14"}
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
            else:
                # Default fallback for unknown formats
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
            
        zip_buffer.seek(0)
        return zip_buffer.getvalue()
