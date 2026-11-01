import os
import json
import logging
import io
import tempfile
import time
import re
from urllib.parse import quote
import zipfile
import xml.etree.ElementTree as ET
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List, Optional

logger = logging.getLogger(__name__)

# Pydantic Schemas for Gemini Structured Outputs
class DiagnosticQuestion(BaseModel):
    question: str
    options: List[str]
    correct: int

class DiagnosticQuiz(BaseModel):
    questions: List[DiagnosticQuestion]

class Hefteintrag(BaseModel):
    title: str
    summary: str
    level_a_notes: str
    level_b_notes: str

class Zusatzaufgabe(BaseModel):
    title: str
    task: str

class Task(BaseModel):
    title: str
    text: str
    format: str
    hint: Optional[str] = ""
    explanation: Optional[str] = ""

class LevelContent(BaseModel):
    title: str
    tasks: List[Task]

class DifferentiatedContent(BaseModel):
    title: str
    extracted_text: str
    diagnostic: DiagnosticQuiz
    hefteintrag: Hefteintrag
    zusatzaufgaben: List[Zusatzaufgabe]
    level_a: LevelContent
    level_b: LevelContent
class InteractionAnswer(BaseModel):
    text: str
    correct: bool

class VideoInteraction(BaseModel):
    time_seconds: int
    time_formatted: str
    title: str
    format: str # 'Multiple Choice', 'Wahr/Falsch', 'Lückentext', 'Infobox'
    question: str
    answers: Optional[List[InteractionAnswer]] = None
    correct: Optional[bool] = None
    text_with_blanks: Optional[str] = None
    text: Optional[str] = None
    explanation: Optional[str] = None

class InteractiveVideoContent(BaseModel):
    title: str
    video_mode: str = "interactive_video"
    subject: str
    school_type: str
    interactions: List[VideoInteraction]



def parse_focus_topics(focus_topic_str: str, default_task_count: int = 2) -> tuple:
    """
    Parses expressions like '4 Textverständnis, 3 Fremdwörter, 2 Grafik' or '4x Textverständnis, 3x Fremdwörter'
    or plain comma-separated strings.
    Returns (expanded_topic_list, calculated_total_task_count).
    """
    import re
    if not focus_topic_str or not focus_topic_str.strip():
        return (["Grundaufgabe"], default_task_count)
    
    parts = [p.strip() for p in focus_topic_str.split(',') if p.strip()]
    expanded_topics = []
    has_explicit_counts = False
    
    for part in parts:
        match = re.match(r'^(\d+)\s*x?\s*(?:zu|für)?\s*(.+)$', part, re.IGNORECASE)
        if match:
            count = int(match.group(1))
            topic_name = match.group(2).strip()
            has_explicit_counts = True
            for _ in range(count):
                expanded_topics.append(topic_name)
        else:
            expanded_topics.append(part)
            
    if has_explicit_counts and len(expanded_topics) > 0:
        total_count = len(expanded_topics)
    else:
        total_count = default_task_count
        
    return (expanded_topics, total_count)

def extract_text_from_docx(docx_bytes):
    try:
        with zipfile.ZipFile(io.BytesIO(docx_bytes)) as docx:
            xml_content = docx.read('word/document.xml')
            root = ET.fromstring(xml_content)
            namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            texts = [node.text for node in root.findall('.//w:t', namespaces) if node.text]
            return " ".join(texts)
    except Exception as e:
        logger.error(f"Error extracting text from DOCX: {e}")
        return ""

class AIService:
    def __init__(self):
        # Load .env file in backend directory if present
        env_path = os.path.join(os.path.dirname(__file__), ".env")
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("GEMINI_API_KEY=") and not os.environ.get("GEMINI_API_KEY"):
                            os.environ["GEMINI_API_KEY"] = line.split("=", 1)[1].strip().strip('"\'')
            except Exception as e:
                logger.error(f"Failed to read .env file: {e}")

        DEFAULT_SERVER_KEY = "AQ.Ab8RN6IIli6Pmhc4lXUcD__SLmQ3pqlFeEOWQO7x5aoi8X9cEg"
        # The new SDK automatically picks up GEMINI_API_KEY from environment or fallback key
        self.api_key = os.environ.get("GEMINI_API_KEY") or DEFAULT_SERVER_KEY
        self.client = None
        if self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.error(f"Failed to initialize Gemini Client: {e}")


    def _prepare_gemini_contents(self, client, files: list, youtube_url: str = None) -> tuple:
        """
        Processes multi-modal attachments:
        - Videos (.mp4, .mov, etc.) are written to a temp file, uploaded to Gemini Files API, and polled until ACTIVE.
        - YouTube URLs have their oEmbed metadata and timestamped transcripts fetched via youtube_transcript_api.
        - Word DOCX files have their text extracted.
        - PDFs and images are passed as Part.from_bytes.
        Returns (contents_list, uploaded_gemini_files, temp_files_to_remove).
        """
        contents = []
        uploaded_gemini_files = []
        temp_files_to_remove = []

        # 1. Process YouTube URL if provided
        if youtube_url and youtube_url.strip():
            url = youtube_url.strip()
            vid_id = None
            yt_m = re.search(r'(?:v=|/|youtu\.be/|embed/)([0-9A-Za-z_-]{11})', url)
            if yt_m:
                vid_id = yt_m.group(1)

            # A. Fetch video title via oEmbed
            try:
                import httpx
                oembed_url = f"https://www.youtube.com/oembed?url={quote(url)}&format=json"
                resp = httpx.get(oembed_url, timeout=5.0)
                if resp.status_code == 200:
                    meta = resp.json()
                    title = meta.get('title', '')
                    author = meta.get('author_name', '')
                    contents.append(f"YouTube-Videotitel: '{title}' (Kanal: '{author}').")
                    logger.info(f"YouTube oEmbed metadata: title='{title}', author='{author}'")
            except Exception as e:
                logger.warning(f"Failed to fetch YouTube oEmbed: {e}")

            # B. Fetch transcript via youtube_transcript_api
            if vid_id:
                try:
                    from youtube_transcript_api import YouTubeTranscriptApi
                    ytt = YouTubeTranscriptApi()
                    transcript_pieces = ytt.fetch(vid_id)
                    if transcript_pieces:
                        lines = []
                        for snippet in transcript_pieces:
                            m, s = divmod(int(snippet.start), 60)
                            lines.append(f"[{m:02d}:{s:02d}] {snippet.text}")
                        transcript_text = "\n".join(lines)
                        if len(transcript_text) > 40000:
                            transcript_text = transcript_text[:40000] + "\n...[Transkript gekürzt]"
                        contents.append(f"VOLLSTÄNDIGE TONSPUR / TRANSKRIPT DES YOUTUBE-VIDEOS MIT ZEITSTEMPELN:\n\n{transcript_text}")
                        logger.info(f"Successfully retrieved YouTube transcript with {len(transcript_pieces)} segments!")
                except Exception as e:
                    logger.warning(f"Could not retrieve YouTube transcript for {vid_id}: {e}")

        # 2. Process uploaded files
        for f in (files or []):
            fc = f.get('content', b'')
            mt = f.get('mime_type', '')
            fname = f.get('filename', '')

            if not fc:
                continue

            is_video = (mt.startswith('video/') or 
                        any(fname.lower().endswith(ext) for ext in ['.mp4', '.mov', '.webm', '.m4v', '.avi']))

            if is_video:
                ext = os.path.splitext(fname)[1] or '.mp4'
                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                    tmp.write(fc)
                    tmp_path = tmp.name
                temp_files_to_remove.append(tmp_path)

                try:
                    logger.info(f"Uploading video file '{fname}' ({len(fc)} bytes) to Gemini Files API...")
                    gemini_file = client.files.upload(file=tmp_path)
                    uploaded_gemini_files.append(gemini_file)

                    # Poll until ACTIVE
                    poll_count = 0
                    while gemini_file.state.name == "PROCESSING" and poll_count < 35:
                        time.sleep(2)
                        gemini_file = client.files.get(name=gemini_file.name)
                        poll_count += 1
                        logger.info(f"Video '{fname}' processing state: {gemini_file.state.name} ({poll_count * 2}s)")

                    if gemini_file.state.name == "ACTIVE":
                        logger.info(f"Video file '{fname}' is ACTIVE in Gemini API and ready for multimodal analysis!")
                        contents.append(gemini_file)
                    else:
                        logger.warning(f"Video file state is '{gemini_file.state.name}', not ACTIVE.")
                except Exception as upload_err:
                    logger.error(f"Failed to upload video to Gemini Files API: {upload_err}", exc_info=True)
                    contents.append(f"Videodatei: {fname}")

            elif mt == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' or fname.endswith('.docx'):
                extracted = extract_text_from_docx(fc)
                if extracted:
                    contents.append(f"Extrahierter Text aus Word-Dokument ({fname}):\n\n{extracted}")
            elif mt == 'application/pdf':
                contents.append(types.Part.from_bytes(data=fc, mime_type='application/pdf'))
            elif mt.startswith('image/'):
                contents.append(types.Part.from_bytes(data=fc, mime_type=mt))
            elif mt.startswith('text/'):
                text_str = fc.decode('utf-8', errors='ignore')
                if text_str.strip():
                    contents.append(text_str)

        return contents, uploaded_gemini_files, temp_files_to_remove

    def _cleanup_gemini_files(self, client, uploaded_gemini_files: list, temp_files_to_remove: list):
        if client:
            for gf in (uploaded_gemini_files or []):
                try:
                    client.files.delete(name=gf.name)
                    logger.info(f"Deleted Gemini file: {gf.name}")
                except Exception as e:
                    logger.warning(f"Could not delete Gemini file {gf.name}: {e}")
        for tp in (temp_files_to_remove or []):
            try:
                if os.path.exists(tp):
                    os.remove(tp)
            except Exception:
                pass

    def generate_differentiated_content(
        self,
        files: list,
        context: str = "",
        target_format: str = "Lückentext",
        task_count: int = 1,
        subject: str = "Deutsch",
        school_type: str = "Grundschule",
        focus_topic: str = "",
        hefteintrag_topic: str = "",
        api_key: str = None
    ) -> dict:
        """
        Sends the uploaded image/PDF to Gemini and returns structured JSON
        matching the H5P differentiation template with multiple exercise topics,
        separate Hefteintrag topic, subject-specific adaptations, and Zusatzaufgaben.
        """
        # Check SQLite Generation Cache first
        try:
            from database import compute_cache_hash, get_cached_generation, set_cached_generation
            combined_content = b"".join([f['content'] for f in files])
            cache_hash = compute_cache_hash(combined_content, subject, school_type, focus_topic, task_count, target_format, hefteintrag_topic)
            cached_res = get_cached_generation(cache_hash)
            if cached_res:
                return cached_res
        except Exception as cache_e:
            logger.warning(f"Cache check error: {cache_e}")
            cache_hash = None

        # Determine client
        client = None
        if api_key and api_key.strip():
            try:
                client = genai.Client(api_key=api_key.strip())
            except Exception as e:
                logger.error(f"Failed to initialize Gemini Client with dynamic API key: {e}")
        
        if not client:
            client = self.client

        # If API key is missing, return mock data for demonstration
        if not client:
            logger.warning("Gemini Client not initialized (missing GEMINI_API_KEY). Returning high-quality mock data.")
            self._cleanup_gemini_files(client, uploaded_gemini_files, temp_files_to_remove)
            return self._get_mock_data(context, target_format, task_count, subject=subject, school_type=school_type, focus_topic=focus_topic, hefteintrag_topic=hefteintrag_topic)

        format_instruction = (
            "4. Formuliere die Aufgaben für Level A und Level B. Wähle für das Feld 'format' jedes Tasks das Format, "
            "das am besten zum jeweiligen Inhalt passt ('Lückentext', 'Drag the Words', 'Wahr/Falsch', 'Multiple Choice' oder 'Vokabelkarten'). "
            "Pädagogische Vorgabe für KI-Mix: Wähle für das niedrigere Niveau (Level A) einfachere Aufgaben-Formate, z. B. 'Drag the Words' anstelle eines 'Lückentextes', da vorgegebene Wörter leichter zuzuordnen sind. "
            "Für das höhere Niveau (Level B) verwende anspruchsvollere Formate, bei denen die Schüler selbst die Antworten tippen müssen (z. B. 'Lückentext'), oder nutze bei 'Multiple Choice' deutlich anspruchsvollere und mehrere Distraktoren. "
            "Variiere die Formate ganz gezielt, um die Übungen abwechslungsreich zu gestalten."
        ) if target_format == "KI-Mix" else (
            f"4. Formuliere die Aufgaben für Level A und Level B. Setze das Feld 'format' für alle Tasks zwingend auf '{target_format}'."
        )

        # Multi-subject / cross-curricular detection
        subjects_list = [s.strip() for s in subject.split(",") if s.strip()]
        is_cross_curricular = len(subjects_list) > 1
        
        if is_cross_curricular:
            subjects_str = " & ".join(subjects_list)
            subject_instruction = (
                f"FÄCHERÜBERGREIFENDER UNTERRICHT ({subjects_str}):\n"
                f"- Die Unterrichtseinheit verbindet folgende Schulfächer: {subjects_str}.\n"
                f"- Didaktischer Auftrag: Verknüpfe die Kompetenzen dieser Fächer gezielt miteinander (z. B. bei Deutsch + Mathematik: Leseverstehen/Textanalyse von Sachzusammenhängen kombiniert mit mathematischer Modellierung und Rechenschritten).\n"
                f"- Level A (Fördern): Bietet sprachliche Entlastung, Signalwort-Markierungen und gestützte Rechenschritte.\n"
                f"- Level B (Fordern): Erfordert das Formulieren eigener Begründungen/Erklärungen kombiniert mit anspruchsvollen Aufgaben."
            )
        else:
            subject_instruction = f"Schulfach: {subject}"

        focus_instruction = f"Übungsschwerpunkte: {focus_topic} (Erstelle gezielt Aufgaben für JEDEN dieser Schwerpunkte!)." if focus_topic else "Übungsschwerpunkte: Automatisch aus dem Dokument ermitteln."
        hefteintrag_instruction = f"Thema für den Hefteintrag / Merkkasten: {hefteintrag_topic}." if hefteintrag_topic else (f"Thema für den Hefteintrag: {focus_topic}" if focus_topic else "Thema für den Hefteintrag: Hauptthema des Dokuments.")

        prompt = f"""
Du bist eine professionelle Lehrkraft an einer {school_type} und ein H5P-Experte für Differenzierung im Unterricht.
Deine Aufgabe ist es, das hochgeladene Dokument (Buchseite, Arbeitsblatt, PDF) zu lesen (OCR) und darauf basierend ein differenziertes Lernpaket im JSON-Format für die Schulart '{school_type}' zu generieren.

Schulart: {school_type}
{subject_instruction}
{focus_instruction}
{hefteintrag_instruction}
Zusätzlicher Kontext (Klasse/Thema): {context}
Gewünschtes Standard-Aufgabenformat: {target_format}
Anzahl der zu generierenden Aufgaben pro Niveau: {task_count}

Generiere genau folgendes JSON-Schema:
{{
  "title": "Titel der Übung (z.B. {school_type} - {subject}: {focus_topic if focus_topic else 'Unterrichtspaket'})",
  "lehrplan_code": "Offizieller LehrplanPlus Bayern Code (z.B. 'M6 EG 2', 'D5 L1' oder 'E6 G1')",
  "lehrplan_competency": "Kurzbezeichnung der Kompetenz im Lehrplan (z. B. 'Anteile und Brüche im Alltag darstellen')",
  "extracted_text": "Der erkannte Text des Originaldokumentes sowie detaillierte Bildbeschreibungen von eventuell vorhandenen Illustrationen/Grafiken/Bildern zur Vorschau für die Lehrkraft",
  "diagnostic": {{
    "questions": [
      {{
        "question": "Einstiegsfrage 1 zur Diagnose des aktuellen Niveaus",
        "options": ["Richtige Antwortoption", "Falsche Antwortoption"],
        "correct": 0
      }},
      {{
        "question": "Einstiegsfrage 2 zur Diagnose",
        "options": ["Falsche Option", "Richtige Option"],
        "correct": 1
      }}
    ]
  }},
  "hefteintrag": {{
    "title": "ÜBERSCHRIFT ZWINGEND ALS W-FRAGE (z. B. 'Wie werte ich eine Grafik aus?' oder 'Wie berechne ich den Umfang?')",
    "summary": "Einheitlicher Klassen-Hefteintrag im HTML-Format (WICHTIG!). Aufbau zwingend so:\n<p><strong>1. Merke:</strong> [Hier der allgemeine Merksatz]</p>\n<p><strong>2. [Passende Frage zum Thema, z.B. Wie entstehen nun Erdöl, Erdgas oder Kohle?]:</strong> [Erklärung, wobei neue Gedanken, neue Punkte und neue Handlungen zwingend durch <br> getrennt in eine neue Zeile kommen, damit es übersichtlicher ist]</p>\n<p><strong>3. Beispiel:</strong> [Das Beispiel]</p>\nWichtige Begriffe im Text müssen zwingend mit <strong>fett</strong> markiert werden.",
    "level_a_notes": "",
    "level_b_notes": ""
  }},
  "zusatzaufgaben": [
    {{
      "title": "Experten-Aufgabe 1 (Transfer)",
      "task": "Weiterführende Knobel-, Reflexions- oder Kreativaufgabe für Schnellarbeiter"
    }},
    {{
      "title": "Experten-Aufgabe 2 (Erweiterung)",
      "task": "Anspruchsvolle Zusatzaufgabe zum Thema"
    }}
  ],
  "level_c": {{
    "title": "Level C - Inklusion & DaZ (Leichte Sprache)",
    "tasks": [
      {{
        "title": "Aufgabe in Leichter Sprache (Inklusion & DaZ)",
        "text": "Aufgabentext in Leichter Sprache mit visueller Wortschatz-Hilfe.",
        "format": "Drag the Words",
        "hint": "Lese-Hilfe / Wortschatz-Tipp",
        "explanation": "Erklärung in sehr einfachen Worten"
      }}
    ]
  }},
  "level_a": {{
    "title": "Level A - Grundlagen (Fördern)",
    "tasks": [
      {{
        "title": "Titel der Aufgabe (Verweise hier explizit auf einen der geforderten Übungsschwerpunkte)",
        "text": "Aufgabentext. WICHTIG FÜR LÜCKENTEXT / DRAG THE WORDS: Erstelle einen SUBSTANTIELLEN, ZUSAMMENHÄNGENDEN FLIESSTEXT aus 4 bis 6 Sätzen mit 4 bis 6 Lücken (*Lücke/Synonym1/Synonym2*). Bei Multiple-Choice: Frage\\n[ ] Falsch\\n[X] Richtig. Bei Wahr/Falsch zwingend exakt so: Aussage: [Behauptung]\\nAntwort: [Wahr/Falsch]",
        "format": "{ 'Drag the Words' if target_format == 'KI-Mix' else target_format }",
        "hint": "Hilfreicher Vorab-Tipp für Level A (z. B. 'Tipp: Schau in Zeile 2 nach Wörtern mit -ung')",
        "explanation": "Erklärung der richtigen Lösung bei einer falschen Antwort"
      }}
    ]
  }},
  "level_b": {{
    "title": "Level B - Vertiefung (Fordern)",
    "tasks": [
      {{
        "title": "Titel der Aufgabe (Verweise hier explizit auf einen der geforderten Übungsschwerpunkte)",
        "text": "Anspruchsvollerer Aufgabentext. WICHTIG FÜR LÜCKENTEXT / DRAG THE WORDS: Erstelle einen SUBSTANTIELLEN, ZUSAMMENHÄNGENDEN FLIESSTEXT aus 4 bis 6 Sätzen mit 4 bis 6 Lücken (*Lücke/Synonym1/Synonym2*). Format-Regeln exakt wie bei Level A beachten! Zwingend: Aussage: [Behauptung]\\nAntwort: [Wahr/Falsch]",
        "format": "{ 'Lückentext' if target_format == 'KI-Mix' else target_format }",
        "hint": "",
        "explanation": "Fachlicher Denkanstoß / Regelhinweis bei falscher Antwort"
      }}
    ]
  }}
}}

WICHTIGE ANWEISUNGEN:
1. Extrahiere den Kerninhalt des Textes aus dem Bild.
2. WICHTIG: Falls mehrere Übungsschwerpunkte angegeben sind ({focus_topic}), erstelle Aufgaben, die ALLE diese Schwerpunkte abdecken!
3. LÜCKENTEXT-REGELN, SYNONYME & EXAKTHEIT:
   - Erstelle bei 'Lückentext' und 'Drag the Words' KEINE Einzelsätze, sondern ZWINGEND zusammenhängende Fließtexte aus 4 bis 6 Sätzen mit mindestens 4 bis 6 Lücken.
   - SYNONYME: Um Frust bei Schülern zu vermeiden, MÜSSEN inhaltlich oder mathematisch mehrdeutige Lücken alle gängigen Synonyme und Schreibweisen enthalten, getrennt durch einen Schrägstrich `/` (z.B. `*teilen/dividieren*`, `*3,14/3.14*`, `*verdoppeln/mal zwei nehmen/multiplizieren*`, `*Zahl/Konstante/Kreiszahl*`).
   - MAL-ZEICHEN: Verwende in mathematischen Formeln und Texten NIEMALS das Sternchen '*' als Multiplikationszeichen (Malzeichen), da dies Lücken-Parser irritiert. Benutze stattdessen ZWINGEND das offizielle Multiplikationszeichen '·' (Mittelpunkt / Malpunkt).
   - FACHLICHE RICHTIGKEIT: Alle mathematischen Formeln, Berechnungen und logischen Aussagen MÜSSEN zu 100% fachlich korrekt und präzise sein. Prüfe deine Aufgaben vor der Ausgabe kritisch auf inhaltliche Fehler!
4. STRIKTE ANLEHNUNG AN DIE QUELLE:
   - Alle Aufgaben, Fragen, Merkkästen und Erklärungen MÜSSEN auf dem extrahierten Originaltext und den darin enthaltenen Zahlen, Definitionen und Beispielen basieren.
   - Nimm mathematische Bezeichnungen, Variablen (z. B. 'U' oder 'Uk', Pi-Symbol 'π' oder Wert '3,14') exakt so an, wie sie in der Vorlage stehen. Verändere keine fachlichen Bezeichnungen aus dem Ausgangstext!
   - Erfinde keine zusätzlichen, nicht behandelten Themen (z. B. Berechnung der Kreisfläche, wenn im Quelltext nur der Umfang erklärt wird).
5. STRIKTE AUFGABEN-FORMATIERUNGSREGELN FÜR DEN FELDINHALT 'text':
   - MULTIPLE CHOICE: Der Feldinhalt 'text' MUSS zwingend im folgenden Format sein:
     [Hier steht die Frage]
     [ ] [Eine falsche Option]
     [X] [Die richtige Option]
     [ ] [Eine andere falsche Option]
     (Generiere immer 3-4 Optionen, davon mindestens eine richtige mit [X] markiert).
   - WAHR/FALSCH: Der Feldinhalt 'text' MUSS zwingend im folgenden Format sein:
     Aussage: [Hier steht die Behauptung]
     Antwort: [Wahr oder Falsch]
   - VOKABELKARTEN: Der Feldinhalt 'text' MUSS zwingend im folgenden Format sein:
     Vorderseite: [Begriff oder Frage]
     Rückseite: [Erklärung oder Antwort]
6. DIDAKTISCHE STRUKTUR & REIHENFOLGE DER AUFGABEN:
   - Ordne die Aufgaben ZWINGEND in logische Themenblöcke!
   - BLOCK 1 (Zuerst): Textverständnis & Inhalt (Fragen zur Handlung, Aussagen zum Text).
   - BLOCK 2 (Danach): Grammatik, Wortarten, Rechtschreibung & Sprache (unter Verwendung der Wörter/Sätze aus dem Text).
   - Verhindere ein wildes Durcheinanderwürfeln der Themen, um die kognitive Belastung gering zu halten.
7. DIDAKTISCHE TIPPS- & FEEDBACK-REGEL:
   - Level A erhält für JEDE Aufgabe einen ermutigenden Vorab-Tipp (`hint`) UND eine einfache Erklärung bei Fehlern (`explanation`).
   - Level B erhält ZWINGEND KEINEN Vorab-Tipp (`hint` bleibt leer), aber ein anspruchsvolles Fehler-Feedback (`explanation`).
8. TRANSFERAUFGABE IN LEVEL B:
   - Formuliere die LETZTE Aufgabe von Level B (Vertiefung) zwingend als 'Transferaufgabe' (Titel z.B. 'Transfer & Anwendung - [Thema]').
   - Hier sollen die Schüler das erworbene Wissen/Regelwerk auf ein neues, bisher unbekanntes Beispiel anwenden oder kritisch hinterfragen.
9. Formuliere 2 Diagnosefragen, die das Verständnis prüfen.
10. Formuliere 2 motivierende Zusatzaufgaben für Schnellarbeiter (Experten-Aufgaben).
{format_instruction}
11. Antworte AUSSCHLIESSLICH im gültigen JSON-Format ohne Markdown-Wrapper.
"""

        uploaded_gemini_files = []
        temp_files_to_remove = []
        try:
            contents, uploaded_gemini_files, temp_files_to_remove = self._prepare_gemini_contents(
                client=client,
                files=files
            )
            contents.append(prompt)
            
            candidate_models = ['gemini-3.5-flash', 'gemini-3.5-flash-lite', 'gemini-3.1-flash-lite']
            response = None
            last_err = None
            for model_name in candidate_models:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=DifferentiatedContent,
                        )
                    )
                    if response and response.text:
                        logger.info(f"Successfully generated content using Gemini model '{model_name}'")
                        break
                except Exception as m_err:
                    logger.warning(f"Gemini model '{model_name}' failed: {m_err}. Trying next candidate model...")
                    last_err = m_err

            if not response or not response.text:
                raise last_err or Exception("All Gemini models failed")
            
            try:
                result_json = json.loads(response.text)
            except json.JSONDecodeError as jde:
                logger.warning(f"Initial JSON parse failed: {jde}. Attempting to escape invalid backslashes.")
                # Replace any backslash that is not a valid JSON escape sequence with a double backslash
                fixed_text = re.sub(r'\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', response.text)
                try:
                    result_json = json.loads(fixed_text)
                except Exception as inner_e:
                    logger.error(f"Failed to parse JSON even after escaping backslashes: {inner_e}")
                    raise jde
            if cache_hash and result_json:
                try:
                    set_cached_generation(cache_hash, result_json)
                except Exception as set_cache_err:
                    logger.warning(f"Failed to set cache: {set_cache_err}")
            self._cleanup_gemini_files(client, uploaded_gemini_files, temp_files_to_remove)
            return result_json

        except Exception as e:
            logger.error(f"Error calling Gemini API: {e}", exc_info=True)
            self._cleanup_gemini_files(client, uploaded_gemini_files, temp_files_to_remove)
            return self._get_mock_data(context, target_format, task_count, subject=subject, school_type=school_type, focus_topic=focus_topic, hefteintrag_topic=hefteintrag_topic, error_message=str(e))

    def refine_single_task(self, task_data: dict, instruction: str, subject: str = "Deutsch", school_type: str = "Grundschule", api_key: str = None) -> dict:
        """Refines a single task based on teacher instructions using Gemini or smart fallback."""
        effective_client = self.client
        if api_key and api_key.strip():
            try:
                effective_client = genai.Client(api_key=api_key.strip())
            except Exception as e:
                logger.error(f"Failed to init custom Gemini client for task refinement: {e}")

        prompt = f"""Du bist ein erfahrener Lehrplan-Experte.
Überarbeite folgende Schulaufgabe gezielt nach den Anweisungen der Lehrkraft:

Bisherige Aufgabe:
Titel: {task_data.get('title', '')}
Text: {task_data.get('text', '')}
Format: {task_data.get('format', 'Lückentext')}
Tipp: {task_data.get('hint', '')}
Erklärung: {task_data.get('explanation', '')}

Anweisung der Lehrkraft: {instruction}
Schulart: {school_type}, Fach: {subject}

Generiere genau dieses JSON:
{{
  "title": "Überarbeiteter Titel",
  "text": "Überarbeiteter Aufgabentext (bei Lückentext/Drag the Words Lücken mit *Sternchen* markieren)",
  "format": "{task_data.get('format', 'Lückentext')}",
  "hint": "Neuer oder angepasster Tipp",
  "explanation": "Neuer oder angepasster Erklärungstext"
}}
"""
        if effective_client:
            try:
                response = effective_client.models.generate_content(
                    model='gemini-3.5-flash-lite',
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.3
                    )
                )
                return json.loads(response.text)
            except Exception as e:
                logger.error(f"Refine task API call failed: {e}")

        # Smart Mock Fallback
        updated_title = f"{task_data.get('title', 'Aufgabe')}"
        updated_text = task_data.get('text', '') + f"\n\n*Zusatz-Schwerpunkt: {instruction}*"
        return {
            "title": updated_title,
            "text": updated_text,
            "format": task_data.get("format", "Lückentext"),
            "hint": task_data.get("hint", "") or f"💡 Tipp: Achte besonders auf {instruction}",
            "explanation": task_data.get("explanation", "")
        }

    def _get_mock_data(self, context: str = "", target_format: str = "KI-Mix", task_count: int = 2, subject: str = "Deutsch", school_type: str = "Grundschule", focus_topic: str = "", hefteintrag_topic: str = "", error_message: str = None) -> dict:
        """Returns beautiful default mock data in case API key is missing or fails."""
        topic_str = focus_topic if focus_topic else ("Textverständnis, Fremdwörter, Wortarten" if subject == "Deutsch" else ("Bruchrechnen" if subject == "Mathematik" else "Simple Past"))
        heft_str = hefteintrag_topic if hefteintrag_topic else (focus_topic if focus_topic else "Fremdwörter")
        
        # Clean topic_str from raw count numbers for a professional document title
        import re
        clean_title_topic = re.sub(r'\d+\s*x?\s*(?:zu|für)?\s*', '', topic_str).strip()
        clean_title_topic = re.sub(r'^\s*,\s*|\s*,\s*$', '', clean_title_topic)
        if not clean_title_topic or len(clean_title_topic) < 3:
            clean_title_topic = "Müll im Ozean - Der achte Kontinent" if subject == "Deutsch" else ("Bruchrechnen" if subject == "Mathematik" else "Grammar & Reading")

        title = clean_title_topic
        
        extracted = f"[DEMO-MODUS] Hier steht der extrahierte Text der Buchseite für {subject}.\n\n"
        if subject == "Mathematik":
            extracted += "Beispiel: 'Ein Kuchen wird in 8 gleiche Teile geschnitten. Anna isst 2 Teile, Ben isst 3 Teile. Welcher Anteil bleibt übrig?'\n"
        elif subject == "Deutsch":
            extracted += "Beispiel: 'Der kleine Hund läuft schnell durch den grünen Garten und bellt laut den Postboten an.'\n"
        else:
            extracted += "Beispiel: 'Yesterday, Sarah and Peter went to the school yard. Sarah played basketball, but Peter forgot his ball.'\n"
        
        extracted += "\nBildbeschreibung: Eine illustrative Grafik passend zum Thema."
        
        tasks_a = []
        tasks_b = []
        tasks_c = []
        formats_pool = ["Lückentext", "Drag the Words", "Wahr/Falsch", "Multiple Choice"]
        
        # Parse topics & count distribution (e.g. '4 Textverständnis, 3 Fremdwörter, 2 Grafik')
        topics_list, actual_count = parse_focus_topics(topic_str, task_count)

        for i in range(actual_count):
            fmt = formats_pool[i % len(formats_pool)] if target_format == "KI-Mix" else target_format
            t_focus = topics_list[i % len(topics_list)]
            
            is_last = (i == task_count - 1)
            b_title = f"Transfer & Anwendung - {t_focus}" if is_last else f"Fordern - {t_focus} (Aufgabe {i+1})"
            
            tasks_c.append({
                "title": f"Inklusion/DaZ - {t_focus} (Aufgabe {i+1})",
                "text": f"Leichte Sprache ({subject}):\nDas Wort *Hund* ist ein *Nomen*.\nDas Wort *läuft* ist ein *Verb*.",
                "format": "Drag the Words",
                "hint": "💡 Sprachhilfe: Verben beschreiben Handlungen (Was tut jemand?).",
                "explanation": "Sehr einfache Sprache unterstützt das Sprachverständnis."
            })

            if subject == "Mathematik":
                tasks_a.append({
                    "title": f"Fördern - {t_focus} (Aufgabe {i+1})",
                    "text": "Anna isst 2 von 8 Teilen. Das ist der Bruch *2/8* (zwei Achtel).\nDer verbleibende Rest ist *3/8* (drei Achtel).",
                    "format": fmt,
                    "hint": "💡 Tipp: Gehe von insgesamt 8 gleich großen Tortenstücken aus.",
                    "explanation": "2 von 8 Stücken bedeutet 2/8 (zwei Achtel)."
                })
                tasks_b.append({
                    "title": b_title,
                    "text": "Transferaufgabe: Ein Kuchen wird in 12 Teile geschnitten. Kürze den Anteil 3/12 auf *1/4*.\nDer Rest von 9/12 entspricht gekürzt *3/4*.",
                    "format": fmt,
                    "hint": "",
                    "explanation": "Gebe Brüche immer in ihrer am weitesten gekürzten Form an."
                })
            elif subject == "Deutsch":
                tasks_a.append({
                    "title": f"Fördern - {t_focus} (Aufgabe {i+1})",
                    "text": f"Aufgabe zum Schwerpunkt '{t_focus}':\n'Der' ist ein *Artikel*.\n'Hund' ist ein *Nomen*.\n'läuft' ist ein *Verb*.",
                    "format": fmt,
                    "hint": "💡 Tipp: Nomen werden großgeschrieben (z. B. Hund). Verben beschreiben Tun-Wörter.",
                    "explanation": "Nomen bezeichnen Lebewesen/Dinge, Verben beschreiben Handlungen."
                })
                tasks_b.append({
                    "title": b_title,
                    "text": f"Transferaufgabe zum Schwerpunkt '{t_focus}':\nWende die Regel auf folgenden neuen Satz an:\n'Das *Laufen* fällt ihm schwer.' -> 'Laufen' wird hier als *Nomen* gebraucht.",
                    "format": fmt,
                    "hint": "",
                    "explanation": "Durch den Signalartikel 'Das' wird das Verb 'laufen' nominalisiert."
                })
            else:
                tasks_a.append({
                    "title": f"Fördern - {t_focus} (Aufgabe {i+1})",
                    "text": f"Sarah und Peter *went* (gehen) gestern zum Schulhof.\nSarah *played* (spielen) Basketball.",
                    "format": fmt,
                    "hint": "💡 Tipp: 'yesterday' verlangt die Vergangenheitsform (Simple Past).",
                    "explanation": "'went' is the irregular past tense of 'to go'."
                })
                tasks_b.append({
                    "title": b_title,
                    "text": f"Transfer Task on '{t_focus}':\nApply the rule to a new context:\nBefore they *left* (leave) the playground, they *had found* (find) a lost key.",
                    "format": fmt,
                    "hint": "",
                    "explanation": "Use Past Perfect ('had found') for the action completed prior to leaving."
                })

        return {
            "title": title,
            "lehrplan_code": f"{'M6 EG 2' if subject == 'Mathematik' else ('D5 L1' if subject == 'Deutsch' else 'E6 G1')}",
            "lehrplan_competency": f"LehrplanPlus Bayern ({subject}): Kompetenzen im Bereich '{topic_str}' anwenden und reflektieren",
            "extracted_text": extracted,
            "diagnostic": {
                "questions": [
                    {
                        "question": f"Einstiegsdiagnose zu '{topics_list[0]}'",
                        "options": ["Richtige Antwort / Grundprinzip", "Falsche Antwort"],
                        "correct": 0
                    },
                    {
                        "question": f"Zweite Kontrollfrage zu '{topics_list[-1]}'",
                        "options": ["Ablenkende Antwort", "Exakte Lösung"],
                        "correct": 1
                    }
                ]
            },
            "hefteintrag": {
                "title": f"Wie wende ich die Regeln zu '{heft_str}' richtig an?",
                "summary": f"📌 WIE WENDE ICH DIE REGELN ZU {heft_str.upper()} RICHTIG AN?\n\n1. MERKREGEL:\nWichtigste Grundregel zum Thema '{heft_str}' kurz und prägnant erklärt.\n\n2. SCHRITTE ZUR ANWENDUNG:\n• Schritt 1: Gegebenes genau lesen & Signalwörter markieren.\n• Schritt 2: Passende Regel oder Formel anwenden.\n• Schritt 3: Ergebnis auf Plausibilität überprüfen.\n\n3. MUSTERBEISPIEL / MERKSATZ:\nAnschauliches Beispiel für den 1:1 Übertrag in das Merkheft.",
                "level_a_notes": "",
                "level_b_notes": ""
            },
            "zusatzaufgaben": [
                {
                    "title": "⭐ Experten-Aufgabe 1 (Transfer)",
                    "task": f"Verbinde das Thema '{heft_str}' mit einer eigenen Alltagssituation und erstelle ein Rätsel für deine Mitschüler."
                },
                {
                    "title": "⭐ Experten-Aufgabe 2 (Erweiterung)",
                    "task": f"Finde 3 weitere Beispiele zum Thema '{heft_str}' aus deiner eigenen Lektüre und begründe deine Auswahl."
                }
            ],
            "level_c": {
                "title": "Level C - Inklusion & DaZ (Leichte Sprache)",
                "tasks": tasks_c
            },
            "level_a": {
                "title": "Level A - Grundlagen (Fördern)",
                "tasks": tasks_a
            },
            "level_b": {
                "title": "Level B - Vertiefung (Fordern)",
                "tasks": tasks_b
            },
            "error": error_message
        }


    def generate_interactive_video_content(
        self,
        files: list,
        context: str = "",
        subject: str = "Informatik",
        school_type: str = "Mittelschule",
        task_count: int = 4,
        api_key: str = None,
        youtube_url: str = None
    ) -> dict:
        """
        Sends the uploaded material / text / video (or YouTube URL) to Gemini.
        The video's visual frames AND audio track are analyzed to autonomously detect
        the actual subject and topic, and generate high-precision interactive quiz checkpoints.
        """
        client = None
        if api_key and api_key.strip():
            try:
                client = genai.Client(api_key=api_key.strip(), http_options=types.HttpOptions(timeout=60000))
            except Exception as e:
                logger.error(f"Failed to initialize Gemini Client with dynamic API key: {e}")
        
        if not client:
            client = self.client

        # Derive intelligent fallback topic from filename or context if available
        first_fname = files[0].get('filename', '') if files else ''
        inferred_topic = context.strip() if context else ''
        if not inferred_topic and first_fname:
            base_fname = os.path.splitext(first_fname)[0].replace('_', ' ').replace('-', ' ').title()
            if any(k in base_fname.lower() for k in ['ip', 'netzwerk', 'informatik', 'router', 'server', 'lan', 'tcp']):
                inferred_topic = f"Informatik: {base_fname}"
                subject = "Informatik"
            else:
                inferred_topic = base_fname

        if not client:
            logger.warning("Gemini Client not initialized. Returning mock interactive video data.")
            return self._get_mock_interactive_video(inferred_topic, subject, school_type, task_count)

        prompt = f"""Du bist ein didaktischer Experte für digitale Bildung und interaktive Lernvideos (H5P Interactive Video) für bayerische Schulen ({school_type}).

ABSOLUTE PRIORITÄT: VIDEO-INHALTSANALYSE (BILD- UND TONSPUR)
1. Du hast das Original-Video (bzw. die Tonspur / das Transkript) vorliegen. Analysiere es von Anfang bis Ende gründlich und präzise:
   - BILDSPUR: Was ist auf dem Bildschirm oder an der Tafel zu sehen? (Folienüberschriften, Programmcode, Diagramme, Schemata, Formeln, hervorgehobene Begriffe).
   - TONSPUR: Was wird wörtlich erklärt? Welche Definitionen, Fachbegriffe, Beispiele und Schritte nennt die sprechende Person?
2. THEMEN- UND FACHERKENNUNG:
   - Ermittle das ECHTE Fach (z. B. Informatik, Mathematik, Physik, Biologie, Deutsch, Geschichte etc.) und das ECHTE Thema (z. B. 'IP-Adressen, IPv4 und Netzwerktechnik') direkt aus dem visuellen und gesprochenen Videoinhalt!
   - IGNORIERE jegliche abweichenden oder widersprüchlichen Voreinstellungen:
     Wenn das Video von IP-Adressen, Computernetzwerken oder Informatik handelt, erstelle ZWINGEND Fragen zu Informatik und IP-Adressen und AUF GAR KEINEN FALL zu Biologie, Wasserkreislauf oder anderen Fächern!
   - Die Bild- und Tonspur des Videos ist die EINZIGE und ABSOLUTE Wahrheitsquelle!
   - Setze das Feld 'subject' auf das erkannte Fach (z.B. 'Informatik') und 'title' auf einen prägnanten Titel zum erkannten Thema (z.B. 'Informatik: IP-Adressen und Subnetze').
3. ERSTELLE GENAU {task_count} INTERAKTIVE QUIZ-HALTEPUNKTE:
   - Die Fragen und Antworten MÜSSEN sich zu 100% auf die konkreten Erklärungen, Fakten und Beispiele aus DIESEM Video beziehen.
   - Verteile die Haltepunkte ('time_seconds') zeitlich passgenau über das Video an die Stellen, an denen der jeweilige Sachverhalt gerade erklärt wurde.
4. FRAGETYPEN & DIDAKTIK:
   - 'Multiple Choice': Genau 1 fachlich richtige Antwort und 2-3 plausible falsche Distraktoren.
   - 'Wahr/Falsch': Aussage zum Videoinhalt zur schnellen Lernzielkontrolle mit 'correct': true oder false.
   - 'Lückentext': Prägnanter Merksatz zum Video mit 1-2 Schlüsselwörtern in Sternchen (*Wort*).
   - 'Infobox': Wichtiger Merksatz oder Praxistipp zum aktuellen Videoabschnitt.
5. ERKLÄRUNGEN (FEEDBACK):
   - Jede Frage MUSS eine verständliche Erklärung ('explanation') enthalten, die nach dem Beantworten eingeblendet wird und den Zusammenhang aus dem Video nochmals kurz aufgreift.

Antworte ausschließlich im vorgegebenen JSON-Format:
"""

        uploaded_gemini_files = []
        temp_files_to_remove = []
        try:
            contents, uploaded_gemini_files, temp_files_to_remove = self._prepare_gemini_contents(
                client=client,
                files=files,
                youtube_url=youtube_url
            )
            contents.append(prompt)

            candidate_models = ['gemini-3.5-flash', 'gemini-3.5-flash-lite', 'gemini-3.1-flash-lite']
            last_err = None
            for model_name in candidate_models:
                try:
                    logger.info(f"Generating interactive video quiz with model '{model_name}'...")
                    response = client.models.generate_content(
                        model=model_name,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=InteractiveVideoContent,
                            temperature=0.2
                        )
                    )
                    if response and response.text:
                        parsed = json.loads(response.text)
                        parsed["video_mode"] = "interactive_video"
                        logger.info(f"Successfully generated interactive video quiz for subject='{parsed.get('subject')}', title='{parsed.get('title')}'")
                        return parsed
                except Exception as e:
                    logger.warning(f"Interactive video generation failed with model {model_name}: {e}")
                    last_err = e

            logger.error(f"All models failed for interactive video: {last_err}")
            return self._get_mock_interactive_video(inferred_topic, subject, school_type, task_count, error_message=str(last_err))
        finally:
            self._cleanup_gemini_files(client, uploaded_gemini_files, temp_files_to_remove)

    def _get_mock_interactive_video(self, context: str = "", subject: str = "Informatik", school_type: str = "Mittelschule", task_count: int = 4, error_message: str = None) -> dict:
        topic = context.strip() if context else ("IP-Adressen und Rechnernetze" if subject == "Informatik" else f"Grundlagen {subject}")
        is_ip_topic = any(k in topic.lower() for k in ['ip', 'netzwerk', 'informatik', 'subnetz', 'router'])
        
        if is_ip_topic:
            subject = "Informatik"
            interactions = [
                {
                    "time_seconds": 30,
                    "time_formatted": "00:30",
                    "title": "Aufbau einer IP-Adresse",
                    "format": "Multiple Choice",
                    "question": "Wozu dient eine IP-Adresse in einem Computernetzwerk?",
                    "answers": [
                        {"text": "Zur eindeutigen Adressierung und Erreichbarkeit von Geräten im Netzwerk", "correct": True},
                        {"text": "Zur dauerhaften Speicherung von Passwörtern", "correct": False},
                        {"text": "Zur Erhöhung der Prozessorgeschwindigkeit", "correct": False}
                    ],
                    "explanation": "Genau richtig! Jedes Gerät in einem Netzwerk benötigt eine eindeutige IP-Adresse, um Datenpakete empfangen und senden zu können."
                },
                {
                    "time_seconds": 90,
                    "time_formatted": "01:30",
                    "title": "IPv4 vs. IPv6",
                    "format": "Wahr/Falsch",
                    "question": "Eine klassische IPv4-Adresse besteht aus 32 Bit (4 Blöcken à 8 Bit, getrennt durch Punkte).",
                    "correct": True,
                    "explanation": "Richtig! IPv4-Adressen (z. B. 192.168.1.1) basieren auf 32 Bit und bieten etwa 4,3 Milliarden Adressen."
                },
                {
                    "time_seconds": 150,
                    "time_formatted": "02:30",
                    "title": "Lückentext-Merksatz",
                    "format": "Lückentext",
                    "question": "Ergänze das Schlüsselwort:",
                    "text_with_blanks": "Die *Subnetzmaske* bestimmt, welcher Teil einer IP-Adresse das Netzwerk und welcher den Host identifiziert.",
                    "explanation": "Ausgezeichnet! Die Subnetzmaske teilt die IP-Adresse in Netzwerk- und Hostanteil auf."
                },
                {
                    "time_seconds": 210,
                    "time_formatted": "03:30",
                    "title": "Zusammenfassung",
                    "format": "Infobox",
                    "question": "Merksatz",
                    "text": "Merke dir: Datenpakete im Internet finden ihren Weg durch Router anhand von Quell- und Ziel-IP-Adressen.",
                    "explanation": ""
                }
            ][:task_count]
        else:
            interactions = [
                {
                    "time_seconds": 30,
                    "time_formatted": "00:30",
                    "title": "Verständnisfrage 1",
                    "format": "Multiple Choice",
                    "question": f"Was ist der zentrale Kernpunkt von '{topic}'?",
                    "answers": [
                        {"text": "Die korrekte Definition und Anwendung", "correct": True},
                        {"text": "Eine rein theoretische Überlegung", "correct": False},
                        {"text": "Ein veraltetes Konzept ohne Nutzen", "correct": False}
                    ],
                    "explanation": f"Genau richtig! Das Verständnis von '{topic}' bildet die Basis für alle weiteren Schritte."
                },
                {
                    "time_seconds": 75,
                    "time_formatted": "01:15",
                    "title": "Wahr oder Falsch",
                    "format": "Wahr/Falsch",
                    "question": f"Die hier gezeigte Methode zu '{topic}' lässt sich direkt auf Alltagssituationen übertragen.",
                    "correct": True,
                    "explanation": "Richtig! Die Methode ist praxisnah und vielseitig anwendbar."
                },
                {
                    "time_seconds": 130,
                    "time_formatted": "02:10",
                    "title": "Lückentext-Merksatz",
                    "format": "Lückentext",
                    "question": "Ergänze das Schlüsselwort:",
                    "text_with_blanks": f"Beim Thema {topic} ist vor allem die *Struktur* und *Genauigkeit* entscheidend.",
                    "explanation": "Ausgezeichnet! Struktur und Genauigkeit führen zum Ziel."
                },
                {
                    "time_seconds": 190,
                    "time_formatted": "03:10",
                    "title": "Zusammenfassender Merksatz",
                    "format": "Infobox",
                    "question": "Merksatz",
                    "text": f"Merke dir: Alle Teilschritte von {topic} bauen logisch aufeinander auf. Wiederhole schwierige Abschnitte bei Bedarf.",
                    "explanation": ""
                }
            ][:task_count]

        return {
            "title": f"Interaktives Video: {topic}",
            "video_mode": "interactive_video",
            "subject": subject,
            "school_type": school_type,
            "interactions": interactions,
            "error": error_message
        }
