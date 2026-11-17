import io
import re
import os
import base64
import logging
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Flowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.shapes import Drawing, Rect
from reportlab.graphics.barcode.qr import QrCodeWidget

from h5p_generator import H5PGenerator

logger = logging.getLogger("adaptify.pdf")

class RotatedFlowable(Flowable):
    def __init__(self, flowable, angle=180):
        super().__init__()
        self.flowable = flowable
        self.angle = angle

    def wrap(self, availWidth, availHeight):
        w, h = self.flowable.wrap(availWidth, availHeight)
        self.width, self.height = w, h
        return w, h

    def draw(self):
        self.canv.saveState()
        self.canv.rotate(self.angle)
        self.canv.translate(-self.width, -self.height)
        self.flowable.drawOn(self.canv, 0, 0)
        self.canv.restoreState()

def clean_reportlab_html(text: str) -> str:
    """
    Cleans up HTML strings for ReportLab Paragraph compatibility:
    - Escapes loose ampersands
    - Replaces <strong> and <em> with ReportLab <b> and <i>
    - Strips unsupported HTML tags while preserving line breaks
    """
    if not text:
        return ""
    s = str(text)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r'</?br\s*/?>', '\n', s, flags=re.IGNORECASE)
    s = re.sub(r'&(?!(?:amp|nbsp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)', '&amp;', s)
    s = re.sub(r'</?strong>', lambda m: '<b>' if '<strong>' in m.group().lower() else '</b>', s, flags=re.IGNORECASE)
    s = re.sub(r'</?em>', lambda m: '<i>' if 'em' in m.group().lower() else '</i>', s, flags=re.IGNORECASE)
    s = re.sub(r'</?(?:div|p|span|section|article|header|table|tr|td|tbody|thead|ul|ol|li|h[1-6]|small|blockquote|hr)\b[^>]*>', '\n', s, flags=re.IGNORECASE)
    s = re.sub(r'\n{3,}', '\n\n', s)
    s = s.replace('\n', '<br/>')
    return s.strip()

class PDFGenerator:
    @staticmethod
    def parse_blanks_for_student(text):
        def repl(match):
            inner = match.group(1).split(':')[0].strip()
            # Draw line proportional to word length (min 10 underscores, max 24)
            line_len = max(10, min(24, len(inner) + 4))
            return "_" * line_len
        clean_text = clean_reportlab_html(text).replace("<u>", "").replace("</u>", "")
        return re.sub(r"\*([^*]+)\*", repl, clean_text)

    @staticmethod
    def parse_blanks_for_teacher(text):
        def repl(match):
            word = match.group(1).split(':')[0].strip()
            return f'<b><font color="#15803d">{word}</font></b>'
        clean_text = clean_reportlab_html(text).replace("<u>", "").replace("</u>", "")
        return re.sub(r"\*([^*]+)\*", repl, clean_text)

    @staticmethod
    def generate_level_content_elements(raw_text, target_format, is_teacher, styles, body_style, distractors=None, is_level_b=False):
        """
        Transforms tasks into classroom-ready ReportLab flowables:
        - Lückentext: Hand-writing lines for students, green bold for teacher
        - Drag the Words: Wortspeicher box (with distractors for Level B) + writing lines
        - Multiple Choice: Checkboxes [   ] or [X]
        - Wahr/Falsch: True/False options with check marks
        - Tabellen-Zuordnung: Clean reportlab Table grid
        - Freies Schreiben: 4-6 writing lines
        - Vokabelkarten: Vocabulary flashcard layout
        """
        story_elements = []
        raw_text = str(raw_text or "").strip()
        hint_style = ParagraphStyle(
            'TaskHintStyle',
            parent=body_style,
            fontName='Helvetica-Oblique',
            fontSize=8.5,
            leading=11.5,
            textColor=colors.HexColor("#64748b")
        )

        # 1. Vokabelkarten / Dialogcards
        if "vorderseite:" in raw_text.lower() or "rückseite:" in raw_text.lower() or target_format == "Vokabelkarten":
            cards = H5PGenerator.parse_dialogcards_text(raw_text)
            if cards:
                for c in cards:
                    clean_q = re.sub('<[^<]+?>', '', c.get("text", "")).replace("&nbsp;", " ").strip()
                    clean_a = re.sub('<[^<]+?>', '', c.get("answer", "")).replace("&nbsp;", " ").strip()
                    story_elements.append(Paragraph(f"<b>Begriff / Vokabel:</b> {clean_q}", body_style))
                    if is_teacher:
                        story_elements.append(Paragraph(f"<b>Lösung / Bedeutung:</b> <font color='#15803d'><b>{clean_a}</b></font>", body_style))
                    else:
                        story_elements.append(Paragraph("<b>Bedeutung:</b> __________________________________________________", body_style))
                    story_elements.append(Spacer(1, 4))
                story_elements.append(Spacer(1, 4))
                return story_elements

        # 2. Multiple Choice
        if target_format == "Multiple Choice":
            mc_questions = H5PGenerator.parse_multiple_choice_text(raw_text)
            if not mc_questions and ("[" in raw_text and "]" in raw_text):
                lines = raw_text.split("\n")
                q_text = lines[0] if lines else "Wähle die richtige Antwort:"
                answers = []
                for l in lines[1:]:
                    l_s = l.strip()
                    if l_s.startswith("[X]") or l_s.startswith("[x]"):
                        answers.append({"text": l_s[3:].strip(), "correct": True})
                    elif l_s.startswith("[ ]") or l_s.startswith("[]"):
                        answers.append({"text": l_s[3:].strip(), "correct": False})
                if answers:
                    mc_questions = [{"question": q_text, "answers": answers}]

            if mc_questions:
                for q in mc_questions:
                    q_clean = re.sub('<[^<]+?>', '', q.get("question", "")).strip()
                    if q_clean and not q_clean.lower().startswith("frage:"):
                        story_elements.append(Paragraph(f"<b>Frage:</b> {q_clean}", body_style))
                    elif q_clean:
                        story_elements.append(Paragraph(f"<b>{q_clean}</b>", body_style))
                    
                    for ans in q.get("answers", []):
                        ans_text = re.sub('<[^<]+?>', '', ans.get("text", "")).strip()
                        if is_teacher and ans.get("correct"):
                            box = "<b>[X] <font color='#15803d'>"
                            end_box = "</font></b>"
                        else:
                            box = "[ &nbsp; ] "
                            end_box = ""
                        story_elements.append(Paragraph(f"{box}{ans_text}{end_box}", body_style))
                    story_elements.append(Spacer(1, 4))
                return story_elements

        # 3. Wahr/Falsch (True/False)
        if target_format in ["Wahr/Falsch", "True/False"] or ("aussage:" in raw_text.lower() and "antwort:" in raw_text.lower()):
            tf_items = H5PGenerator.parse_true_false_text(raw_text)
            if tf_items:
                for item in tf_items:
                    stmt = re.sub('<[^<]+?>', '', item.get("question", "")).strip()
                    is_correct = bool(item.get("correct"))
                    story_elements.append(Paragraph(f"<b>Behauptung:</b> {stmt}", body_style))
                    if is_teacher:
                        tf_text = "<b>[X] <font color='#15803d'>Wahr / Richtig</font></b> &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; [ &nbsp; ] Falsch" if is_correct else "[ &nbsp; ] Wahr &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; <b>[X] <font color='#15803d'>Falsch / Unzutreffend</font></b>"
                    else:
                        tf_text = "[ &nbsp; ] <b>Wahr / Richtig</b> &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; [ &nbsp; ] <b>Falsch / Unzutreffend</b>"
                    story_elements.append(Paragraph(tf_text, body_style))
                    story_elements.append(Spacer(1, 4))
                return story_elements

        # 4. Drag the Words (Wortspeicher mit / ohne Distraktoren)
        if target_format == "Drag the Words":
            # Extract target words in asterisks
            target_words = re.findall(r'\*([^*:]+)(?::[^*]*)?\*', raw_text)
            all_pool = list(dict.fromkeys(target_words))
            clean_distractors = [str(d).strip().strip('*') for d in (distractors or []) if str(d).strip()]
            
            pool_words = all_pool.copy()
            if clean_distractors:
                for d in clean_distractors:
                    if d not in pool_words:
                        pool_words.append(d)

            # Wortspeicher Box for students
            if pool_words:
                sorted_pool = sorted(pool_words, key=lambda s: s.lower())
                pool_str = " &nbsp;&nbsp;•&nbsp;&nbsp; ".join(sorted_pool)
                dist_note = " <font color='#4f46e5' size=7.5><i>(inklusive Zusatzbegriffe / Distraktoren)</i></font>" if (clean_distractors and not is_teacher) else ""
                ws_box = Table([[
                    Paragraph(f"📦 <b>Wortspeicher (Wähle die passenden Begriffe für die Lücken):</b>{dist_note}<br/>{pool_str}", ParagraphStyle('WS', parent=body_style, fontSize=8.5, leading=11.5, textColor=colors.HexColor("#1e293b")))
                ]], colWidths=[inch*7.1])
                ws_box.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f1f5f9")),
                    ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#cbd5e1")),
                    ('PADDING', (0,0), (-1,-1), 6),
                ]))
                story_elements.append(ws_box)
                story_elements.append(Spacer(1, 4))

            parsed_text = PDFGenerator.parse_blanks_for_teacher(raw_text) if is_teacher else PDFGenerator.parse_blanks_for_student(raw_text)
            story_elements.append(Paragraph(parsed_text, body_style))
            if is_teacher and clean_distractors:
                story_elements.append(Paragraph(f"<i><font color='#64748b' size=8>Distraktoren im Wortspeicher: {', '.join(clean_distractors)}</font></i>", body_style))
            return story_elements

        # 5. Freies Schreiben / Essay / Schreibaufgabe
        if target_format in ["Freies Schreiben", "Essay", "Kreatives Schreiben", "Schreibaufgabe", "Textproduktion"]:
            clean_inst = clean_reportlab_html(raw_text)
            story_elements.append(Paragraph(clean_inst, body_style))
            if is_teacher:
                story_elements.append(Paragraph("<b><font color='#15803d'>Musterantwort / Kriterien:</font></b> Individuelle Textproduktion. Bewertung nach inhaltlicher Stimmigkeit, Textaufbau, logischer Argumentation und Sprachrichtigkeit.", body_style))
            else:
                lines_html = "<br/>".join(["________________________________________________________________________________________"] * 5)
                story_elements.append(Paragraph(lines_html, ParagraphStyle('WritingLines', parent=body_style, textColor=colors.HexColor("#94a3b8"), leading=16)))
            story_elements.append(Spacer(1, 4))
            return story_elements

        # 6. Tabellen-Zuordnung
        is_table = bool(
            ("<table" in raw_text.lower()) or 
            (len([l for l in raw_text.strip().split("\n") if l.strip().startswith("|") and l.strip().endswith("|")]) >= 2) or
            bool(re.search(r'\[\s*[^\]]+\s*\]', raw_text)) or
            target_format in ["Tabellen-Zuordnung", "Kategorie-Zuordnung"]
        )
        if is_table:
            headers = []
            cols_data = []

            # Case A: HTML table
            if "<table" in raw_text.lower():
                th_list = re.findall(r'<th[^>]*>(.*?)</th>', raw_text, re.IGNORECASE | re.DOTALL)
                if not th_list:
                    first_tr = re.search(r'<tr[^>]*>(.*?)</tr>', raw_text, re.IGNORECASE | re.DOTALL)
                    if first_tr:
                        th_list = re.findall(r'<td[^>]*>(.*?)</td>', first_tr.group(1), re.IGNORECASE | re.DOTALL)
                headers = [clean_reportlab_html(re.sub(r'<[^>]+>', '', h).strip()) for h in th_list if re.sub(r'<[^>]+>', '', h).strip()]
                
                rows = re.findall(r'<tr[^>]*>(.*?)</tr>', raw_text, re.IGNORECASE | re.DOTALL)
                cols_dict = {i: [] for i in range(len(headers))}
                for r in rows:
                    if "<th" in r.lower() and "<td" not in r.lower():
                        continue
                    tds = re.findall(r'<td[^>]*>(.*?)</td>', r, re.IGNORECASE | re.DOTALL)
                    if tds:
                        for i, td in enumerate(tds):
                            clean_td = clean_reportlab_html(re.sub(r'<[^>]+>', '', td).strip())
                            if clean_td and i in cols_dict:
                                cols_dict[i].append(clean_td)
                cols_data = [cols_dict.get(i, []) for i in range(len(headers))]

            # Case B: Markdown table
            elif any(l.strip().startswith("|") and l.strip().endswith("|") for l in raw_text.split("\n")):
                md_lines = [l.strip() for l in raw_text.strip().split("\n") if l.strip().startswith("|") and l.strip().endswith("|")]
                if len(md_lines) >= 2:
                    headers = [clean_reportlab_html(c.strip()) for c in md_lines[0].strip('|').split('|')]
                    start_row = 2 if (len(md_lines) > 1 and re.match(r'^[|\-:\s]+$', md_lines[1])) else 1
                    cols_dict = {i: [] for i in range(len(headers))}
                    for r_line in md_lines[start_row:]:
                        cols = [clean_reportlab_html(c.strip()) for c in r_line.strip('|').split('|')]
                        for i, c_val in enumerate(cols):
                            if i in cols_dict:
                                cols_dict[i].append(c_val)
                    cols_data = [cols_dict.get(i, []) for i in range(len(headers))]

            # Case C: Bracket categories [ Category ] or Kategorie: ...
            elif re.search(r'(?:\[\s*([^\]]+)\s*\]|(?:Kategorie|Spalte):\s*([^\n]+))', raw_text):
                cat_matches = list(re.finditer(r'(?:\[\s*([^\]]+)\s*\]|(?:^|\n)(?:Kategorie|Spalte):\s*([^\n]+))', raw_text))
                for i, m in enumerate(cat_matches):
                    c_name = (m.group(1) or m.group(2) or "").strip()
                    headers.append(clean_reportlab_html(c_name))
                    start = m.end()
                    end = cat_matches[i+1].start() if i + 1 < len(cat_matches) else len(raw_text)
                    chunk = raw_text[start:end]
                    dis_m = re.search(r'(?:Distraktoren|Zusatzwörter|Falsche Optionen):', chunk, re.IGNORECASE)
                    if dis_m:
                        chunk = chunk[:dis_m.start()]
                    items = []
                    for line in chunk.split("\n"):
                        clean_l = line.strip().lstrip("-*•").strip()
                        if clean_l and not clean_l.startswith("["):
                            items.append(clean_reportlab_html(clean_l))
                    cols_data.append(items)

            if headers and cols_data:
                header_p = [Paragraph(f"<b>{h}</b>", ParagraphStyle('TH', parent=body_style, fontName='Helvetica-Bold', fontSize=9, textColor=colors.white, alignment=1)) for h in headers]
                table_data = [header_p]
                max_r = max(len(c) for c in cols_data) if cols_data else 0
                for r_idx in range(max_r):
                    row_cells = []
                    for c_idx in range(len(headers)):
                        c_val = cols_data[c_idx][r_idx] if r_idx < len(cols_data[c_idx]) else ""
                        if c_val:
                            cell_text = PDFGenerator.parse_blanks_for_teacher(c_val) if is_teacher else PDFGenerator.parse_blanks_for_student(c_val)
                        else:
                            cell_text = ""
                        row_cells.append(Paragraph(cell_text, ParagraphStyle('TD', parent=body_style, fontSize=8.5, leading=11, alignment=1)))
                    table_data.append(row_cells)

                col_w = (7.1 * inch) / max(1, len(headers))
                col_widths = [col_w] * len(headers)
                t_widget = Table(table_data, colWidths=col_widths)
                t_widget.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1e293b")),
                    ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('GRID', (0,0), (-1,-1), 1, colors.HexColor("#cbd5e1")),
                    ('PADDING', (0,0), (-1,-1), 6),
                    ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
                ]))
                story_elements.append(t_widget)
                story_elements.append(Spacer(1, 6))
                return story_elements

        # 7. Wörter markieren
        if target_format == "Wörter markieren":
            if is_teacher:
                parsed_text = PDFGenerator.parse_blanks_for_teacher(raw_text)
            else:
                parsed_text = re.sub(r"\*([^*]+)\*", r"\1", raw_text).replace("\n", "<br/>")
                story_elements.append(Paragraph("<i>✍️ Lies den Text aufmerksam durch und markiere die gesuchten Wörter mit einem Textmarker:</i>", hint_style))
            story_elements.append(Paragraph(parsed_text, body_style))
            return story_elements

        # 8. Default: Lückentext
        parsed_text = PDFGenerator.parse_blanks_for_teacher(raw_text) if is_teacher else PDFGenerator.parse_blanks_for_student(raw_text)
        story_elements.append(Paragraph(parsed_text, body_style))
        return story_elements

    @staticmethod
    def generate_worksheet_pdf(data: dict) -> bytes:
        """
        Generates differentiated DIN A4 PDF worksheets:
        - Arbeitsblatt 1 (Basis / Fördern – Level A)
        - Arbeitsblatt 2 (Profi / Fordern – Level B)
        - Lösungsblatt & Lehrerkopie (Selbstkontrolle)
        No diagnostic/branching questions on the student printouts.
        """
        if data.get("video_mode") == "interactive_video" or (data.get("interactions") and not data.get("level_a")):
            return PDFGenerator.generate_video_hefteintrag_pdf(data)

        raw_title = data.get("title", "Differenzierte Übung")
        if ":" in raw_title:
            raw_title = raw_title.split(":", 1)[-1].strip()
        elif " - " in raw_title:
            raw_title = raw_title.split(" - ", 1)[-1].strip()

        clean_title = re.sub(r'\d+\s*x?\s*(?:zu|für)?\s*', '', raw_title).strip()
        clean_title = re.sub(r'^\s*,\s*|\s*,\s*$', '', clean_title)
        if not clean_title or len(clean_title) < 3 or ("Textverständnis" in clean_title and "Fremdwörter" in clean_title):
            clean_title = "Unterrichtseinheit"
        title = clean_title

        target_format = data.get("target_format", "Lückentext")
        level_a = data.get("level_a") or {}
        level_b = data.get("level_b") or {}

        # Ensure tasks are present for both levels
        tasks_a = level_a.get("tasks", []) or data.get("tasks", [])
        tasks_b = level_b.get("tasks", []) or data.get("tasks", [])
        if not tasks_a and tasks_b:
            tasks_a = tasks_b
        if not tasks_b and tasks_a:
            tasks_b = tasks_a

        # Customization parameters
        class_name = data.get("pdf_class_name", "")
        teacher_name = data.get("pdf_teacher_name", "")
        accent_color_hex = data.get("pdf_accent_color", "#0284c7")
        accent_color = colors.HexColor(accent_color_hex)
        pdf_variant = str(data.get("pdf_variant", "bundle")).lower().strip()

        include_lehrplan = data.get("pdf_include_lehrplan", False)
        lehrplan_code = data.get("lehrplan_code", "")

        # Page setup: DIN A4, margins 0.5 inch (symmetric, content width = 7.27 inch)
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=inch*0.5,
            leftMargin=inch*0.5,
            topMargin=inch*0.45,
            bottomMargin=inch*0.45
        )

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            'WorksheetTitle',
            parent=styles['Title'],
            fontName='Helvetica-Bold',
            fontSize=16,
            leading=20,
            textColor=accent_color,
            alignment=0,
            spaceAfter=3,
            keepWithNext=True
        )

        badge_style_a = ParagraphStyle(
            'LevelBadgeA',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#0284c7"),
            spaceAfter=4,
            keepWithNext=True
        )

        badge_style_b = ParagraphStyle(
            'LevelBadgeB',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#1d4ed8"),
            spaceAfter=4,
            keepWithNext=True
        )

        badge_style_sol = ParagraphStyle(
            'LevelBadgeSol',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#15803d"),
            spaceAfter=4,
            keepWithNext=True
        )

        section_style = ParagraphStyle(
            'SectionHeader',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=12,
            leading=16,
            textColor=accent_color,
            spaceBefore=10,
            spaceAfter=5,
            keepWithNext=True
        )

        body_style = ParagraphStyle(
            'StandardBody',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9.5,
            leading=14,
            textColor=colors.HexColor("#334155"),
            spaceAfter=6
        )

        hint_style = ParagraphStyle(
            'StandardHint',
            parent=styles['Italic'],
            fontSize=8.5,
            leading=11.5,
            textColor=colors.HexColor("#64748b")
        )

        # Proportional Logo builder
        logo_bytes = None
        logo_data = data.get("pdf_logo_base64")
        if not logo_data:
            default_logo_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "www", "logo_full.png")
            if os.path.exists(default_logo_path):
                try:
                    with open(default_logo_path, "rb") as f:
                        logo_bytes = f.read()
                except Exception:
                    pass
        else:
            try:
                if "," in logo_data:
                    logo_data = logo_data.split(",", 1)[1]
                logo_bytes = base64.b64decode(logo_data)
            except Exception:
                pass

        def _make_proportional_logo(raw_bytes, max_w=1.45*inch, max_h=0.65*inch):
            if not raw_bytes:
                return None
            try:
                from PIL import Image as PILImage
                from reportlab.platypus import Image as RLImage
                bio = io.BytesIO(raw_bytes)
                pil_im = PILImage.open(bio)
                orig_w, orig_h = pil_im.size
                if orig_w <= 0 or orig_h <= 0:
                    return None
                aspect = float(orig_w) / float(orig_h)
                if aspect > (max_w / max_h):
                    draw_w = max_w
                    draw_h = max_w / aspect
                else:
                    draw_h = max_h
                    draw_w = max_h * aspect
                bio.seek(0)
                rl_img = RLImage(bio, width=draw_w, height=draw_h)
                rl_img.hAlign = 'RIGHT'
                return rl_img
            except Exception as e:
                logger.warning(f"Failed to create proportional logo: {e}")
                return None

        # Calculate School Year
        import datetime
        now = datetime.datetime.now()
        year = now.year
        month = now.month
        school_year = f"Schuljahr {year}/{str(year+1)[2:]}" if month >= 8 else f"Schuljahr {year-1}/{str(year)[2:]}"

        # Build QR-Code for Student Self-Check Solution
        solution_url = (data.get("solution_url") or "").strip()
        pin_code = data.get("session_pin") or data.get("pin") or "DEMO123"
        if not solution_url or "localhost" in solution_url or "127.0.0.1" in solution_url or "file:" in solution_url:
            solution_url = f"https://adaptify-xpym.onrender.com/solution.html?pin={pin_code}"
        elif "play.html" in solution_url:
            solution_url = solution_url.replace("play.html", "solution.html")

        include_qr = data.get("pdf_include_qr", True)
        qr_card = None
        if include_qr:
            try:
                qr_size = 68
                qr_w = QrCodeWidget(solution_url)
                qr_w.barWidth = qr_size
                qr_w.barHeight = qr_size
                qr_w.barLevel = 'M'
                qr_w.barBorder = 3

                qr_draw = Drawing(qr_size, qr_size)
                qr_draw.add(Rect(0, 0, qr_size, qr_size, fillColor=colors.white, strokeColor=None))
                qr_draw.add(qr_w)

                qr_title_style = ParagraphStyle(
                    'QRTitleStyle',
                    fontName='Helvetica-Bold',
                    fontSize=7,
                    leading=8.5,
                    textColor=colors.HexColor("#0f172a"),
                    alignment=1
                )
                qr_sub_style = ParagraphStyle(
                    'QRSubStyle',
                    fontName='Helvetica',
                    fontSize=6,
                    leading=7.5,
                    textColor=colors.HexColor("#475569"),
                    alignment=1
                )

                qr_card = Table([
                    [qr_draw],
                    [Paragraph("📱 <b>Lösungs-Check</b>", qr_title_style)],
                    [Paragraph("Selbstkontrolle", qr_sub_style)]
                ], colWidths=[inch*1.3])
                qr_card.setStyle(TableStyle([
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('BACKGROUND', (0,0), (-1,-1), colors.white),
                    ('BOX', (0,0), (-1,-1), 1.0, colors.HexColor("#cbd5e1")),
                    ('TOPPADDING', (0,0), (-1,-1), 3),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 3),
                    ('LEFTPADDING', (0,0), (-1,-1), 3),
                    ('RIGHTPADDING', (0,0), (-1,-1), 3),
                ]))
            except Exception as qr_err:
                logger.warning(f"Failed to generate QR code: {qr_err}")

        # Helper to construct sheet headers
        def build_header_table(sheet_title, badge_text, badge_style, is_sol=False):
            left_details = []
            left_details.append(Paragraph(f"<b>{sheet_title}</b>", title_style))
            left_details.append(Paragraph(badge_text, badge_style))

            if not is_sol:
                meta_line1 = f"<b>Name:</b> ___________________________ &nbsp;&nbsp;&nbsp;&nbsp; <b>Klasse:</b> {class_name or '______'} &nbsp;&nbsp;&nbsp;&nbsp; <b>Datum:</b> ____________"
                left_details.append(Paragraph(meta_line1, body_style))
                sub_meta = []
                if teacher_name:
                    sub_meta.append(f"<b>Lehrkraft:</b> {teacher_name}")
                if include_lehrplan and lehrplan_code:
                    sub_meta.append(f"<i><font color='#4f46e5'>📌 LehrplanPlus: {lehrplan_code}</font></i>")
                if sub_meta:
                    left_details.append(Paragraph(" &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; ".join(sub_meta), body_style))
            else:
                left_details.append(Paragraph("<i>Vollständige Musterlösungen zur Selbstkontrolle oder Lehrkraft-Ablage</i>", hint_style))
                sub_meta = []
                if class_name:
                    sub_meta.append(f"<b>Klasse:</b> {class_name}")
                if teacher_name:
                    sub_meta.append(f"<b>Lehrkraft:</b> {teacher_name}")
                if sub_meta:
                    left_details.append(Paragraph(" &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; ".join(sub_meta), body_style))

            left_table = Table([[p] for p in left_details], colWidths=[inch*5.5])
            left_table.setStyle(TableStyle([
                ('BOTTOMPADDING', (0,0), (-1,-1), 0),
                ('TOPPADDING', (0,0), (-1,-1), 0),
                ('LEFTPADDING', (0,0), (-1,-1), 0),
                ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ]))

            right_flow = []
            logo_img = _make_proportional_logo(logo_bytes) if logo_bytes else None
            if logo_img:
                right_flow.append([logo_img])
            
            school_year_style = ParagraphStyle(
                'SchoolYearStyle',
                parent=body_style,
                fontName='Helvetica-Oblique',
                fontSize=7.5,
                leading=9,
                textColor=colors.HexColor("#475569"),
                alignment=2
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

            h_table = Table([[left_table, right_table]], colWidths=[inch*5.6, inch*1.65])
            h_table.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('BOTTOMPADDING', (0,0), (-1,-1), 0),
                ('TOPPADDING', (0,0), (-1,-1), 0),
                ('LEFTPADDING', (0,0), (-1,-1), 0),
                ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ]))
            return h_table

        def make_divider():
            d = Table([['']], colWidths=[inch*7.25], rowHeights=[1.5])
            d.setStyle(TableStyle([
                ('LINEABOVE', (0,0), (-1,-1), 1.5, accent_color),
                ('BOTTOMPADDING', (0,0), (-1,-1), 0),
                ('TOPPADDING', (0,0), (-1,-1), 0),
            ]))
            return d

        def make_qr_box():
            if not qr_card:
                return None
            qr_wrapper = Table([[
                Paragraph("<b>📱 Digitale Selbstkontrolle &amp; Lösungen:</b><br/><font size=8 color='#475569'>Scanne diesen QR-Code mit deinem Smartphone/Tablet für die interaktive Lösungskontrolle.</font>", body_style),
                qr_card
            ]], colWidths=[inch*5.8, inch*1.45])
            qr_wrapper.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
                ('BOX', (0,0), (-1,-1), 1.0, colors.HexColor("#cbd5e1")),
                ('PADDING', (0,0), (-1,-1), 5),
            ]))
            return qr_wrapper

        extracted_text = (data.get("extracted_text") or "").strip()
        hefteintrag = data.get("hefteintrag") or {}

        def make_reading_box():
            if extracted_text and len(extracted_text) > 40 and not extracted_text.startswith("Der erkannte Text des Originaldokumentes"):
                clean_reading_text = extracted_text.replace("\n", "<br/>")
                reading_table = Table([
                    [Paragraph("📖 <b>Lesetext &amp; Ausgangslage:</b>", ParagraphStyle('RHead', parent=body_style, fontName='Helvetica-Bold', fontSize=10, textColor=colors.HexColor("#0f172a")))],
                    [Paragraph(clean_reading_text, body_style)]
                ], colWidths=[inch*7.25])
                reading_table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
                    ('BOX', (0,0), (-1,-1), 1.0, colors.HexColor("#cbd5e1")),
                    ('PADDING', (0,0), (-1,-1), 7),
                ]))
                return reading_table
            return None

        def add_tasks_to_story(target_story, tasks, is_teacher, level_char="A"):
            is_level_b = (level_char == "B")
            for idx, task in enumerate(tasks):
                task_title = task.get("title", f"Aufgabe {idx+1}")
                task_hint = task.get("hint", "").strip()
                task_exp = task.get("explanation", "").strip()
                t_format = task.get("format", target_format)
                distractors = task.get("distractors", [])

                target_story.append(Paragraph(f"<b>{idx+1}. {task_title}</b>", body_style))
                target_story.append(Spacer(1, 2))

                elements = PDFGenerator.generate_level_content_elements(
                    task.get("text", ""),
                    t_format,
                    is_teacher,
                    styles,
                    body_style,
                    distractors=distractors,
                    is_level_b=is_level_b
                )
                target_story.extend(elements)

                if not is_teacher and not is_level_b and task_hint:
                    target_story.append(Spacer(1, 2))
                    target_story.append(Paragraph(f"💡 <i>Tipp: {task_hint}</i>", hint_style))

                if is_teacher and task_exp:
                    target_story.append(Spacer(1, 2))
                    target_story.append(Paragraph(f"<b><font color='{accent_color_hex}'>💬 Erklärung / Feedback: {task_exp}</font></b>", hint_style))

                target_story.append(Spacer(1, 8))

        story = []

        # ====================================================
        # ARBEITSBLATT 1: BASIS (FÖRDERN – LEVEL A)
        # ====================================================
        if pdf_variant in ["bundle", "basic"]:
            h_table_a = build_header_table(
                title,
                "<b>Arbeitsblatt 1: Basis &amp; Grundlagen (Level A – Fördern)</b>",
                badge_style_a,
                is_sol=False
            )
            story.append(h_table_a)
            story.append(Spacer(1, 4))
            story.append(make_divider())
            story.append(Spacer(1, 6))

            qr_box_a = make_qr_box()
            if qr_box_a:
                story.append(qr_box_a)
                story.append(Spacer(1, 6))

            read_box_a = make_reading_box()
            if read_box_a:
                story.append(read_box_a)
                story.append(Spacer(1, 6))

            # Merkkasten Level A (Grundlagen)
            notes_a = hefteintrag.get("level_a_notes") or hefteintrag.get("summary")
            if notes_a and notes_a.strip():
                clean_notes_a = clean_reportlab_html(notes_a)
                heft_t = clean_reportlab_html(hefteintrag.get('title', 'Merkkasten'))
                box_a = Table([
                    [Paragraph("✍️ <b>Aufgabe für dein Heft:</b> Übertrage diesen Merkkasten sauber in dein Schulheft!", hint_style)],
                    [Paragraph(f"<b>📌 {heft_t}</b><br/><br/>{clean_notes_a}", body_style)]
                ], colWidths=[inch*7.25])
                box_a.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#eff6ff")),
                    ('BOX', (0,0), (-1,-1), 1.2, colors.HexColor("#3b82f6")),
                    ('PADDING', (0,0), (-1,-1), 8),
                ]))
                story.append(box_a)
                story.append(Spacer(1, 8))

            story.append(Paragraph("<b>Übungsaufgaben (Basis &amp; Grundlagen):</b>", section_style))
            add_tasks_to_story(story, tasks_a, is_teacher=False, level_char="A")

        # PageBreak between worksheets
        if pdf_variant == "bundle":
            story.append(PageBreak())

        # ====================================================
        # ARBEITSBLATT 2: PROFI (FORDERN – LEVEL B)
        # ====================================================
        if pdf_variant in ["bundle", "profi"]:
            h_table_b = build_header_table(
                title,
                "<b>Arbeitsblatt 2: Vertiefung &amp; Transfer (Level B – Fordern)</b>",
                badge_style_b,
                is_sol=False
            )
            story.append(h_table_b)
            story.append(Spacer(1, 4))
            story.append(make_divider())
            story.append(Spacer(1, 6))

            qr_box_b = make_qr_box()
            if qr_box_b:
                story.append(qr_box_b)
                story.append(Spacer(1, 6))

            read_box_b = make_reading_box()
            if read_box_b:
                story.append(read_box_b)
                story.append(Spacer(1, 6))

            # Merkkasten Level B (Vertiefung)
            notes_b = hefteintrag.get("level_b_notes") or hefteintrag.get("summary")
            if notes_b and notes_b.strip():
                clean_notes_b = clean_reportlab_html(notes_b)
                heft_t = clean_reportlab_html(hefteintrag.get('title', 'Merkkasten'))
                box_b = Table([
                    [Paragraph("✍️ <b>Aufgabe für dein Heft:</b> Ergänze die Fachbegriffe und Zusammenhänge in deinem Schulheft!", hint_style)],
                    [Paragraph(f"<b>📌 {heft_t}</b><br/><br/>{clean_notes_b}", body_style)]
                ], colWidths=[inch*7.25])
                box_b.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f0fdf4")),
                    ('BOX', (0,0), (-1,-1), 1.2, colors.HexColor("#16a34a")),
                    ('PADDING', (0,0), (-1,-1), 8),
                ]))
                story.append(box_b)
                story.append(Spacer(1, 8))

            story.append(Paragraph("<b>Übungsaufgaben (Vertiefung &amp; Transfer):</b>", section_style))
            add_tasks_to_story(story, tasks_b, is_teacher=False, level_char="B")

            # Zusatzaufgaben (Experten-Aufgaben) on Level B
            zusatzaufgaben = data.get("zusatzaufgaben", [])
            if zusatzaufgaben:
                story.append(Spacer(1, 4))
                story.append(Paragraph("⭐ <b>Experten-Aufgaben (für Schnellarbeiter &amp; Transfer):</b>", section_style))
                for i, z in enumerate(zusatzaufgaben):
                    z_title = z.get('title', f'Experten-Aufgabe {i+1}')
                    z_task = z.get('task', '')
                    story.append(Paragraph(f"<b>{z_title}:</b> {z_task}", body_style))
                    story.append(Spacer(1, 4))
                story.append(Spacer(1, 6))

        # ====================================================
        # LÖSUNGSBLATT & LEHRERKOPIE (SEPARATE SEITE)
        # ====================================================
        story.append(PageBreak())

        h_table_sol = build_header_table(
            title,
            "<b>Lösungsblatt &amp; Lehrerkopie (Musterlösungen)</b>",
            badge_style_sol,
            is_sol=True
        )
        story.append(h_table_sol)
        story.append(Spacer(1, 4))
        story.append(make_divider())
        story.append(Spacer(1, 8))

        # Full Hefteintrag summary for teacher
        full_heft = hefteintrag.get("level_b_notes") or hefteintrag.get("summary") or hefteintrag.get("level_a_notes")
        if full_heft and full_heft.strip():
            clean_full_heft = clean_reportlab_html(full_heft)
            heft_t = clean_reportlab_html(hefteintrag.get('title', 'Vollständiger Hefteintrag'))
            sol_box = Table([
                [Paragraph(f"<b>📌 {heft_t} (Vollständige Mitschrift)</b><br/><br/>{clean_full_heft}", body_style)]
            ], colWidths=[inch*7.25])
            sol_box.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
                ('BOX', (0,0), (-1,-1), 1.2, colors.HexColor("#64748b")),
                ('PADDING', (0,0), (-1,-1), 8),
            ]))
            story.append(sol_box)
            story.append(Spacer(1, 10))

        # Level A Solutions
        if pdf_variant in ["bundle", "basic"]:
            story.append(Paragraph("<b>Musterlösungen: Arbeitsblatt 1 (Basis / Level A)</b>", section_style))
            add_tasks_to_story(story, tasks_a, is_teacher=True, level_char="A")
            story.append(Spacer(1, 8))

        # Level B Solutions
        if pdf_variant in ["bundle", "profi"]:
            story.append(Paragraph("<b>Musterlösungen: Arbeitsblatt 2 (Profi / Level B)</b>", section_style))
            add_tasks_to_story(story, tasks_b, is_teacher=True, level_char="B")
            story.append(Spacer(1, 8))

            zusatzaufgaben = data.get("zusatzaufgaben", [])
            if zusatzaufgaben:
                story.append(Paragraph("<b>Musterlösungen: Experten-Aufgaben (Transfer)</b>", section_style))
                for i, z in enumerate(zusatzaufgaben):
                    z_title = z.get('title', f'Experten-Aufgabe {i+1}')
                    z_task = z.get('task', '')
                    story.append(Paragraph(f"<b>{z_title}:</b> {z_task}", body_style))
                    story.append(Paragraph("<b><font color='#15803d'>Lösungshinweis:</font></b> Individuelle Schülerlösung / Rechercheergebnis. Bewertung nach inhaltlicher Korrektheit und Fachbezug.", body_style))
                    story.append(Spacer(1, 4))

        # Level C (Inklusion & DaZ) solutions if requested
        include_level_c = data.get("include_level_c", False) or data.get("pdf_include_level_c", False)
        level_c = data.get("level_c", {})
        if include_level_c and level_c and level_c.get("tasks"):
            story.append(Paragraph("<b>Musterlösungen: Level C (Inklusion &amp; DaZ)</b>", section_style))
            add_tasks_to_story(story, level_c.get("tasks", []), is_teacher=True, level_char="C")

        # Build Document
        doc.build(story)
        pdf_data = buffer.getvalue()
        buffer.close()
        return pdf_data

    @staticmethod
    def generate_video_hefteintrag_pdf(data):
        """Generates companion worksheet for interactive videos."""
        title = data.get("title", "Interaktives Video")
        hefteintrag = data.get("full_hefteintrag") or data.get("hefteintrag", {}).get("summary", "")
        tasks = data.get("interactions", [])
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=inch*0.5,
            leftMargin=inch*0.5,
            topMargin=inch*0.45,
            bottomMargin=inch*0.45
        )
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('VidTitle', parent=styles['Title'], fontName='Helvetica-Bold', fontSize=16, leading=20, textColor=colors.HexColor("#0284c7"), alignment=0)
        body_style = ParagraphStyle('VidBody', parent=styles['Normal'], fontName='Helvetica', fontSize=9.5, leading=14, textColor=colors.HexColor("#334155"))
        section_style = ParagraphStyle('VidSec', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=12, leading=16, textColor=colors.HexColor("#0284c7"), spaceBefore=8, spaceAfter=4)

        story = []
        story.append(Paragraph(f"<b>{clean_reportlab_html(title)} – Video-Begleitblatt</b>", title_style))
        story.append(Paragraph("<b>Name:</b> ___________________________ &nbsp;&nbsp;&nbsp;&nbsp; <b>Klasse:</b> ______ &nbsp;&nbsp;&nbsp;&nbsp; <b>Datum:</b> ____________", body_style))
        story.append(Spacer(1, 8))

        if hefteintrag:
            story.append(Paragraph("📌 <b>Hefteintrag &amp; Kerninhalte des Videos</b>", section_style))
            box = Table([[Paragraph(clean_reportlab_html(hefteintrag), body_style)]], colWidths=[inch*7.25])
            box.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
                ('BOX', (0,0), (-1,-1), 1.0, colors.HexColor("#cbd5e1")),
                ('PADDING', (0,0), (-1,-1), 8),
            ]))
            story.append(box)
            story.append(Spacer(1, 8))

        if tasks:
            story.append(Paragraph("<b>Video-Aufgaben &amp; Kontrollfragen:</b>", section_style))
            for i, t in enumerate(tasks):
                t_q = t.get("question") or t.get("text") or f"Aufgabe {i+1}"
                story.append(Paragraph(f"<b>{i+1}. {clean_reportlab_html(t_q)}</b>", body_style))
                story.append(Spacer(1, 4))

        doc.build(story)
        pdf_data = buffer.getvalue()
        buffer.close()
        return pdf_data
