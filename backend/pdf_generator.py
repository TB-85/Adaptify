import re
import io
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Flowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch

class RotatedFlowable(Flowable):
    def __init__(self, flowable, angle=180):
        Flowable.__init__(self)
        self.flowable = flowable
        self.angle = angle

    def wrap(self, availWidth, availHeight):
        self.width, self.height = self.flowable.wrap(availWidth, availHeight)
        return self.width, self.height

    def draw(self):
        self.canv.saveState()
        if self.angle == 180:
            self.canv.translate(self.width, self.height)
            self.canv.rotate(180)
        self.flowable.drawOn(self.canv, 0, 0)
        self.canv.restoreState()

from h5p_generator import H5PGenerator

class PDFGenerator:
    @staticmethod
    def parse_blanks_for_student(text):
        def repl(match):
            return "______________________"
        clean_text = text.replace("&nbsp;", " ").replace("&nbsp", " ").replace("<u>", "").replace("</u>", "")
        return re.sub(r"\*([^*]+)\*", repl, clean_text).replace("\n", "<br/>")

    @staticmethod
    def parse_blanks_for_teacher(text):
        def repl(match):
            word = match.group(1)
            return f'<b><font color="#1b5e20">{word}</font></b>'
        clean_text = text.replace("&nbsp;", " ").replace("&nbsp", " ").replace("<u>", "").replace("</u>", "")
        return re.sub(r"\*([^*]+)\*", repl, clean_text).replace("\n", "<br/>")

    @staticmethod
    def generate_level_content_elements(raw_text, target_format, is_teacher, styles, body_style):
        story_elements = []
        
        # Auto-detect Vokabelkarten / Dialogcards if Vorderseite/Rückseite present or format is Vokabelkarten
        if "vorderseite:" in raw_text.lower() or "rückseite:" in raw_text.lower() or target_format == "Vokabelkarten":
            cards = H5PGenerator.parse_dialogcards_text(raw_text)
            if cards:
                for c in cards:
                    clean_q = re.sub('<[^<]+?>', '', c.get("text", "")).replace("&nbsp;", " ").replace("&nbsp", " ").strip()
                    clean_a = re.sub('<[^<]+?>', '', c.get("answer", "")).replace("&nbsp;", " ").replace("&nbsp", " ").strip()
                    
                    story_elements.append(Paragraph(f"<b>Begriff / Vokabel:</b> {clean_q}", body_style))
                    if is_teacher:
                        story_elements.append(Paragraph(f"<b>Lösung / Bedeutung:</b> <font color='#1b5e20'>{clean_a}</font>", body_style))
                    else:
                        story_elements.append(Paragraph("<b>Bedeutung:</b> __________________________________________________", body_style))
                    story_elements.append(Spacer(1, 4))
                story_elements.append(Spacer(1, 4))
                return story_elements

        if target_format == "Multiple Choice":
            mc_questions = H5PGenerator.parse_multiple_choice_text(raw_text)
            for q in mc_questions:
                q_clean = re.sub('<[^<]+?>', '', q["question"]) # strip p tags
                story_elements.append(Paragraph(f"<b>Frage:</b> {q_clean}", body_style))
                
                for ans in q["answers"]:
                    ans_text = re.sub('<[^<]+?>', '', ans["text"]) # strip div tags
                    if is_teacher and ans["correct"]:
                        box = "<b>[X] <font color='#1b5e20'>"
                        end_box = "</font></b>"
                    else:
                        box = "[ &nbsp; ] "
                        end_box = ""
                    story_elements.append(Paragraph(f"{box}{ans_text}{end_box}", body_style))
                story_elements.append(Spacer(1, 4))
                
        elif target_format == "Wörter markieren":
            if is_teacher:
                parsed_text = PDFGenerator.parse_blanks_for_teacher(raw_text)
            else:
                parsed_text = re.sub(r"\*([^*]+)\*", r"\1", raw_text).replace("\n", "<br/>")
            story_elements.append(Paragraph(parsed_text, body_style))
            
        else: # Lückentext
            parsed_text = PDFGenerator.parse_blanks_for_teacher(raw_text) if is_teacher else PDFGenerator.parse_blanks_for_student(raw_text)
            story_elements.append(Paragraph(parsed_text, body_style))
            
        return story_elements

    @staticmethod
    def generate_worksheet_pdf(data: dict) -> bytes:
        raw_title = data.get("title", "Differenzierte Übung")
        if ":" in raw_title:
            raw_title = raw_title.split(":", 1)[-1].strip()
        elif " - " in raw_title:
            raw_title = raw_title.split(" - ", 1)[-1].strip()

        # Clean any raw count numbers or topic strings from title
        clean_title = re.sub(r'\d+\s*x?\s*(?:zu|für)?\s*', '', raw_title).strip()
        clean_title = re.sub(r'^\s*,\s*|\s*,\s*$', '', clean_title)
        if not clean_title or len(clean_title) < 3 or ("Textverständnis" in clean_title and "Fremdwörter" in clean_title):
            clean_title = "Müll im Ozean - Der achte Kontinent"
        title = clean_title

        target_format = data.get("target_format", "Lückentext")
        questions = data.get("diagnostic", {}).get("questions", [])
        level_a = data.get("level_a", {})
        level_b = data.get("level_b", {})

        # Get customization parameters
        class_name = data.get("pdf_class_name", "")
        teacher_name = data.get("pdf_teacher_name", "")
        accent_color_hex = data.get("pdf_accent_color", "#0f172a")
        accent_color = colors.HexColor(accent_color_hex)

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=inch*0.4,
            leftMargin=inch*0.4,
            topMargin=inch*0.4,
            bottomMargin=inch*0.4
        )

        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'PremiumTitle',
            parent=styles['Title'],
            fontName='Helvetica-Bold',
            fontSize=18,
            leading=22,
            textColor=accent_color,
            alignment=0,
            spaceAfter=6
        )
        
        section_style = ParagraphStyle(
            'PremiumSection',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=13,
            leading=17,
            textColor=accent_color,
            spaceBefore=12,
            spaceAfter=6,
            keepWithNext=True
        )

        body_style = ParagraphStyle(
            'PremiumBody',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#334155"),
            spaceAfter=8
        )

        hint_style = ParagraphStyle(
            'PremiumHint',
            parent=styles['Italic'],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#64748b")
        )

        # Build Logo image if provided
        logo_img = None
        logo_data = data.get("pdf_logo_base64")
        logo_io = None
        if logo_data:
            try:
                import base64
                if "," in logo_data:
                    logo_data = logo_data.split(",", 1)[1]
                logo_bytes = base64.b64decode(logo_data)
                logo_io = io.BytesIO(logo_bytes)
                from reportlab.platypus import Image
                logo_img = Image(logo_io, width=1.0*inch, height=0.55*inch)
                logo_img.hAlign = 'RIGHT'
            except Exception:
                pass
        
        # Build QR-Code for Student Self-Check Solution
        solution_url = data.get("solution_url")
        if not solution_url or not str(solution_url).strip():
            pin_code = data.get("session_pin") or data.get("pin") or "DEMO123"
            solution_url = f"http://localhost:8080/play.html?pin={pin_code}"

        qr_card = None
        try:
            from reportlab.graphics.shapes import Drawing
            from reportlab.graphics.barcode.qr import QrCodeWidget
            
            qr_w = QrCodeWidget(solution_url)
            qr_w.barWidth = 48
            qr_w.barHeight = 48
            qr_w.qrVersion = 1
            
            qr_draw = Drawing(48, 48)
            qr_draw.add(qr_w)
            
            qr_title_style = ParagraphStyle(
                'QRTitleStyle',
                fontName='Helvetica-Bold',
                fontSize=6.5,
                leading=8,
                textColor=colors.HexColor("#0f172a"),
                alignment=1
            )
            qr_sub_style = ParagraphStyle(
                'QRSubStyle',
                fontName='Helvetica',
                fontSize=5.5,
                leading=7,
                textColor=colors.HexColor("#334155"),
                alignment=1
            )
            
            qr_card = Table([
                [qr_draw],
                [Paragraph("📱 <b>Lösungs-QR</b>", qr_title_style)],
                [Paragraph("Selbstkontrolle", qr_sub_style)]
            ], colWidths=[inch*1.1])
            qr_card.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BOX', (0,0), (-1,-1), 1.2, colors.HexColor("#0f172a")),
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
                ('TOPPADDING', (0,0), (-1,-1), 2),
                ('BOTTOMPADDING', (0,0), (-1,-1), 3),
                ('LEFTPADDING', (0,0), (-1,-1), 2),
                ('RIGHTPADDING', (0,0), (-1,-1), 2),
            ]))
        except Exception as qr_err:
            pass

        # Calculate School Year
        import datetime
        now = datetime.datetime.now()
        year = now.year
        month = now.month
        if month >= 8:
            school_year = f"Schuljahr {year}/{str(year+1)[2:]}"
        else:
            school_year = f"Schuljahr {year-1}/{str(year)[2:]}"

        # Left Column Table for Header
        left_details = []
        left_details.append("<b>Name:</b> ___________________________")
        
        row_fields = []
        if class_name:
            row_fields.append(f"<b>Klasse:</b> {class_name}")
        if teacher_name:
            row_fields.append(f"<b>Lehrkraft:</b> {teacher_name}")
            
        if row_fields:
            left_details.append(" &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; ".join(row_fields))
            
        include_lehrplan = data.get("pdf_include_lehrplan", False)
        lehrplan_code = data.get("lehrplan_code", "")
        if include_lehrplan and lehrplan_code:
            left_details.append(f"<i><font color='#4f46e5'>📌 LehrplanPlus: {lehrplan_code}</font></i>")

        left_paragraphs = [Paragraph(detail, body_style) for detail in left_details]
        left_table = Table([[p] for p in left_paragraphs], colWidths=[inch*4.6])
        left_table.setStyle(TableStyle([
            ('BOTTOMPADDING', (0,0), (-1,-1), 1),
            ('TOPPADDING', (0,0), (-1,-1), 1),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ]))

        # Right Column Flowable containing Logo (optional) and School Year
        right_flow = []
        if logo_img:
            right_flow.append([logo_img])
        
        school_year_style = ParagraphStyle(
            'SchoolYearStyle',
            parent=body_style,
            fontName='Helvetica-Oblique',
            fontSize=7.5,
            leading=9,
            textColor=colors.HexColor("#475569"),
            alignment=2 # Right aligned
        )
        right_flow.append([Paragraph(school_year, school_year_style)])
        
        right_table = Table(right_flow, colWidths=[inch*1.6])
        right_table.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'RIGHT'),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 1),
            ('TOPPADDING', (0,0), (-1,-1), 1),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ]))

        header_table = Table([[left_table, right_table]], colWidths=[inch*4.8, inch*1.7])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ]))

        story = []

        # ----------------------------------------------------
        # PAGE 1: STUDENT WORKSHEET
        # ----------------------------------------------------
        story.append(Paragraph(title, title_style))
        story.append(header_table)
        story.append(Spacer(1, 6))
        
        # Add visual divider
        divider = Table([['']], colWidths=[inch*6.5], rowHeights=[1.5])
        divider.setStyle(TableStyle([
            ('LINEABOVE', (0,0), (-1,-1), 1.5, accent_color),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0),
        ]))
        story.append(divider)
        story.append(Spacer(1, 8))

        # Prominent Student Self-Check QR Code Box
        if qr_card:
            qr_wrapper = Table([[
                Paragraph("<b>📱 Digitale Selbstkontrolle &amp; Lösungen:</b><br/><font size=8 color='#334155'>Scanne diesen QR-Code mit dem Smartphone/Tablet für die interaktive Lösungskontrolle.</font>", body_style),
                qr_card
            ]], colWidths=[inch*5.3, inch*1.2])
            qr_wrapper.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
                ('BOX', (0,0), (-1,-1), 1.2, colors.HexColor("#0f172a")),
                ('PADDING', (0,0), (-1,-1), 5),
            ]))
            story.append(qr_wrapper)
            story.append(Spacer(1, 8))

        # Hefteintrag Section (Board Entry / Merkkasten)
        hefteintrag = data.get("hefteintrag")
        if hefteintrag and (hefteintrag.get("level_a_notes") or hefteintrag.get("level_b_notes") or hefteintrag.get("summary")):
            story.append(Paragraph("📌 Merkkasten / Hefteintrag", section_style))
            notes_text = hefteintrag.get("level_a_notes") or hefteintrag.get("summary") or ""
            notes_text = notes_text.replace("\n", "<br/>")
            
            box_data = [[Paragraph(f"<b>{hefteintrag.get('title', 'Hefteintrag')}</b><br/><br/>{notes_text}", body_style)]]
            box_table = Table(box_data, colWidths=[inch*6.5])
            box_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f5f7ff")),
                ('BOX', (0,0), (-1,-1), 1.5, accent_color),
                ('PADDING', (0,0), (-1,-1), 12),
            ]))
            story.append(box_table)
            story.append(Spacer(1, 10))

        # Einstufungsbox (Self-assessment check card) on Page 1
        if questions:
            box_content = [
                Paragraph("<b>🔍 Einstufungs-Check (Selbsteinschätzung)</b>", section_style),
                Paragraph("Löse diese Einstiegsfrage(n) zur Einschätzung deines Lernpfads. Vergleiche deine Antwort mit dem Selbstkontroll-Ergebnis unten.", body_style),
                Spacer(1, 4)
            ]
            solutions_list = []
            for i, q in enumerate(questions):
                question_text = q.get("question", "")
                options = q.get("options", [])
                correct_idx = q.get("correct", 0)
                correct_answer = options[correct_idx] if correct_idx < len(options) else ""
                
                box_content.extend([
                    Paragraph(f"<b>Frage {i+1}:</b> {question_text}", body_style),
                    Paragraph(" &nbsp;&nbsp;&nbsp;&nbsp; ".join([f"[ &nbsp; ] {opt}" for opt in options]), body_style),
                    Spacer(1, 4)
                ])
                solutions_list.append(f"Frage {i+1}: {correct_answer}")
                
            route_instruction = (
                "👉 <b>Dein Lernpfad:</b><br/>"
                "• Hast du die Frage(n) <b>richtig</b> beantwortet? Dann fahre direkt unten bei <b>Level B (Vertiefung)</b> fort!<br/>"
                "• War deine Antwort <b>nicht richtig</b>? Dann starte bei <b>Level A (Grundlagen)</b>."
            )
            box_content.append(Paragraph(route_instruction, ParagraphStyle('RouteText', parent=body_style, fontSize=9, leading=12, textColor=accent_color)))
            box_content.append(Spacer(1, 6))
            
            box_content.append(Spacer(1, 4))
            
            diagnostic_box = Table([[box_content]], colWidths=[inch*6.5])
            diagnostic_box.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
                ('BOX', (0,0), (-1,-1), 1.2, colors.HexColor("#cbd5e1")),
                ('LEFTPADDING', (0,0), (-1,-1), 12),
                ('RIGHTPADDING', (0,0), (-1,-1), 12),
                ('TOPPADDING', (0,0), (-1,-1), 10),
                ('BOTTOMPADDING', (0,0), (-1,-1), 10),
            ]))
            story.append(diagnostic_box)
            story.append(Spacer(1, 10))

        def add_level_tasks_to_story(level_data, section_title, is_teacher):
            story.append(Paragraph(section_title, section_style))
            tasks = level_data.get("tasks", [])
            if not tasks:
                tasks = [{"title": level_data.get("title", ""), "text": level_data.get("text", ""), "format": target_format}]
            
            for task in tasks:
                task_title = task.get("title", "")
                task_hint = task.get("hint", "")
                task_exp = task.get("explanation", "")
                
                if task_title:
                    story.append(Paragraph(f"<b>{task_title}</b>", body_style))
                    story.append(Spacer(1, 4))
                story.extend(PDFGenerator.generate_level_content_elements(
                    task.get("text", ""), 
                    task.get("format", target_format), 
                    is_teacher, 
                    styles, 
                    body_style
                ))
                
                if not is_teacher and task_hint and task_hint.strip():
                    story.append(Spacer(1, 2))
                    story.append(Paragraph(f"<i>{task_hint}</i>", hint_style))
                
                if is_teacher and task_exp and task_exp.strip():
                    story.append(Spacer(1, 2))
                    story.append(Paragraph(f"<b><font color='{accent_color_hex}'>💬 Erklärung / Feedback: {task_exp}</font></b>", hint_style))

                story.append(Spacer(1, 8))
            story.append(Spacer(1, 12))

        # Level C (Inklusion & DaZ) only if explicitly requested by teacher
        include_level_c = data.get("include_level_c", False) or data.get("pdf_include_level_c", False)
        level_c = data.get("level_c", {})
        if include_level_c and level_c and level_c.get("tasks"):
            add_level_tasks_to_story(level_c, f"Level C - Inklusion & DaZ (Leichte Sprache)", False)

        # Level A
        add_level_tasks_to_story(level_a, f"2. {level_a.get('title', 'Level A - Grundlagen')}", False)

        # Level B
        add_level_tasks_to_story(level_b, f"3. {level_b.get('title', 'Level B - Vertiefung')}", False)
        
        # Zusatzaufgaben (Experten-Aufgaben)
        zusatzaufgaben = data.get("zusatzaufgaben", [])
        if zusatzaufgaben:
            story.append(Paragraph("⭐ Experten-Aufgaben (für Schnellarbeiter)", section_style))
            for i, z in enumerate(zusatzaufgaben):
                story.append(Paragraph(f"<b>{z.get('title', f'Experten-Aufgabe {i+1}')}:</b> {z.get('task')}", body_style))
                story.append(Spacer(1, 4))
            story.append(Spacer(1, 10))

        # ----------------------------------------------------
        # PAGE 2: TEACHER SOLUTION SHEET
        # ----------------------------------------------------
        story.append(PageBreak())
        
        solution_title_style = ParagraphStyle(
            'SolutionTitle',
            parent=title_style,
            textColor=accent_color
        )
        
        story.append(Paragraph(f"Lösungsblatt & Lehrerhinweise: {title}", solution_title_style))
        
        # Build Solution Header
        left_details_sol = []
        left_details_sol.append("<i>Lösungsblatt & Lehrerkopie</i>")
        row_fields_sol = []
        if class_name:
            row_fields_sol.append(f"<b>Klasse:</b> {class_name}")
        if teacher_name:
            row_fields_sol.append(f"<b>Lehrkraft:</b> {teacher_name}")
        if row_fields_sol:
            left_details_sol.append(" &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; ".join(row_fields_sol))
            
        left_paragraphs_sol = [Paragraph(detail, body_style) for detail in left_details_sol]
        left_table_sol = Table([[p] for p in left_paragraphs_sol], colWidths=[inch*4.8])
        left_table_sol.setStyle(TableStyle([
            ('BOTTOMPADDING', (0,0), (-1,-1), 1),
            ('TOPPADDING', (0,0), (-1,-1), 1),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ]))
        
        logo_img_sol = None
        if logo_data and logo_io:
            try:
                logo_io.seek(0)
                logo_img_sol = Image(logo_io, width=1.0*inch, height=0.55*inch)
                logo_img_sol.hAlign = 'RIGHT'
            except Exception:
                pass
                
        right_flow_sol = []
        if logo_img_sol:
            right_flow_sol.append([logo_img_sol])
        right_flow_sol.append([Paragraph(school_year, school_year_style)])
        
        right_table_sol = Table(right_flow_sol, colWidths=[inch*1.5])
        right_table_sol.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'RIGHT'),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 1),
            ('TOPPADDING', (0,0), (-1,-1), 1),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ]))

        header_table_sol = Table([[left_table_sol, right_table_sol]], colWidths=[inch*5.0, inch*1.5])
        header_table_sol.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ]))
        
        story.append(header_table_sol)
        story.append(Spacer(1, 10))

        if hefteintrag and hefteintrag.get("level_b_notes"):
            story.append(Paragraph("📌 Merkkasten / Hefteintrag (Level B - Mitschrift)", section_style))
            b_notes = hefteintrag.get("level_b_notes", "").replace("\n", "<br/>")
            b_box = Table([[Paragraph(f"<b>{hefteintrag.get('title', 'Vollständiger Hefteintrag')}</b><br/><br/>{b_notes}", body_style)]], colWidths=[inch*6.5])
            b_box.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f0fdf4")),
                ('BOX', (0,0), (-1,-1), 1.5, accent_color),
                ('PADDING', (0,0), (-1,-1), 12),
            ]))
            story.append(b_box)
            story.append(Spacer(1, 10))

        if questions:
            story.append(Paragraph("1. Einstufungs-Fragen (Lösungen)", section_style))
            for i, q in enumerate(questions):
                correct_idx = q.get("correct", 0)
                options_str = []
                for idx, opt in enumerate(q.get("options", [])):
                    if idx == correct_idx:
                        options_str.append(f"<b>[X] <font color='#1b5e20'>{opt}</font></b>")
                    else:
                        options_str.append(f"[ ] {opt}")
                story.append(Paragraph(f"<b>Frage {i+1}:</b> {q.get('question')}", body_style))
                story.append(Paragraph(" &nbsp;&nbsp;&nbsp;&nbsp; ".join(options_str), body_style))
                story.append(Spacer(1, 4))
            story.append(Spacer(1, 8))

        level_c = data.get("level_c", {})
        if level_c and level_c.get("tasks"):
            add_level_tasks_to_story(level_c, f"Level C - Inklusion & DaZ (Lösungen)", True)

        # Level A Solutions
        add_level_tasks_to_story(level_a, f"2. {level_a.get('title', 'Level A')} (Lösungen)", True)

        # Level B Solutions
        add_level_tasks_to_story(level_b, f"3. {level_b.get('title', 'Level B')} (Lösungen)", True)

        # Build PDF
        doc.build(story)
        pdf_data = buffer.getvalue()
        buffer.close()
        return pdf_data
