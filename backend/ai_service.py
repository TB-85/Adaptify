import os
import json
import logging
import io
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

    def generate_differentiated_content(
        self,
        file_content: bytes,
        mime_type: str,
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
            cache_hash = compute_cache_hash(file_content, subject, school_type, focus_topic, task_count, target_format, hefteintrag_topic)
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
    "summary": "Einheitlicher Klassen-Hefteintrag (1:1 ins Merkheft übertragbar im Format: 1. MERKREGEL, 2. SCHRITTE ZUR ANWENDUNG und 3. MUSTERBEISPIEL)",
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

        try:
            # Check if document is DOCX
            is_docx = (mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' 
                       or mime_type.endswith('document') 
                       or mime_type.endswith('docx'))
            
            if is_docx:
                extracted_text = extract_text_from_docx(file_content)
                logger.info("Successfully extracted text from DOCX locally.")
                contents = [
                    f"Hier ist der Text des hochgeladenen Word-Dokuments (.docx):\n\n{extracted_text}\n\n",
                    prompt
                ]
            else:
                part = types.Part.from_bytes(
                    data=file_content,
                    mime_type=mime_type
                )
                contents = [part, prompt]
            
            response = client.models.generate_content(
                model='gemini-3.5-flash-lite',
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=DifferentiatedContent,
                )
            )
            
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
            return result_json

        except Exception as e:
            logger.error(f"Error calling Gemini API: {e}", exc_info=True)
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
