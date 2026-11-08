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
    text: str = Field(description="Antworttext für Multiple Choice")
    correct: bool = Field(description="True wenn dies die fachlich richtige Antwort ist, sonst False")

class VideoInteraction(BaseModel):
    time_seconds: int = Field(description="Exakter Haltepunkt in Sekunden. MUSS exakt 1 bis 3 Sekunden NACH dem Moment liegen, in dem die abgefragte Information im Video gerade vollständig erklärt oder gezeigt wurde!")
    time_formatted: str = Field(description="Haltepunkt formatiert als MM:SS (z. B. '01:25')")
    rewind_seconds: Optional[int] = Field(default=None, description="Sekunde im Video, an der die Erklärung begonnen hat. Dorthin springt das Video bei falscher Antwort automatisch zurück.")
    title: str = Field(description="Prägnanter Titel des Quiz-Stopps oder Merkkastens (z. B. '💡 Merkkasten: IPv4-Aufbau' oder 'Verständnis-Check: Subnetzmaske')")
    format: str = Field(description="Interaktionstyp: 'Multiple Choice', 'Wahr/Falsch', 'Lückentext' oder 'Infobox'")
    question: str = Field(description="Die konkrete Frage oder Handlungsanweisung, basierend auf dem gerade Gesehenen/Gehörten")
    answers: Optional[List[InteractionAnswer]] = Field(default=None, description="Für 'Multiple Choice': 3-4 Optionen mit genau 1 korrekten Antwort")
    correct: Optional[bool] = Field(default=None, description="Für 'Wahr/Falsch': True wenn die Aussage stimmt, sonst False")
    text_with_blanks: Optional[str] = Field(default=None, description="Für 'Lückentext': Didaktischer Merksatz mit dem gesuchten Schlüsselbegriff in Sternchen (z. B. 'Eine IPv4-Adresse besteht aus *32* Bit.')")
    text: Optional[str] = Field(default=None, description="Für 'Infobox' (Merkkasten): Zusammenfassung und Kernaussage des gerade gezeigten Abschnitts ('💡 Merke dir: ...')")
    hefteintrag_point: Optional[str] = Field(default=None, description="Der konkrete, prägnante Stichpunkt für diesen Haltepunkt (z. B. 'Eine IPv4-Adresse besteht aus vier 8-Bit-Zahlenblöcken (32 Bit), getrennt durch Punkte.'), der als wachsende Zeile in das digitale Tafelbild / Schulheft aufgenommen wird.")
    hefteintrag_step: Optional[str] = Field(default=None, description="Der wachsende kumulative Hefteintrag bis zu diesem Stopp (Thema + alle bisherigen Punkte + Aufforderung '✍️ Schreibe diesen Punkt jetzt in dein Heft!')")
    explanation: Optional[str] = Field(default=None, description="Verständliche didaktische Rückmeldung, die erklärt, warum die Antwort richtig ist und direkt auf das Video verweist")

class InteractiveVideoContent(BaseModel):
    title: str = Field(description="Prägnanter Titel der Lerneinheit, autonom ermittelt aus dem echten Videoinhalt (z. B. 'Informatik: IP-Adressen und Subnetze')")
    video_mode: str = "interactive_video"
    subject: str = Field(description="Das tatsächliche Schulfach des Videos (z. B. Informatik, Mathematik, Physik, Biologie, Deutsch, Geschichte)")
    school_type: str = Field(description="Schulart (z. B. Mittelschule, Realschule, Gymnasium)")
    full_hefteintrag: Optional[str] = Field(default=None, description="Das vollständige strukturierte Gesamt-Tafelbild / Hefteintrag für das gesamte Video zur dauerhaften Ergebnissicherung")
    interactions: List[VideoInteraction] = Field(description="Genau die geforderten Haltepunkte, chronologisch aufsteigend nach time_seconds geordnet")



def parse_teacher_context_directives(context: str = "", focus_topic: str = "", default_task_count: int = 5, default_format: str = "KI-Mix"):
    """
    Universally parses all teacher directives from the detail box (context) and focus_topic:
    - Topic distribution & task counts (e.g. '5 Fragen zum Text und 15 zu den unterstrichenen Wörtern', 'Textverständnis: 5, Wortarten: 10')
    - Proportions ('Hälfte X, Hälfte Y')
    - Format constraints ('Keine Multiple Choice', 'Nur Lückentexte und Zuordnungen', 'Als Vokabelkarten')
    - Content/Source focus ('Nur unterstrichene Wörter', 'Nur Abschnitt 2')
    - Pedagogical/Language directives ('DaZ einfache Sprache', 'Kurze Sätze')
    """
    ctx = (context or "").strip()
    foc = (focus_topic or "").strip()
    
    # Normalize hyphens and punctuation for directive matching
    norm_text = re.sub(r'[-_]', ' ', f"{ctx} {foc}".lower())
    
    # 1. Format constraints & exclusions
    forbidden_formats = []
    if any(p in norm_text for p in ["keine multiple choice", "kein multiple choice", "keine mc", "kein mc", "ohne multiple choice"]):
        forbidden_formats.append("Multiple Choice")
    if any(p in norm_text for p in ["keine lückentexte", "kein lückentext", "ohne lücken", "ohne lückentext"]):
        forbidden_formats.append("Lückentext")
    if any(p in norm_text for p in ["kein freies schreiben", "keine freitexte", "kein essay", "kein aufsatz", "ohne freies schreiben"]):
        forbidden_formats.append("Freies Schreiben")
    if any(p in norm_text for p in ["kein wahr falsch", "keine wahr falsch", "ohne wahr falsch"]):
        forbidden_formats.append("Wahr/Falsch")

    forced_format = None
    if any(p in norm_text for p in ["nur lückentext", "nur lückentexte", "ausschließlich lückentext"]):
        forced_format = "Lückentext"
    elif any(p in norm_text for p in ["nur multiple choice", "nur mc", "ausschließlich multiple choice"]):
        forced_format = "Multiple Choice"
    elif any(p in norm_text for p in ["nur drag the words", "nur drag and drop", "nur drag drop", "nur wortspeicher"]):
        forced_format = "Drag the Words"
    elif any(p in norm_text for p in ["nur tabellen zuordnung", "nur tabellenzuordnung", "nur tabellen"]):
        forced_format = "Tabellen-Zuordnung"
    elif any(p in norm_text for p in ["nur wahr falsch", "nur wahr oder falsch"]):
        forced_format = "Wahr/Falsch"
    elif any(p in norm_text for p in ["als vokabelkarten", "nur vokabelkarten", "vokabelkarten erstellen"]):
        forced_format = "Vokabelkarten"
    elif any(p in norm_text for p in ["nur wörter markieren", "nur mark the words"]):
        forced_format = "Wörter markieren"

    # Helper to clean meta phrases from topic strings
    def clean_topic_str(t: str) -> str:
        s = t.strip()
        meta_sub = [
            r'keine?\s+multiple[\s\-]+choice', r'kein\s+mc', r'keine\s+mc', r'ohne\s+multiple[\s\-]+choice',
            r'nur\s+lückentext\w*', r'nur\s+multiple[\s\-]+choice', r'nur\s+drag[\s\-]+the[\s\-]+words',
            r'nur\s+drag[\s\-]+and[\s\-]+drop', r'nur\s+wahr[\s\-]+falsch',
            r'daz\s+einfache\s+sprache', r'einfache\s+sprache', r'leichte\s+sprache',
            r'kurze\s+sätze', r'keine\s+schachtelsätze',
            r'fokus\s+auf\s+', r'schwerpunkt\s+auf\s+', r'fragen\s+zu[mr]?\s+', r'aufgaben\s+zu[mr]?\s+',
            r'^(?:zu[mr]?|zm|für|über|an|in|den|dem|die|das)\s+',
            r'^(?:nur\s+fragen\s+zu[mr]?\s+|nur\s+aufgaben\s+zu[mr]?\s+)'
        ]
        for pat in meta_sub:
            s = re.sub(pat, '', s, flags=re.IGNORECASE).strip()
        return s.strip('.:,; -')

    # 2. Topic Distribution Parsing
    # Look first in context, but if context is only meta instructions, use focus_topic
    dist_str = ""
    has_ctx_distribution = bool(
        re.search(r'\d+\s*(?:x|mal)?\s*(?:fragen?|aufgaben?|übungen?)?', ctx, re.IGNORECASE) or
        re.search(r'[:=]\s*\d+', ctx) or
        ("hälfte" in ctx.lower()) or
        ("," in ctx or " und " in ctx or " + " in ctx or " & " in ctx)
    )
    
    if has_ctx_distribution and ctx:
        dist_str = ctx
    elif foc:
        dist_str = foc
    else:
        dist_str = ctx

    distribution = {}
    expanded_topics = []
    has_explicit_counts = False
    
    # Check for "Hälfte X, Hälfte Y"
    half_match = re.search(r'hälfte\s+(.+?)(?:,\s*|\s+und\s+|\s*\+\s*)(?:die\s+andere\s+)?hälfte\s+(.+)', dist_str, re.IGNORECASE)
    if half_match:
        top_a = clean_topic_str(half_match.group(1))
        top_b = clean_topic_str(half_match.group(2))
        count_half = max(1, default_task_count // 2)
        count_rem = default_task_count - count_half
        distribution[top_a] = count_half
        distribution[top_b] = count_rem
        expanded_topics = [top_a] * count_half + [top_b] * count_rem
        has_explicit_counts = True
    else:
        # Protect phrases like "Abschnitt 1 und 2", "Seite 3 und 4" from splitting
        cleaned_dist = re.sub(r'^(?:insgesamt|gesamt|insg\.?)\s*\d*\s*(?:fragen?|aufgaben?|übungen?)?[:\s,-]*', '', dist_str, flags=re.IGNORECASE).strip()
        cleaned_dist = re.sub(
            r'((?:abschnitt|absatz|kapitel|seite)\s+\d+)\s+und\s+(\d+)',
            r'\1_UND_\2',
            cleaned_dist,
            flags=re.IGNORECASE
        )
        split_pattern = r'(?:\s*,\s*|\s*;\s*|\s*\+\s*|\s+und\s+|\s*&\s*|[\r\n]+)'
        raw_parts = [p.strip() for p in re.split(split_pattern, cleaned_dist, flags=re.IGNORECASE) if p.strip()]

        for part in raw_parts:
            # Restore protected _UND_
            part_restored = part.replace('_UND_', ' und ')
            p_clean = clean_topic_str(part_restored)
            
            # If after cleaning nothing is left, or it's a pure constraint phrase with no numbers, skip
            if not p_clean or (len(p_clean) < 2 and not re.search(r'\d+', part_restored)):
                continue

            # Pattern A: "5 fragen zum Textverständnis" or "5x Wortarten"
            m_a = re.match(
                r'^(\d+)\s*(?:x|mal)?\s*(?:fragen?|aufgaben?|übungen?)?\s*(?:zu[mr]?|zm|für|über|an|in|den|die|das)?\s*(.+)$',
                part_restored,
                re.IGNORECASE
            )
            # Pattern B: "Textverständnis: 5" or "Textverständnis (5)"
            m_b = re.match(
                r'^(.+?)\s*[:=\(]\s*(\d+)\s*(?:x|mal)?\s*(?:fragen?|aufgaben?)?\)?$',
                part_restored,
                re.IGNORECASE
            )
            if m_a and (int(m_a.group(1)) > 40 or re.match(r'(?:min|minuten|std|stunden|klasse|jahrgang|jahre|seite|seiten|uhr|prozent|euro)\b', m_a.group(2).strip(), re.IGNORECASE)):
                m_a = None
            if m_a:
                count = int(m_a.group(1))
                clean_topic = clean_topic_str(m_a.group(2))
                if clean_topic:
                    has_explicit_counts = True
                    distribution[clean_topic] = distribution.get(clean_topic, 0) + count
                    for _ in range(count):
                        expanded_topics.append(clean_topic)
            elif m_b:
                count = int(m_b.group(2))
                clean_topic = clean_topic_str(m_b.group(1))
                if clean_topic:
                    has_explicit_counts = True
                    distribution[clean_topic] = distribution.get(clean_topic, 0) + count
                    for _ in range(count):
                        expanded_topics.append(clean_topic)
            else:
                if p_clean and len(p_clean) > 2 and not any(meta in p_clean.lower() for meta in ["multiple choice", "lückentext", "daz", "sprache"]):
                    distribution[p_clean] = distribution.get(p_clean, 0) + 1
                    expanded_topics.append(p_clean)

    if has_explicit_counts and len(expanded_topics) > 0:
        total_task_count = len(expanded_topics)
    else:
        total_task_count = default_task_count
        if not expanded_topics:
            fallback_topic = foc if foc else (clean_topic_str(ctx) if clean_topic_str(ctx) else "Grundaufgabe")
            expanded_topics = [fallback_topic] * total_task_count
            distribution[fallback_topic] = total_task_count

    # 3. Content source targeting directives
    content_directives = []
    if any(w in norm_text for w in ["unterstrichen", "unterstreichung"]):
        content_directives.append("Arbeite zwingend mit den im Originaltext UNTERSTRICHENEN Wörtern bzw. Sätzen. Zitiere den jeweiligen Satz vollständig und hebe das Zielwort hervor (z. B. <u>Wort</u>).")
    if any(w in norm_text for w in ["gelb markiert", "grün markiert", "rot markiert", "farbig markiert", "markierten wörtern"]):
        content_directives.append("Konzentriere dich vorrangig auf die im Dokument FARBIG MARKIERTEN Textstellen und Begriffe.")
    if any(w in norm_text for w in ["fettgedruckt", "fett gedruckt", "fett formatierte"]):
        content_directives.append("Beziehe dich vorrangig auf die FETTGEDRUCKTEN Fachbegriffe und Kernaussagen.")
    abschnitt_match = re.search(r'(?:nur\s+)?(abschnitt\s+\d+(?:\s*(?:und|-|bis)\s*\d+)?|absatz\s+\d+(?:\s*(?:und|-|bis)\s*\d+)?)', norm_text)
    if abschnitt_match:
        content_directives.append(f"Beschränke die Fragen inhaltlich streng auf {abschnitt_match.group(1)}.")

    # 4. Pedagogical & linguistic directives
    pedagogical_directives = []
    if any(w in norm_text for w in ["daz", "deutsch als zweitsprache", "leichte sprache", "einfache sprache", "sprachhilfe", "a2", "b1"]):
        pedagogical_directives.append("DAZ & SPRACHSENSIBILITÄT: Verwende klare, kurze Hauptsätze, vermeide unnötige Schachtelsätze und Fremdwörter. Gib bei Level A & C zusätzliche Vokabelhilfen und eindeutige Signalwörter.")
    if any(w in norm_text for w in ["inklusion", "förderschule", "förderbedarf", "starke entlastung"]):
        pedagogical_directives.append("INKLUSION: Achte auf besonders niedrigschwellige Einstiege, visuelle Unterstützung und vorgegebene Auswahlwörter (Wortspeicher).")
    if any(w in norm_text for w in ["gymnasium", "transfer", "anspruchsvoll", "begründe"]):
        pedagogical_directives.append("HÖHERE ANFORDERUNG: Fordere bei Level B vertiefte Begründungen, Textanalysen und selbstständige Begriffstransfers.")
    if any(w in norm_text for w in ["auf englisch", "in english", "englische aufgabenstellung"]):
        pedagogical_directives.append("SPRACHE: Formuliere alle Aufgabenstellungen, Fragen und Optionen auf Englisch.")

    return {
        "raw_context": ctx,
        "raw_focus": foc,
        "total_task_count": total_task_count,
        "distribution": distribution,
        "expanded_topics": expanded_topics,
        "has_explicit_counts": has_explicit_counts,
        "forbidden_formats": forbidden_formats,
        "forced_format": forced_format,
        "content_directives": content_directives,
        "pedagogical_directives": pedagogical_directives
    }


def parse_focus_topics(focus_topic_str: str, default_task_count: int = 2) -> tuple:
    """
    Parses expressions like:
    - '5 fragen zm textverständnis und 15 fragen zu den unterstrichenen wörtern'
    - '4 Textverständnis, 3 Fremdwörter, 2 Grafik'
    - '4x Textverständnis & 3x Grammatik'
    - '5 Fragen zum Text + 15 Aufgaben zu den unterstrichenen Wörtern'
    Returns (expanded_topic_list, calculated_total_task_count, topic_distribution_dict).
    """
    import re
    default_count = max(1, default_task_count)
    if not focus_topic_str or not focus_topic_str.strip():
        return (["Grundaufgabe"] * default_count, default_count, {"Grundaufgabe": default_count})

    raw_str = focus_topic_str.strip()
    raw_str = re.sub(r'^(?:insgesamt|gesamt|insg\.?)\s*\d*\s*(?:fragen?|aufgaben?|übungen?)?[:\s,-]*', '', raw_str, flags=re.IGNORECASE).strip()
    
    split_pattern = r'(?:\s*,\s*|\s*;\s*|\s*\+\s*|\s+und\s+|\s*&\s*|[\r\n]+)'
    raw_parts = [p.strip() for p in re.split(split_pattern, raw_str, flags=re.IGNORECASE) if p.strip()]

    expanded_topics = []
    distribution = {}
    has_explicit_counts = False

    for part in raw_parts:
        match = re.match(
            r'^(\d+)\s*(?:x|mal)?\s*(?:fragen?|aufgaben?|übungen?)?\s*(?:zu[mr]?|zm|für|über|den|die|das)?\s*(.+)$',
            part,
            re.IGNORECASE
        )
        if match:
            count = int(match.group(1))
            raw_topic = match.group(2).strip()
            clean_topic = re.sub(r'^(?:zu[mr]?|zm|für|über|in|an|den|dem|die|das)\s+', '', raw_topic, flags=re.IGNORECASE).strip()
            clean_topic = clean_topic.rstrip('.:,; ')
            if clean_topic:
                has_explicit_counts = True
                distribution[clean_topic] = distribution.get(clean_topic, 0) + count
                for _ in range(count):
                    expanded_topics.append(clean_topic)
        else:
            clean_part = re.sub(r'^(?:zu[mr]?|zm|für|über|in|an|den|dem|die|das)\s+', '', part, flags=re.IGNORECASE).strip()
            clean_part = clean_part.rstrip('.:,; ')
            if clean_part:
                distribution[clean_part] = distribution.get(clean_part, 0) + 1
                expanded_topics.append(clean_part)

    if has_explicit_counts and len(expanded_topics) > 0:
        total_count = len(expanded_topics)
    else:
        total_count = default_count
        if len(expanded_topics) == 0:
            expanded_topics = ["Grundaufgabe"] * total_count

    return (expanded_topics, total_count, distribution)

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


    def _prepare_gemini_contents(self, client, files: list, youtube_url: str = None, video_duration: int = None) -> tuple:
        """
        Processes multi-modal attachments:
        - Videos (.mp4, .mov, etc.) are written to a temp file, uploaded to Gemini Files API, and polled until ACTIVE.
        - YouTube URLs have their oEmbed metadata, exact duration and timestamped transcripts fetched.
        - Word DOCX files have their text extracted.
        - PDFs and images are passed as Part.from_bytes.
        Returns (contents_list, uploaded_gemini_files, temp_files_to_remove, detected_duration_sec).
        """
        contents = []
        uploaded_gemini_files = []
        temp_files_to_remove = []
        detected_duration_sec = int(video_duration) if (video_duration and int(video_duration) > 0) else None

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

            # B. Extract exact YouTube length in seconds from YouTube watch page
            if vid_id and not detected_duration_sec:
                try:
                    import httpx
                    yt_watch_resp = httpx.get(
                        f"https://www.youtube.com/watch?v={vid_id}",
                        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'},
                        timeout=4.0
                    )
                    if yt_watch_resp.status_code == 200:
                        m_len = re.search(r'"lengthSeconds":"(\d+)"', yt_watch_resp.text)
                        if m_len:
                            detected_duration_sec = int(m_len.group(1))
                            logger.info(f"Extracted YouTube exact lengthSeconds: {detected_duration_sec}s")
                except Exception as yt_err:
                    logger.warning(f"Could not scrape YouTube duration: {yt_err}")

            # C. Fetch transcript via youtube_transcript_api (multi-language & timestamp aware)
            if vid_id:
                try:
                    from youtube_transcript_api import YouTubeTranscriptApi
                    ytt = YouTubeTranscriptApi()
                    tlist = ytt.list(vid_id)
                    selected_transcript = None
                    try:
                        selected_transcript = tlist.find_transcript(['de', 'de-DE', 'de-AT', 'de-CH', 'en', 'en-US', 'en-GB'])
                    except Exception:
                        for tr in tlist:
                            selected_transcript = tr
                            break

                    if selected_transcript:
                        transcript_pieces = selected_transcript.fetch()
                        lines = []
                        max_timestamp = 0
                        for snippet in transcript_pieces:
                            start_sec = int(snippet.start)
                            dur = getattr(snippet, 'duration', 0) or 0
                            end_sec = int(snippet.start + dur)
                            if end_sec > max_timestamp:
                                max_timestamp = end_sec
                            m, s = divmod(start_sec, 60)
                            lines.append(f"[{m:02d}:{s:02d}] {snippet.text}")
                        transcript_text = "\n".join(lines)
                        if len(transcript_text) > 40000:
                            transcript_text = transcript_text[:40000] + "\n...[Transkript gekürzt]"

                        if not detected_duration_sec and max_timestamp > 0:
                            detected_duration_sec = max_timestamp

                        m_end, s_end = divmod(max_timestamp, 60)
                        contents.append(
                            f"VOLLSTÄNDIGE TONSPUR / TRANSKRIPT DES YOUTUBE-VIDEOS MIT ZEITSTEMPELN "
                            f"(Gesamtlänge ca. {m_end:02d}:{s_end:02d} / {max_timestamp} Sekunden):\n\n{transcript_text}"
                        )
                        logger.info(f"Successfully retrieved YouTube transcript in '{selected_transcript.language_code}' with {len(transcript_pieces)} segments (~{m_end:02d}:{s_end:02d})!")
                except Exception as e:
                    logger.warning(f"Could not retrieve YouTube transcript for {vid_id}: {e}")

        # 2. Process uploaded files
        for f in (files or []):
            fc = f.get('content', b'')
            mt = f.get('mime_type', '')
            fname = f.get('filename', '')
            fpath = f.get('file_path')

            if not fc and not fpath:
                continue

            is_video = (mt.startswith('video/') or 
                        any(fname.lower().endswith(ext) for ext in ['.mp4', '.mov', '.webm', '.m4v', '.avi']))

            if is_video:
                if fpath and os.path.exists(fpath):
                    tmp_path = fpath
                else:
                    ext = os.path.splitext(fname)[1] or '.mp4'
                    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                        tmp.write(fc)
                        tmp_path = tmp.name
                    temp_files_to_remove.append(tmp_path)

                try:
                    fsize = os.path.getsize(tmp_path) if os.path.exists(tmp_path) else (len(fc) if fc else 0)
                    logger.info(f"Uploading video file '{fname}' ({fsize} bytes) to Gemini Files API...")
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
                        if not detected_duration_sec:
                            try:
                                import subprocess
                                ff_res = subprocess.run(
                                    ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', tmp_path],
                                    capture_output=True, text=True, timeout=5
                                )
                                if ff_res.returncode == 0 and ff_res.stdout.strip():
                                    detected_duration_sec = int(float(ff_res.stdout.strip()))
                            except Exception as ff_err:
                                logger.debug(f"Could not probe video duration: {ff_err}")

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

        if detected_duration_sec and detected_duration_sec > 0:
            m_dur, s_dur = divmod(detected_duration_sec, 60)
            contents.append(
                f"STRENGSTE REGEL ZUR LAUFZEIT: Die Gesamtlänge dieses Videos beträgt EXAKT {m_dur:02d}:{s_dur:02d} ({detected_duration_sec} Sekunden). "
                f"Der allerletzte Haltepunkt darf HÖCHSTENS bei Sekunde {max(15, detected_duration_sec - 10)} liegen! Jeder Haltepunkt danach ist ungültig!"
            )
            logger.info(f"Target video duration verified: {m_dur:02d}:{s_dur:02d} ({detected_duration_sec}s)")

        return contents, uploaded_gemini_files, temp_files_to_remove, detected_duration_sec

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
        api_key: str = None,
        differentiation_mode: str = "differentiated"
    ) -> dict:
        """
        Sends the uploaded image/PDF to Gemini and returns structured JSON
        matching the H5P differentiation template with multiple exercise topics,
        separate Hefteintrag topic, subject-specific adaptations, and Zusatzaufgaben.
        Supports differentiation_mode == 'direct' for 1:1 worksheet transcription.
        """
        # Check SQLite Generation Cache first
        try:
            from database import compute_cache_hash, get_cached_generation, set_cached_generation
            combined_content = b"".join([f.get('content') or b"" for f in files])
            cache_hash = compute_cache_hash(combined_content, subject, school_type, focus_topic, task_count, target_format, f"{hefteintrag_topic}|{differentiation_mode}")
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
            return self._get_mock_data(context, target_format, task_count, subject=subject, school_type=school_type, focus_topic=focus_topic, hefteintrag_topic=hefteintrag_topic, differentiation_mode=differentiation_mode)

        format_instruction = (
            "4. Formuliere die Aufgaben für Level A und Level B. Wähle für das Feld 'format' jedes Tasks das Format, "
            "das am besten zum jeweiligen Inhalt passt ('Lückentext', 'Drag the Words', 'Tabellen-Zuordnung', 'Wörter markieren', 'Freies Schreiben', 'Wahr/Falsch', 'Multiple Choice' oder 'Vokabelkarten'). "
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

        # Alle Vorgaben der Lehrkraft (Detail-Box + Schwerpunkt) einheitlich auswerten
        directives = parse_teacher_context_directives(context, focus_topic, task_count)
        topic_dist = directives["distribution"]
        if directives["has_explicit_counts"]:
            task_count = directives["total_task_count"]
        if directives["forced_format"]:
            target_format = directives["forced_format"]

        extra_rules = []
        if directives["forbidden_formats"]:
            extra_rules.append("VERBOTENE AUFGABENFORMATE (laut Lehrkraft): " + ", ".join(directives["forbidden_formats"]) + ". Verwende diese Formate in KEINER Aufgabe.")
        if directives["forced_format"]:
            extra_rules.append(f"AUSSCHLIESSLICH dieses Aufgabenformat verwenden: {directives['forced_format']}.")
        extra_rules.extend(directives["content_directives"])
        extra_rules.extend(directives["pedagogical_directives"])
        if context and context.strip():
            extra_rules.append(f"Originalwortlaut der Lehrkraft (verbindlich, jede Angabe vollständig umsetzen): \"{context.strip()}\"")
        extra_block = ("\nZUSÄTZLICHE VERBINDLICHE VORGABEN DER LEHRKRAFT:\n" + "\n".join(f"- {r}" for r in extra_rules)) if extra_rules else ""

        if directives["has_explicit_counts"] and topic_dist:
            dist_lines = []
            for top_name, top_count in topic_dist.items():
                low = top_name.lower()
                is_reading = any(w in low for w in ["textverst", "leseverst", "reading", "comprehension", "sachtext", "inhalt", "fragen zum text"])
                is_underlined = any(w in low for w in ["unterstrichen", "markiert", "wortart", "grammatik", "wörter", "pronomen", "nomen", "verben"])
                if is_reading:
                    dist_lines.append(f"- {top_count}x {top_name}: REINE INHALTLICHE VERSTÄNDNISFRAGEN zum Sinn, zu Fakten, Zusammenhängen und Details des Textes (KEINE Grammatik!). Jede Frage muss sich auf einen anderen Textaspekt beziehen (KEINE Dopplungen!).")
                elif is_underlined:
                    dist_lines.append(f"- {top_count}x {top_name}: Grammatik-, Wortarten- und Bestimmungsaufgaben zu den im Text unterstrichenen oder vorkommenden Wörtern! Jede Aufgabe muss den konkreten Beispielsatz aus dem Text zitieren und das Zielwort hervorheben (z. B. mit <u>Wort</u>). Biete abwechslungsreiche Übungen (Wortarten bestimmen, Grundform/Infinitiv, Pronomen einsetzen, Wörter markieren, Tabellen-Zuordnung).")
                else:
                    dist_lines.append(f"- {top_count}x {top_name}: Gezielte, inhaltlich eigenständige Aufgaben ausschließlich zu diesem Schwerpunkt.")
            dist_desc = "\n".join(dist_lines)
            focus_instruction = (
                f"STRIKTE VORGABE FÜR DIE AUFGABEN-VERTEILUNG (GESAMT {task_count} AUFGABEN PRO NIVEAU):\n"
                f"Die Lehrkraft hat eine EXAKTE Verteilung von {task_count} Aufgaben gefordert:\n"
                f"{dist_desc}\n"
                f"WICHTIG:\n"
                f"1. Generiere ZWINGEND GENAU {task_count} Aufgaben in 'level_a.tasks' und GENAU {task_count} Aufgaben in 'level_b.tasks'!\n"
                f"2. Halte die Reihenfolge der Themenblöcke exakt ein: Zuerst alle Aufgaben zum ersten Schwerpunkt, danach die weiteren Schwerpunkte.\n"
                f"3. KEINE DOPPELTEN AUFGABEN: Jede einzelne der {task_count} Aufgaben muss eine eigenständige, neue Frage oder Übung sein!"
            )
        elif focus_topic:
            focus_instruction = f"Übungsschwerpunkte: {focus_topic} (Erstelle gezielt Aufgaben für JEDEN dieser Schwerpunkte!)."
        else:
            focus_instruction = "Übungsschwerpunkte: Automatisch aus dem Dokument ermitteln."
        focus_instruction += extra_block
        hefteintrag_raw = hefteintrag_topic if hefteintrag_topic else (focus_topic if focus_topic else "Hauptthema des Dokuments")
        hefteintrag_instruction = (
            f"Thema für den Hefteintrag / Merkkasten: {hefteintrag_raw}.\n"
            f"STRIKTE DIDAKTISCHE UNTERSCHEIDUNG FÜR DEN HEFTEINTRAG (SACHINHALT VS. METHODE):\n"
            f"- Wenn der Fokus/Text ein SACHTEXT oder ein inhaltliches Thema ist (z. B. 'Information about the Great Barrier Reef', Sachtext, Natur, Erdkunde, Geschichte, Landeskunde, Müll im Ozean):\n"
            f"  -> Der Hefteintrag MUSS zwingend die REINEN FACHINHALTE, FAKTEN und KERNAUSSAGEN des Textes festhalten (z. B. Steckbrief, Merkmale, wichtige Zahlen/Daten, Ursachen und Folgen)! Erfinde NIEMALS eine meta-didaktische Regelschablone ('Wie wende ich die Regeln zu ... an? Schritt 2: Formel anwenden') für einen Sachtext!\n"
            f"  -> Titel: z. B. '{hefteintrag_raw} – Wichtige Fakten im Überblick' (oder auf Englisch '{hefteintrag_raw} – Key Facts') bzw. eine themenbezogene Leitfrage.\n"
            f"- NUR wenn der Fokus explizit eine METHODE oder REGEL ist (z. B. 'Wie entnehme ich Informationen aus einem Sachtext?', 'Lesestrategien', 'Bruchrechnen', 'Grammatikregel: Pronomen'):\n"
            f"  -> DANN und nur dann beschreibt der Hefteintrag eine Vorgehensweise / Regel in nummerierten Schritten mit Musterbeispiel."
        )

        # Check if media (image/pdf) was uploaded, or if this is a topic/prompt-driven unit (ISB quality rubric)
        has_media = any(
            f.get('mime_type', '').startswith('image/') or f.get('mime_type') == 'application/pdf'
            for f in (files or [])
        )

        if differentiation_mode == "direct":
            role_description = (
                f"Du bist eine didaktisch herausragende Lehrkraft an einer {school_type}.\n"
                f"Deine Kernaufgabe ist die EXAKTE 1:1 DIGITALISIERUNG des hochgeladenen Arbeitsblatts / Dokuments als interaktives H5P-Übungsset.\n"
                f"Lies jede einzelne Aufgabe (Aufgabe 1, Aufgabe 2, Aufgabe 3...) exakt so wie sie auf dem Arbeitsblatt steht ab und transformiere sie 1:1 in eine digitale interaktive H5P-Aufgabe. "
                f"Erstelle KEIN künstliches Vorab-Diagnosequiz (diagnostic.questions bleibt eine leere Liste []) und erfinde KEINE alternativen Fördern/Fordern-Zweige (Level A und Level B erhalten identisch genau diese Aufgaben)."
            )
            source_instruction = (
                "1. ARBEITSBLATT 1:1 DIGITALISIERUNG:\n"
                "   - Erfasse JEDE Aufgabe des Arbeitsblatts getreu mit ihrer Nummerierung, Arbeitsanweisung und ihrem Text.\n   - WICHTIG: Bei Aufgaben, die sich auf einen Text, Satz oder unterstrichene Wörter beziehen (z. B. 'Bestimme die Wortart des unterstrichenen Wortes'): Übernimm ZWINGEND den vollständigen Satz und markiere das Wort (z. B. mit <u>Wort</u>), damit die Angabe für den Schüler vollständig und lösbar ist!\n"
                "   - Konvertiere jede Aufgabe direkt in das dafür am besten geeignete H5P-Format ('Lückentext' mit *Lückenwörtern*, 'Drag the Words' mit *Wörtern*, 'Tabellen-Zuordnung' mit Tabellenspalten und *Wörtern*, 'Wörter markieren' mit *Wörtern*, 'Wahr/Falsch' oder 'Multiple Choice').\n"
                "   - WICHTIG BEI DRAG THE WORDS / WÖRTSPEICHER: Falls das Arbeitsblatt im Wortspeicher zusätzliche Wörter (Distraktoren) enthält, die in keine Lücke gehören, erfasse diese ZWINGEND im Aufgaben-Feld 'distractors' (z. B. 'distractors': ['Wort1', 'Wort2']), damit sie dem Schüler im H5P-Wortspeicher zur Auswahl stehen!\n"
                "   - WICHTIG BEI ERSETZUNGS-AUFGABEN (z. B. 'Ersetze die in Klammern angegebenen Wörter durch passende Pronomen'): Übernimm die originale Arbeitsanweisung exakt als erste Zeile und behalte die Wörter in Klammern ZWINGEND direkt neben der Lücke bei (z. B. 'Wie *sie* (die Regeln) gestaltet werden, hängt von den Eltern ab. Wenn *sie* (die Eltern) eher großzügig sind...')! Lösche NIEMALS die Klammern, da der Schüler sonst die Bezugswörter nicht kennt! Wähle hierfür bevorzugt 'Lückentext'.\n"
                "   - Gib für jede Aufgabe eine verständliche Erklärung ('explanation') und einen ermutigenden Tipp ('hint') an.\n"
                "   - Das Feld 'diagnostic.questions' MUSS zwingend eine leere Liste [] sein."
            )
        else:
            role_description = (
                f"Du bist eine didaktisch herausragende Lehrkraft an einer {school_type} und ein Experte für differenzierten Unterricht nach dem bayerischen LehrplanPLUS und dem ISB-Qualitätstableau für digitalen Content.\n"
                f"Deine Aufgabe ist es, das hochgeladene Dokument (Buchseite, Arbeitsblatt, PDF) zu lesen (OCR) und darauf basierend ein qualitätsgeprüftes, differenziertes Lernpaket im JSON-Format für die Schulart '{school_type}' zu generieren."
            ) if has_media else (
                f"Du bist eine didaktisch herausragende Lehrkraft an einer {school_type} und ein Experte für kompetenzorientierten Unterricht nach dem bayerischen LehrplanPLUS und dem ISB-Qualitätstableau für digitalen Content.\n"
                f"Die Lehrkraft plant eine komplette, lebensnahe Unterrichtseinheit (z. B. 2x 45 min) und hat kein Buchseiten-Foto hochgeladen, sondern ein Thema/eine Anforderung vorgegeben: '{focus_topic or context}'.\n"
                f"Deine didaktische Kernaufgabe ist es, im Feld 'extracted_text' ZWINGEND einen packenden, zusammenhängenden, altersgerechten Basistext (ca. 180 bis 300 Wörter) aus dem Schüleralltag ({school_type}) passend zu Fach '{subject}' und Thema '{focus_topic or context}' zu verfassen. "
                f"Alle nachfolgenden differenzierten Aufgaben (Diagnose, Level A, Level B, Level C, Zusatzaufgaben und Tafelbild) MÜSSEN sich zwingend auf diesen situativen Basistext beziehen!"
            )

            source_instruction = (
                "1. BILDVORLAGE & OCR: Extrahiere den Kerninhalt des Textes aus dem Bild/PDF getreu im Feld 'extracted_text'."
            ) if has_media else (
                "1. ISB-QUALITÄTSTABLEAU & SITUIERTER BASISTEXT (OHNE BILDVORLAGE):\n"
                "   - Da kein Buchseiten-Scan hochgeladen wurde, formulierst du im Feld 'extracted_text' ZWINGEND einen packenden, zusammenhängenden und altersgerechten Basistext (180 bis 300 Wörter) aus dem Schüleralltag (z. B. Schulalltag, Pause, Sportfest, Klassenfahrt, Jugendthemen).\n"
                "   - Dieser Text dient als thematische und sprachliche Grundlage für die gesamte Einheit (situierter Kontext, ISB-Kriterium Lebensweltbezug).\n"
                "   - Alle nachfolgenden Aufgaben (Diagnose, Level A, Level B, Level C, Zusatzaufgaben) MÜSSEN sich direkt auf die Wörter, Sätze, Daten oder Figuren dieses Textes beziehen!"
            )

        text_basis_instruction = (
            "4. STRIKTE ANLEHNUNG AN DEN ORIGINALTEXT:\n"
            "   - Alle Aufgaben, Fragen, Merkkästen und Erklärungen MÜSSEN auf dem extrahierten Originaltext und den darin enthaltenen Zahlen, Definitionen und Beispielen basieren.\n"
            "   - Nimm mathematische Bezeichnungen, Variablen (z. B. 'U' oder 'Uk', Pi-Symbol 'π' oder Wert '3,14') exakt so an, wie sie in der Vorlage stehen. Verändere keine fachlichen Bezeichnungen aus dem Ausgangstext!\n"
            "   - Erfinde keine zusätzlichen, nicht behandelten Themen."
        ) if has_media else (
            "4. STRIKTE ANLEHNUNG AN DEN ERSTELLTEN BASISTEXT (ISB-LEBENSWELTBEZUG):\n"
            "   - Alle Aufgaben, Fragen, Merkkästen und Erklärungen MÜSSEN sich zwingend auf den im Feld 'extracted_text' generierten Basistext beziehen!\n"
            "   - Bei Grammatik/Wortarten: Verwende konkrete Sätze und Wörter aus dem Basistext für die Aufgaben!"
        )

        isb_rubric_instruction = """
- ISB-QUALITÄTSSTANDARDS (Automatisch im Hintergrund aktiv):
  • Lebenswelt- und Situationsbezug: Authentischer, altersgerechter Kontext für die Schulart.
  • Passgenaue Binnendifferenzierung: Fördern (Level A mit Scaffolding/Tipps), Fordern (Level B mit kognitiver Aktivierung und Transfer), Inklusion (Level C in Leichter Sprache) und Diagnose zur Einstufung.
  • Strukturierter Hefteintrag: Überschrift als leitende W-Frage, Merksatz, strukturierte Erklärung und konkretes Beispiel.
  • LehrplanPLUS Bayern: Exakte Ausrichtung auf die bayerischen Bildungsstandards mit offiziellem Lehrplancode.
"""

        prompt = f"""
{role_description}

Schulart: {school_type}
{subject_instruction}
{focus_instruction}
{hefteintrag_instruction}
Zusätzlicher Kontext (Klasse/Thema/Zeitvorgabe): {context}
Gewünschtes Standard-Aufgabenformat: {target_format}
Anzahl der zu generierenden Aufgaben pro Niveau: {task_count}

VORGABEN FÜR SPEZIELLE AUFGABENFORMATE:
- 'Wörter markieren' (H5P.MarkTheWords):
  -> Im Text klickt der Schüler gesuchte Wörter an (z. B. Wortarten, Fehler, Signalwörter).
  -> Alle korrekten Zielwörter MÜSSEN mit *Sternchen* umschlossen sein!
  -> Beispiel: 'Klicke alle Präpositionen an:\nDie Kinder lernen *mit* Freunden und gehen *in* die Schule.'
- 'Tabellen-Zuordnung' (Drag & Drop in Tabellenspalten / Kategorien):
  -> Begriffe werden Spalten/Kategorien einer Tabelle zugeordnet.
  -> Erstelle eine Markdown-Tabelle mit Spaltenüberschriften, wobei die zu ziehenden Begriffe mit *Sternchen* in den Zellen stehen.
  -> Beispiel:
     Ordne die Wortarten den passenden Spalten zu:
     | Flektierbare Wortarten | Unveränderliche Wortarten |
     | *Nomen* | *Präposition* |
     | *Verb* | *Konjunktion* |
     | *Adjektiv* | *Adverb* |
     Distraktoren: Banane, Baumhaus

- 'Freies Schreiben' / 'Essay' (KI-Schreibcoach mit semantischer Textkorrektur):
  -> Für freie Textproduktion, kreatives Schreiben, Argumentationen, Zusammenfassungen oder Beschreibungen.
  -> In 'text' formulierst du die Schreibaufgabe mit klaren, überprüfbaren Kriterien (z. B. Umfang in Sätzen/Wörtern, zu verwendende sprachliche Elemente wie Wortarten, Satzanfänge, Argumente).
  -> In 'hint' gibst du hilfreiche Formulierungshilfen oder Wortschatz-Impulse.
  -> In 'explanation' gibst du ein inspirierendes Musterbeispiel.

STRIKTE VORGABE FÜR DEN SCHWERPUNKT 'TEXTVERSTÄNDNIS' / 'LESEVERSTEHEN' / 'READING':
- Wenn ein Schwerpunkt 'Textverständnis', 'Leseverstehen', 'Reading' oder 'Sachtext' lautet:
  -> Nimm den extrahierten Text (bzw. Basistext) ganz genau als Grundlage!
  -> Generiere ECHTE INHALTLICHE VERSTÄNDNISFRAGEN zum Sinn, zu Details, Fakten, Zahlen, Ursachen und Folgen des Textes (z. B. 'Warum...?', 'Welche zwei Ursachen...?', 'Wo...?', 'Welche Folge hat...?').
  -> Erstelle NIEMALS Grammatik-Aufgaben (wie Simple Past, Wortarten, Verben), wenn Textverständnis / Reading verlangt wird!
  -> Multiple Choice Fragen MÜSSEN ZWINGEND so aufgebaut sein:
     Frage: [Konkrete inhaltliche Textfrage mit Fragezeichen]
     [X] [Die richtige inhaltliche Aussage zum Text]
     [ ] [Plausibler Distraktor / falsche Aussage zum Text]
     [ ] [Zweiter plausibler Distraktor]

Generiere genau folgendes JSON-Schema:
{{
  "title": "Prägnanter Titel der Übung/des Themas für Schüler ZWINGEND OHNE Schulart und OHNE Fach (z. B. '{focus_topic if focus_topic else 'Wortarten und ihre Verwendung'}') - nur das reine Thema!",
  "lehrplan_code": "Offizieller LehrplanPlus Bayern Code (z.B. 'M6 EG 2', 'D5 L1' oder 'E6 G1')",
  "lehrplan_competency": "Kurzbezeichnung der Kompetenz im Lehrplan (z. B. 'Anteile und Brüche im Alltag darstellen')",
  "extracted_text": "{'Der erkannte Text des Originaldokumentes sowie detaillierte Bildbeschreibungen von eventuell vorhandenen Illustrationen/Grafiken/Bildern zur Vorschau für die Lehrkraft' if has_media else 'Der vollständige, packende und lebensnahe Basistext (180-300 Wörter) aus dem Schüleralltag, der als Arbeits- und Lesegrundlage für alle Aufgaben dient'}",
  "diagnostic": {{
    "questions": [
      {{
        "question": "Einstiegsfrage 1 zur Diagnose (WICHTIG: Bei Sachtexten/Inhalten ZWINGEND eine glasklare Textverständnisfrage zum Thema/Inhalt wie 'Wo befindet sich das Great Barrier Reef?'. Niemals Grammatik oder Meta-Fragen bei einem Sachtext!)",
        "options": ["Konkrete, inhaltlich richtige Antwort", "Plausible Falschantwort"],
        "correct": 0
      }},
      {{
        "question": "Einstiegsfrage 2 zur Diagnose (konkrete, themenbezogene Inhaltsfrage zum Text)",
        "options": ["Plausible Falschantwort", "Konkrete richtige Textantwort"],
        "correct": 1
      }}
    ]
  }},
  "hefteintrag": {{
    "title": "Prägnante Überschrift (bei Methoden als W-Frage z.B. 'Wie berechne ich...', bei Sachtexten das Fachthema wie 'The Great Barrier Reef – Key Facts' oder 'Das Great Barrier Reef – Kernaussagen')",
    "summary": "Einheitlicher Klassen-Hefteintrag im sauberen HTML-Format (WICHTIG!). Bei Sachtexten: Gliedere in 1. Kernaussage / Überblick, 2. Wichtige Fakten & Zusammenhänge (neue Punkte zwingend mit <br> trennen), 3. Zusammenfassender Merksatz. Bei Methoden/Regeln: 1. Merke, 2. Schritte/Erklärung, 3. Beispiel. Wichtige Fachbegriffe mit <strong>fett</strong> hervorheben.",
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
{source_instruction}
2. WICHTIG: Falls mehrere Übungsschwerpunkte angegeben sind ({focus_topic}), erstelle Aufgaben, die ALLE diese Schwerpunkte abdecken!
3. LÜCKENTEXT-REGELN, SYNONYME & EXAKTHEIT:
   - Erstelle bei 'Lückentext' und 'Drag the Words' KEINE Einzelsätze, sondern ZWINGEND zusammenhängende Fließtexte aus 4 bis 6 Sätzen mit mindestens 4 bis 6 Lücken.
   - SYNONYME: Um Frust bei Schülern zu vermeiden, MÜSSEN inhaltlich oder mathematisch mehrdeutige Lücken alle gängigen Synonyme und Schreibweisen enthalten, getrennt durch einen Schrägstrich `/` (z.B. `*teilen/dividieren*`, `*3,14/3.14*`, `*verdoppeln/mal zwei nehmen/multiplizieren*`, `*Zahl/Konstante/Kreiszahl*`).
   - MAL-ZEICHEN: Verwende in mathematischen Formeln und Texten NIEMALS das Sternchen '*' als Multiplikationszeichen (Malzeichen), da dies Lücken-Parser irritiert. Benutze stattdessen ZWINGEND das offizielle Multiplikationszeichen '·' (Mittelpunkt / Malpunkt).
   - FACHLICHE RICHTIGKEIT: Alle mathematischen Formeln, Berechnungen und logischen Aussagen MÜSSEN zu 100% fachlich korrekt und präzise sein. Prüfe deine Aufgaben vor der Ausgabe kritisch auf inhaltliche Fehler!
   - ERSETZUNGS-AUFGABEN (z. B. 'Ersetze die Wörter in Klammern durch passende Pronomen'): Das zu ersetzende Ausgangswort MUSS ZWINGEND in Klammern direkt neben der Lücke stehen bleiben (z. B. 'Wie *sie* (die Regeln) gestaltet werden...'). Niemals die Klammern löschen!
{text_basis_instruction}
{isb_rubric_instruction}
5. STRIKTE AUFGABEN-FORMATIERUNGSREGELN FÜR DEN FELDINHALT 'text':
   - DRAG THE WORDS: Markiere alle Lückenwörter im Fließtext mit *Sternchen*.
     WICHTIG FÜR WÖRTSPEICHER & DISTRAKTOREN: Wenn das Arbeitsblatt im Wortspeicher zusätzliche falsche Wörter enthält oder zur Erhöhung des Anspruchs Distraktoren nötig sind, gib diese im Aufgaben-Feld 'distractors' an (z. B. "distractors": ["falschesWort1", "falschesWort2"]).
   - MULTIPLE CHOICE: Jede Aufgabe MUSS zwingend die vollständige Aufgabenstellung UND den konkreten Beispielsatz / die Angabe enthalten!
     Format des Feldes 'text':
     [Aufgabenstellung / Frage]
     Beispielsatz: "[Vollständiger Satz mit dem gesuchten Wort, z. B. 'Die Kinder <u>laufen</u> schnell nach Hause.']"
     [ ] [Eine falsche Option]
     [X] [Die richtige Option]
     [ ] [Eine andere falsche Option]
     WICHTIG: Wenn die Aufgabe nach 'dem unterstrichenen Wort' oder 'im folgenden Satz' fragt, MUSS der vollständige Beispielsatz zwingend direkt im Text angegeben werden! Niemals die Frage isoliert ohne den Beispielsatz generieren!
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
            contents, uploaded_gemini_files, temp_files_to_remove, _ = self._prepare_gemini_contents(
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
                            max_output_tokens=8192,
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
            if isinstance(result_json, dict) and "title" in result_json:
                from .h5p_generator import clean_student_title
                result_json["title"] = clean_student_title(result_json["title"])

            if differentiation_mode == "direct" and isinstance(result_json, dict):
                result_json["is_direct_worksheet"] = True
                result_json["differentiation_mode"] = "direct"
                if "level_a" in result_json:
                    result_json["level_b"] = result_json["level_a"]
                if "diagnostic" in result_json:
                    result_json["diagnostic"]["questions"] = []

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
            return self._get_mock_data(context, target_format, task_count, subject=subject, school_type=school_type, focus_topic=focus_topic, hefteintrag_topic=hefteintrag_topic, error_message=str(e), differentiation_mode=differentiation_mode)

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

    def _get_mock_data(self, context: str = "", target_format: str = "KI-Mix", task_count: int = 2, subject: str = "Deutsch", school_type: str = "Grundschule", focus_topic: str = "", hefteintrag_topic: str = "", error_message: str = None, differentiation_mode: str = "differentiated") -> dict:
        """Returns beautiful default mock data in case API key is missing or fails."""
        parsed_str = focus_topic.strip() if focus_topic and focus_topic.strip() else (context.strip() if context and context.strip() else "")
        if not parsed_str:
            parsed_str = "Textverständnis, Fremdwörter, Wortarten" if subject == "Deutsch" else ("Bruchrechnen" if subject == "Mathematik" else "Simple Past")
        topic_str = parsed_str

        _d = parse_teacher_context_directives(context, focus_topic, task_count)
        topics_list, actual_count, topic_dist = _d["expanded_topics"], _d["total_task_count"], _d["distribution"]
        heft_str = hefteintrag_topic if hefteintrag_topic else (focus_topic if focus_topic else "Hauptthema")
        lower_heft = (heft_str or "").lower()
        
        import re
        clean_title_topic = re.sub(r'\d+\s*x?\s*(?:zu|für)?\s*', '', parsed_str).strip()
        clean_title_topic = re.sub(r'^\s*,\s*|\s*,\s*$', '', clean_title_topic)
        if not clean_title_topic or len(clean_title_topic) < 3:
            clean_title_topic = "Müll im Ozean - Der achte Kontinent" if subject == "Deutsch" else ("Bruchrechnen" if subject == "Mathematik" else "Grammar & Reading")

        title = clean_title_topic
        
        extracted = f"[DEMO-MODUS] Hier steht der extrahierte Text der Buchseite für {subject}.\n\n"
        if subject == "Mathematik":
            extracted += "Beispiel: 'Ein Kuchen wird in 8 gleiche Teile geschnitten. Anna isst 2 Teile, Ben isst 3 Teile. Welcher Anteil bleibt übrig?'\n"
        elif subject == "Deutsch":
            extracted += "Kinder brauchen im Familienleben feste Regeln. Wie sie gestaltet werden, hängt von den Eltern ab.\nWenn Eltern eher großzügig sind, gehen sie oft lockerer mit den Regeln um.\nMerkt das Kind, dass Regeln nur manchmal gelten, wird es sich nicht unbedingt an ihnen orientieren, sondern am Verhalten seiner Eltern.\n"
        else:
            extracted += "The Great Barrier Reef is the largest coral reef system on Earth, located off the northeast coast of Australia.\nRising sea temperatures cause coral bleaching and threaten marine biodiversity.\n"
        
        extracted += "\nBildbeschreibung: Eine illustrative Grafik passend zum Thema."
        
        tasks_a = []
        tasks_b = []
        tasks_c = []

        # Rich pool for Reading Comprehension
        reading_pool_de = [
            {
                "format": "Multiple Choice", "suffix": "Kernaussage des Textes",
                "a_text": f"Frage: Worüber informiert der vorliegende Text zu '{clean_title_topic}' hauptsächlich?\n[X] Über feste Regeln, klare Orientierung und das Zusammenleben in der Familie\n[ ] Dass Absprachen im Alltag überhaupt keine Rolle spielen\n[ ] Ausschließlich über Freizeitaktivitäten in den Schulferien",
                "b_text": f"Frage: Welche zentrale Schlussfolgerung zieht der Autor über familiäre Regeln?\n[X] Verlässlichkeit und Vorbildfunktion der Eltern sind entscheidend für die Orientierung des Kindes\n[ ] Kinder orientieren sich nur dann, wenn keinerlei Grenzen existieren\n[ ] Regeln müssen täglich komplett neu verhandelt werden",
                "hint": "💡 Tipp: Achte genau auf den ersten und letzten Satz des Textes.",
                "exp": "Die Kernaussage betont die Verlässlichkeit und Vorbildfunktion der Eltern."
            },
            {
                "format": "Wahr/Falsch", "suffix": "Detailaussagen zum Text",
                "a_text": "Aussage: Wenn Eltern Regeln nur manchmal gelten lassen, fällt es Kindern schwerer, sich daran zu halten.\nAntwort: Wahr",
                "b_text": "Aussage: Kinder orientieren sich primär am tatsächlichen Verhalten der Eltern und nicht an theoretischen Vorgaben.\nAntwort: Wahr",
                "hint": "💡 Tipp: Lies den letzten Satz des Abschnitts noch einmal aufmerksam.",
                "exp": "Das Kind orientiert sich am tatsächlichen Verhalten der Eltern."
            },
            {
                "format": "Lückentext", "suffix": "Kausalzusammenhänge erfassen",
                "a_text": "Kinder brauchen feste *Regeln*, um sich sicher zu fühlen. Wie diese gestaltet werden, entscheiden die *Eltern*. Ein *Verhalten*, das verlässlich ist, gibt Kindern klare *Orientierung*.",
                "b_text": "Inkonsequentes *Verhalten* führt dazu, dass Kinder bestehende *Regeln* hinterfragen. Eine verlässliche *Struktur* erfordert klare *Absprachen* zwischen Eltern und Kind.",
                "hint": "💡 Tipp: Achte auf die Schlüsselwörter im Text.",
                "exp": "Regeln und Orientierung bilden das didaktische Fundament des Textes."
            },
            {
                "format": "Wörter markieren", "suffix": "Zentrale Textbegriffe markieren",
                "a_text": "Klicke alle Schlüsselbegriffe im folgenden Satz an:\nFeste *Regeln* im *Familienleben* geben Kindern Halt und wichtige *Orientierung*.",
                "b_text": "Klicke alle Verhaltensweisen und Kriterien an:\nWenn Eltern *großzügig* oder *locker* handeln, müssen Absprachen *verlässlich* bleiben.",
                "hint": "💡 Tipp: Markiere die wesentlichen Leitbegriffe des Textes.",
                "exp": "'Regeln', 'Familienleben' und 'Orientierung' sind die thematischen Ankerbegriffe."
            },
            {
                "format": "Multiple Choice", "suffix": "Textanalyse & Vertiefung",
                "a_text": "Frage: Was passiert laut Text, wenn Regeln nur manchmal gelten?\n[X] Das Kind orientiert sich am Verhalten der Eltern statt an der Regel\n[ ] Das Kind beachtet die Regeln sofort doppelt so aufmerksam\n[ ] Es hat keinerlei Auswirkungen auf das Kind",
                "b_text": "Frage: Warum ist elterliche Konsequenz laut Text von so großer Bedeutung?\n[X] Weil Vorbildwirkung und Regelanwendung das Werteverständnis des Kindes prägen\n[ ] Weil Eltern dadurch weniger Freizeit haben\n[ ] Weil das Gesetz tägliche schriftliche Kontrollen vorschreibt",
                "hint": "💡 Tipp: Verknüpfe Ursache und Folge im Text.",
                "exp": "Inkonsequenz führt zu Orientierungslosigkeit bei Kindern."
            }
        ]

        # Rich pool for Underlined Words & Grammar
        grammar_pool_de = [
            {
                "format": "Wörter markieren", "suffix": "Nomen erkennen",
                "a_text": "Klicke alle unterstrichenen Nomen im Satz an:\nIm *Familienleben* brauchen *Kinder* feste *Regeln* und klare *Orientierung*.",
                "b_text": "Klicke alle Nomen mit Signalwörtern an:\nDas *Verhalten* der *Eltern* bestimmt den *Alltag* und die *Grenzen*.",
                "hint": "💡 Tipp: Nomen werden großgeschrieben und bezeichnen Dinge, Lebewesen oder Begriffe.",
                "exp": "Nomen bezeichnen Lebewesen, Gegenstände oder Begriffe."
            },
            {
                "format": "Lückentext", "suffix": "Pronomen mit Klammerbezug einsetzen",
                "a_text": "Ersetze die in Klammern angegebenen Wörter durch passende Pronomen:\nWie *sie* (die Regeln) gestaltet werden, hängt von den Eltern ab. Wenn *sie* (die Eltern) eher großzügig sind, wird *es* (das Kind) sich nicht an *ihnen* (den Regeln) orientieren.",
                "b_text": "Ersetze die Satzglieder durch zutreffende Pronomen:\nMerkt das Kind, dass Regeln gelten, orientiert *es* (das Kind) sich am Verhalten *seiner* (des Kindes) Eltern, denn *sie* (die Eltern) sind Vorbilder für *ihn/es* (das Kind).",
                "hint": "💡 Tipp: Achte auf Fall (Kasus) und grammatisches Geschlecht (Genus).",
                "exp": "Pronomen stehen als Stellvertreter für bereits genannte Nomen."
            },
            {
                "format": "Drag the Words", "suffix": "Verben in die Grundform (Infinitiv) setzen",
                "a_text": "Ordne den gebeugten Verben ihre Grundform (Infinitiv) zu:\n'hängt ab' -> *abhängen*\n'gehen um' -> *umgehen*\n'gilt' -> *gelten*\n'orientiert sich' -> *orientieren*",
                "b_text": "Ordne den Präteritum-Formen den Infinitiv zu:\n'brauchten' -> *brauchen*\n'galten' -> *gelten*\n'gingen' -> *gehen*\n'merkte' -> *merken*",
                "hint": "💡 Tipp: Der Infinitiv endet im Deutschen meist auf -en.",
                "exp": "Die Grundform eines Verbs ist der Infinitiv."
            },
            {
                "format": "Tabellen-Zuordnung", "suffix": "Wortarten in Tabelle zuordnen",
                "a_text": "Ordne die unterstrichenen Wörter den passenden Wortarten-Spalten zu:\n\n| Nomen | Verben | Adjektive |\n| *Familienleben* | *gestalten* | *großzügig* |\n| *Regeln* | *orientieren* | *locker* |\n\nDistraktoren: gestern, schnell",
                "b_text": "Ordne die Wörter den passenden Kategorien zu:\n\n| Nomen | Verben | Pronomen |\n| *Eltern* | *brauchen* | *sie* |\n| *Verhalten* | *gelten* | *ihnen* |\n\nDistraktoren: heute, dort",
                "hint": "💡 Tipp: Ziehe jedes Kärtchen in die passende Spalte.",
                "exp": "Wortarten lassen sich anhand ihrer grammatischen Merkmale eindeutig bestimmen."
            },
            {
                "format": "Multiple Choice", "suffix": "Adjektive und Gegenteile",
                "a_text": "Frage: Welches Wort ist das genaue Gegenteil des unterstrichenen Adjektivs <u>großzügig</u>?\nBeispielsatz: 'Wenn Eltern eher <u>großzügig</u> sind, gehen sie lockerer mit Regeln um.'\n[X] streng / geizig\n[ ] tolerant\n[ ] freundlich",
                "b_text": "Frage: Welches Antonym passt exakt zum unterstrichenen Adjektiv <u>locker</u>?\nBeispielsatz: 'Sie gehen <u>lockerer</u> mit den Absprachen um.'\n[X] strikt / verbindlich\n[ ] lässig\n[ ] entspannt",
                "hint": "💡 Tipp: Gegenteile bedeuten das genaue Gegenteil des Adjektivs.",
                "exp": "Großzügig hat als Antonym geizig oder streng."
            },
            {
                "format": "Wörter markieren", "suffix": "Präpositionen (Verhältniswörter)",
                "a_text": "Klicke alle Präpositionen im Satz an:\nKinder orientieren sich *an* den Eltern und leben *in* einer Familie *mit* festen Regeln.",
                "b_text": "Klicke alle Präpositionen mit Dativ/Akkusativ an:\nSie lernen *durch* das Vorbild und handeln *nach* den Vorgaben *von* Erwachsenen.",
                "hint": "💡 Tipp: Präpositionen verlangen einen bestimmten Fall (Dativ oder Akkusativ).",
                "exp": "'an', 'in' und 'mit' sind Präpositionen."
            },
            {
                "format": "Drag the Words", "suffix": "Konjunktionen im Satzgefüge",
                "a_text": "Setze die passenden Konjunktionen (Bindewörter) ein:\n*Wenn* Eltern großzügig sind, gelten Regeln manchmal nicht, *weil* die Konsequenz fehlt, *dass* Absprachen eingehalten werden.",
                "b_text": "Verbinde die Haupt- und Nebensätze mit Konjunktionen:\nDas Kind merkt schnell, *dass* Regeln Orientierung geben, *obwohl* Ausnahmen verlockend sind, *damit* das Miteinander gelingt.",
                "hint": "💡 Tipp: Konjunktionen verbinden Sätze und leiten Nebensätze ein.",
                "exp": "'wenn', 'weil' und 'dass' sind unterordnende Konjunktionen."
            },
            {
                "format": "Multiple Choice", "suffix": "Satzglieder bestimmen (Subjekt)",
                "a_text": "Frage: Welches Satzglied ist der unterstrichene Teil <u>das Kind</u>?\nBeispielsatz: 'Merkt <u>das Kind</u> die Ausnahme, orientiert es sich daran.'\n[X] Subjekt (Satzgegenstand: Wer oder was?)\n[ ] Prädikat (Satzaussage)\n[ ] Akkusativobjekt (Wen-Ergänzung)",
                "b_text": "Frage: Welche syntaktische Funktion hat <u>von den Eltern</u> im Satz?\nBeispielsatz: 'Wie Regeln gestaltet werden, hängt <u>von den Eltern</u> ab.'\n[X] Präpositionalobjekt\n[ ] Subjekt\n[ ] Adverbiale Bestimmung der Zeit",
                "hint": "💡 Tipp: Frage nach dem Satzglied: Wer oder was merkt die Ausnahme?",
                "exp": "'Das Kind' ist das Subjekt, da es die Handlung im Satz ausführt."
            },
            {
                "format": "Lückentext", "suffix": "Komposita (Zusammengesetzte Nomen)",
                "a_text": "Zerlege das zusammengesetzte Nomen 'Familienleben':\nEs setzt sich zusammen aus dem Bestimmungswort *Familie/Familien* und dem Grundwort *Leben*.",
                "b_text": "Bilde aus den beiden Nomen 'Regel' und 'Verstoß' ein Kompositum:\nDas zusammengesetzte Nomen lautet *Regelverstoß* mit dem Grundwort *Verstoß*.",
                "hint": "💡 Tipp: Das Grundwort bestimmt den Artikel des zusammengesetzten Nomens.",
                "exp": "Familie + Leben = das Familienleben."
            },
            {
                "format": "Lückentext", "suffix": "Steigerung von Adjektiven",
                "a_text": "Bilde die Steigerungsstufen des unterstrichenen Adjektivs 'locker':\nPositiv: *locker* -> Komparativ: *lockerer* -> Superlativ: *am lockersten*.",
                "b_text": "Bilde die Steigerung des Adjektivs 'fest':\nPositiv: *fest* -> Komparativ: *fester* -> Superlativ: *am festesten*.",
                "hint": "💡 Tipp: Achte auf die Endungen -er und -sten.",
                "exp": "Adjektive lassen sich regelmäßig mit -er und -sten steigern."
            },
            {
                "format": "Tabellen-Zuordnung", "suffix": "Flektierbare vs. Unflektierbare Wortarten",
                "a_text": "Ordne die Wörter den beiden Hauptkategorien zu:\n\n| Flektierbare Wortarten (veränderbar) | Unveränderliche Wortarten |\n| *Eltern* | *manchmal* |\n| *brauchen* | *nicht* |\n| *fest* | *sondern* |\n\nDistraktoren: Baum, Haus",
                "b_text": "Ordne nach grammatischer Veränderbarkeit:\n\n| Flektierbar | Nicht flektierbar |\n| *Regel* | *sehr* |\n| *gelten* | *oft* |\n| *großzügig* | *wenn* |\n\nDistraktoren: Kind, Tisch",
                "hint": "💡 Tipp: Flektierbare Wörter lassen sich beugen, deklinieren oder konjugieren.",
                "exp": "Nomen, Verben und Adjektive sind flektierbar; Adverbien und Konjunktionen unveränderlich."
            },
            {
                "format": "Drag the Words", "suffix": "Wortfamilien & Wortstamm",
                "a_text": "Finde Wörter aus der Wortfamilie mit dem Wortstamm *halt* (von 'verhalten'):\nDas *Verhalten*, der *Halt*, die *Haltung* und das Verb *behalten*.",
                "b_text": "Ordne Wörter mit dem Wortstamm *stell* (von 'gestalten'):\nDie *Gestaltung*, der *Darsteller*, *vorstellen* und die *Stelle*.",
                "hint": "💡 Tipp: Wörter einer Wortfamilie haben den gleichen Wortstamm.",
                "exp": "Alle diese Wörter teilen den gemeinsamen Wortstamm."
            },
            {
                "format": "Lückentext", "suffix": "Zeitformen der Verben (Präteritum)",
                "a_text": "Setze die unterstrichenen Verben in die einfache Vergangenheit (Präteritum):\nDie Eltern *brauchten* (brauchen) Ruhe. Sie *galten* (gelten) als verlässlich und *halfen* (helfen) den Kindern.",
                "b_text": "Wandle die Präsenssätze ins Präteritum um:\nDas Kind *merkte* (merken) die Ausnahme und *ging* (gehen) lockerer mit der Regel um.",
                "hint": "💡 Tipp: Achte auf unregelmäßige (starke) Verben: gelten -> galt.",
                "exp": "'brauchten' ist regelmäßig, 'galten' und 'ging' sind unregelmäßige Präteritum-Formen."
            },
            {
                "format": "Wahr/Falsch", "suffix": "Grammatische Merkmale prüfen",
                "a_text": "Aussage: Das Wort 'Regeln' im Satz 'Kinder brauchen feste Regeln' steht im Plural (Mehrzahl) und im Akkusativ (Wen-Fall).\nAntwort: Wahr",
                "b_text": "Aussage: Das Wort 'großzügig' fungiert im Satz 'Wenn Eltern großzügig sind' als prädikatives Adjektiv und wird nicht flektiert.\nAntwort: Wahr",
                "hint": "💡 Tipp: Frage nach dem Fall: Wen oder was brauchen Kinder? Feste Regeln.",
                "exp": "'Regeln' ist Akkusativ Plural von 'die Regel'."
            },
            {
                "format": "Freies Schreiben", "suffix": "Transfer: Eigene Regelsätze verfassen",
                "a_text": "Formuliere 3 eigene, wichtige Regeln für deine Klasse oder Familie (ca. 4-5 Sätze).\nKriterien:\n- Verwende mindestens zwei Nomen, zwei Verben und zwei Adjektive aus dem Text.\n- Markiere deine Nomen blau, Verben rot und Adjektive grün.",
                "b_text": "Verfasse eine kurze Reflexion (ca. 6-8 Sätze) zum Thema 'Brauchen Jugendliche Regeln?'.\nKriterien:\n- Begründe deine Meinung mit zwei Argumenten.\n- Verwende mindestens drei verschiedene Konjunktionen (weil, dass, obwohl).\n- Baue Fachbegriffe wie 'Orientierung' und 'Verlässlichkeit' ein.",
                "hint": "💡 Tipp: Verwende Satzanfänge wie 'Es ist wichtig, dass...' oder 'Wir achten darauf, dass...'",
                "exp": "Ein gelungener Regelsatz verbindet klare Kriterien mit korrekter Grammatik."
            }
        ]

        reading_counter = 0
        grammar_counter = 0

        for i in range(actual_count):
            t_focus = topics_list[i % len(topics_list)]
            lower_focus = (t_focus or "").lower()
            is_reading_focus = any(w in lower_focus for w in [
                "textverst", "leseverst", "reading", "comprehension", "sachtext",
                "inhalt", "fragen zum text", "information", "fakten"
            ])
            is_last = (i == actual_count - 1)

            if is_reading_focus:
                pool_item = reading_pool_de[reading_counter % len(reading_pool_de)]
                reading_counter += 1
            else:
                pool_item = grammar_pool_de[grammar_counter % len(grammar_pool_de)]
                grammar_counter += 1

            fmt = target_format if target_format != "KI-Mix" else pool_item["format"]
            a_title = f"Fördern - {t_focus} ({pool_item['suffix']})"
            b_title = f"Transfer & Anwendung - {t_focus}" if is_last else f"Fordern - {t_focus} ({pool_item['suffix']})"

            # Level C (Inklusion & DaZ)
            tasks_c.append({
                "title": f"Inklusion/DaZ - {t_focus} (Aufgabe {i+1})",
                "text": f"Leichte Sprache ({subject}):\nDer Text gibt wichtige *Regeln*.\nWir lesen den Text *genau*.",
                "format": "Drag the Words",
                "hint": "💡 Sprachhilfe: Konzentriere dich auf die Schlüsselbegriffe im Text.",
                "explanation": "Sehr einfache Sprache unterstützt das Textverständnis."
            })

            tasks_a.append({
                "title": a_title,
                "text": pool_item["a_text"],
                "format": fmt,
                "hint": pool_item["hint"],
                "explanation": pool_item["exp"]
            })
            tasks_b.append({
                "title": b_title,
                "text": pool_item["b_text"],
                "format": fmt,
                "hint": "",
                "explanation": pool_item["exp"]
            })

        # Determine whether Hefteintrag is content/fact-focused vs. method/rule-focused
        lower_heft = (heft_str or "").lower()
        factual_indicators = [
            "sachtext", "information", "info", "fakten", "reef", "barrier", "ozean", "klima", "umwelt",
            "geschichte", "erdkunde", "geografie", "biologie", "gpg", "pcb", "landeskunde",
            "tier", "pflanz", "kontinent", "australi", "deutschland", "europa", "stadt", "land"
        ]
        method_indicators = ["wie ", "methode", "regel", "strategie", "formel", "rechen", "grammatik", "entnehme ich", "schritte", "anleitung"]
        is_factual = any(w in lower_heft for w in factual_indicators) or (subject in ["Englisch", "GPG", "PCB", "Biologie", "Geografie", "Geschichte"] and not any(w in lower_heft for w in method_indicators))
        is_english = (subject == "Englisch") or any(w in lower_heft for w in ["reef", "barrier", "great barrier", "information about", "past", "present", "english"])

        if is_factual:
            if is_english:
                mock_heft_title = f"{heft_str} – Key Facts & Summary"
                if "reef" in lower_heft or "barrier" in lower_heft:
                    mock_heft_summary = (
                        f"📌 THE GREAT BARRIER REEF – KEY FACTS\n\n"
                        f"1. OVERVIEW & LOCATION:\n"
                        f"• The Great Barrier Reef is the world's largest coral reef system, located off the coast of Australia.\n\n"
                        f"2. BIODIVERSITY & IMPORTANCE:\n"
                        f"• Unique habitat for thousands of marine species (corals, turtles, fish, sharks).\n"
                        f"• Vital for ocean ecology and recognized as a UNESCO World Heritage site.\n\n"
                        f"3. THREATS & CONSERVATION:\n"
                        f"• Main threat: Rising sea temperatures cause coral bleaching.\n"
                        f"• Protection: Strictly regulated marine reserve to preserve biodiversity."
                    )
                else:
                    mock_heft_summary = (
                        f"📌 {heft_str.upper()} – KEY FACTS\n\n"
                        f"1. CORE INFORMATION:\n"
                        f"• Essential facts and definitions regarding '{heft_str}'.\n\n"
                        f"2. KEY POINTS & DETAILS:\n"
                        f"• Main characteristic: Central factual findings from the text.\n"
                        f"• Supporting detail: Important data, causes, and consequences.\n\n"
                        f"3. SUMMARY:\n"
                        f"• Essential takeaway sentence to remember for tests and class discussions."
                    )
            else:
                mock_heft_title = f"{heft_str} – Wichtige Fakten im Überblick"
                mock_heft_summary = (
                    f"📌 {heft_str.upper()} – WICHTIGE FAKTEN\n\n"
                    f"1. KERNAUSSAGE / ÜBERBLICK:\n"
                    f"• Die wesentlichen Sachinformationen zu '{heft_str}' kurz und präzise zusammengefasst.\n\n"
                    f"2. WICHTIGE FAKTEN & ZUSAMMENHÄNGE:\n"
                    f"• Hauptmerkmal: Zentrale Erkenntnis und wichtige Fachbegriffe aus dem Text.\n"
                    f"• Details & Hintergründe: Ursachen, Wirkungen und konkrete Zahlen/Daten.\n\n"
                    f"3. MERKSATZ FÜRS HEFT:\n"
                    f"• Der wichtigste Gedanke als Merksatz zum dauerhaften Behalten."
                )
        else:
            mock_heft_title = heft_str if lower_heft.startswith("wie ") else f"Wie wende ich die Regeln zu '{heft_str}' richtig an?"
            mock_heft_summary = (
                f"📌 {mock_heft_title.upper()}\n\n"
                f"1. MERKREGEL:\n"
                f"Wichtigste Grundregel zum Thema '{heft_str}' kurz und prägnant erklärt.\n\n"
                f"2. SCHRITTE ZUR ANWENDUNG:\n"
                f"• Schritt 1: Gegebenes genau analysieren & Signalwörter markieren.\n"
                f"• Schritt 2: Passende Regel oder Formel anwenden.\n"
                f"• Schritt 3: Ergebnis auf Richtigkeit und Plausibilität überprüfen.\n\n"
                f"3. MUSTERBEISPIEL / MERKSATZ:\n"
                f"Anschauliches Beispiel für den 1:1 Übertrag in das Merkheft."
            )

        mock_hefteintrag = {
            "title": mock_heft_title,
            "summary": mock_heft_summary,
            "level_a_notes": "",
            "level_b_notes": ""
        }

        # Build appropriate diagnostic questions based on differentiation mode and topic
        if differentiation_mode == "direct":
            mock_diagnostic = {"questions": []}
        else:
            if is_factual:
                if is_english:
                    if "reef" in lower_heft or "barrier" in lower_heft:
                        mock_diagnostic = {
                            "questions": [
                                {
                                    "question": "Where is the Great Barrier Reef located?",
                                    "options": ["Off the northeast coast of Australia", "In the Atlantic Ocean"],
                                    "correct": 0
                                },
                                {
                                    "question": "What is currently the greatest threat to coral reefs?",
                                    "options": ["Too many fish species", "Rising sea temperatures and coral bleaching"],
                                    "correct": 1
                                }
                            ]
                        }
                    else:
                        mock_diagnostic = {
                            "questions": [
                                {
                                    "question": f"What is the central topic of the text about '{clean_title_topic}'?",
                                    "options": [f"Key factual information and background on {clean_title_topic}", "A fictional fairy tale"],
                                    "correct": 0
                                },
                                {
                                    "question": f"Which fact is highlighted regarding '{clean_title_topic}'?",
                                    "options": ["An unimportant side note", f"The specific causes, data, and consequences described in the text"],
                                    "correct": 1
                                }
                            ]
                        }
                else:
                    mock_diagnostic = {
                        "questions": [
                            {
                                "question": f"Worum geht es im vorliegenden Sachtext zu '{clean_title_topic}' hauptsächlich?",
                                "options": [f"Um die wesentlichen Sachinformationen und Fakten zu {clean_title_topic}", "Um eine frei erfundene Geschichte"],
                                "correct": 0
                            },
                            {
                                "question": f"Welche Information ist für das Thema '{clean_title_topic}' besonders wichtig?",
                                "options": ["Eine zufällige Randbemerkung", "Die im Text genannten Ursachen, Wirkungen und Fachbegriffe"],
                                "correct": 1
                            }
                        ]
                    }
            else:
                mock_diagnostic = {
                    "questions": [
                        {
                            "question": f"Welches Grundprinzip gilt beim Thema '{clean_title_topic}'?",
                            "options": [f"Die grundlegende Regel zu {clean_title_topic} schrittweise anwenden", "Regeln und Rechenschritte beliebig vertauschen"],
                            "correct": 0
                        },
                        {
                            "question": f"Wie gehst du bei einer kniffligeren Aufgabe zu '{clean_title_topic}' vor?",
                            "options": ["Sofort aufgeben", "Die Aufgabenstellung genau analysieren und den passenden Lösungsweg wählen"],
                            "correct": 1
                        }
                    ]
                }

        return {
            "title": title,
            "lehrplan_code": f"{'M6 EG 2' if subject == 'Mathematik' else ('D5 L1' if subject == 'Deutsch' else 'E6 G1')}",
            "lehrplan_competency": f"LehrplanPlus Bayern ({subject}): Kompetenzen im Bereich '{topic_str}' anwenden und reflektieren",
            "extracted_text": extracted,
            "diagnostic": mock_diagnostic,
            "hefteintrag": mock_hefteintrag,
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
        task_count: int = 5,
        api_key: str = None,
        youtube_url: str = None,
        video_duration: int = None
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

ABSOLUTE ANFORDERUNGEN AN THEMEN-PASSGENAUIGKEIT, ERKLÄRUNGEN UND STOPP-ZEITPUNKTE:

1. THEMA UND FACH (100% PASSGENAU AUS DEM VIDEO):
   - Das tatsächliche Schulfach (z. B. 'Informatik', 'Mathematik', 'Physik', 'Biologie', 'Chemie', 'Geschichte', 'Deutsch', 'Wirtschaft' etc.) und der genaue Titel (z. B. 'Informatik: Aufbau von IPv4-Adressen und Subnetzen') MÜSSEN zu 100% aus dem tatsächlichen Inhalt des Videos abgeleitet werden.
   - Bildspur und Tonspur sind die absolute Wahrheitsquelle. Ignoriere irreführende Vorbelegungen oder Standardwerte vollständig.

2. EXAKTER STOPP-ZEITPUNKT (TIMESTAMPS – DIREKT NACH DEM FERTIGEN SATZ STOPPEN!):
   - ABSOLUTE TIMING-PFLICHT: Stoppe DIREKT in der natürlichen Atempause (0,5 bis maximal 1 Sekunde) nach dem allerletzten Wort des erklärenden Satzes!
   - NIEMALS ZU LANGE WARTEN: Wenn du 2 bis 4 Sekunden wartest, beginnt der Sprecher im Video bereits den nächsten Satz! Das darf keinesfalls passieren.
   - NIEMALS mitten im Satz oder während eines noch unfertigen Wortes stoppen.
   - Nutze die Transkript-Zeitstempel und Satzzeichen (. ! ?): Wenn der erklärende Satz bei Sekunde 24 endet, stoppe exakt bei Sekunde 24 oder 25 – direkt nach dem Schlusspunkt, bevor das erste Wort des nächsten Satzes fällt.
   - Haltepunkte müssen streng chronologisch aufsteigend angeordnet sein (Stopp 1 < Stopp 2 < Stopp 3 ...).

3. FRAGEN UND MERKKÄSTEN (PASSGENAU ZUM VIDEO MIT KLARER SCHÜLER-ANWEISUNG):
   - Jede Frage muss eine konkrete, im Video genannte Tatsache, Definition, Zahl, Struktur oder Vorgehensweise abfragen. Keine vagen Allgemeinplätze!
   - FRAGETYPEN:
     * 'Multiple Choice': Klare Frage zum soeben erklärten Punkt. Genau 1 richtige Antwort (stimmt exakt mit dem Video überein) und 2-3 plausible falsche Distraktoren.
     * 'Wahr/Falsch': Präzise Aussage zu dem im Video gezeigten Sachverhalt mit 'correct': true oder false.
     * 'Lückentext' (als aktiver Merkkasten): Ein didaktischer Merksatz, bei dem der wichtigste soeben gelernte Fachbegriff in Sternchen steht (z. B. "Eine IPv4-Adresse besteht aus *32* Bit."), den die Schüler eintragen.
     * 'Infobox' (als didaktischer Merkkasten): Ein hervorgehobener Merkkasten, der die Kernaussage, Formel oder Regel des soeben gesehenen Abschnitts einprägsam zusammenfasst.
       WICHTIG: Jeder Merkkasten ('Infobox') MUSS IMMER für die Schüler die unmissverständliche Handlungsanweisung enthalten:
       "✍️ **Aufgabe für dein Heft:** Übertrage diesen Merkkasten jetzt sauber in dein Schulheft!"
       sowie die Erklärung zum Fortfahren:
       "▶️ **So geht's weiter:** Klicke oben rechts auf das ✕ (Schließen) oder unten auf Play ▶, sobald du fertig geschrieben hast!"
   - Mindestens einer der Haltepunkte sollte als didaktischer Merkkasten ('Infobox' oder 'Lückentext') gestaltet sein, um das Gelernte zu festigen.

4. DIDAKTISCHE RÜCKMELDUNG ('explanation'):
   - Jede Interaktion MUSS eine verständliche Erklärung enthalten, die dem Schüler direkt nach der Beantwortung den Bezug zum Video bestätigt (z. B. "Richtig! Wie im Video bei 01:18 erklärt wurde, teilt die Subnetzmaske die IP-Adresse in Netz- und Hostanteil auf.").

5. DIGITALER WACHSENDER HEFTEINTRAG & ADAPTIVER RÜCKSPRUNG (FÜR JEDE AUFGABENANZAHL {task_count}):
   - 'full_hefteintrag': Erstelle ein sauberes, strukturiertes Gesamttafelbild für das Heft (Überschrift zum Thema + nummerierte Kernpunkte 1 bis {task_count}).
   - Für JEDEN Haltepunkt (unabhängig von der gewählten Aufgabenanzahl 1 bis {task_count}):
     * 'hefteintrag_point': Formuliere genau den 1 prägnanten didaktischen Merksatz für diesen Schritt (z. B. 'Eine IPv4-Adresse besteht aus vier 8-Bit-Zahlenblöcken (32 Bit), getrennt durch Punkte.'). Dieser Punkt erscheint digital im H5P-Video auf dem Tafelbild!
     * 'hefteintrag_step': Der kumulativ wachsende Hefteintrag bis zu diesem Schritt (Thema + alle bisherigen Punkte 1 bis aktuell + Schreibaufgabe für das Schulheft).
     * 'rewind_seconds': Die genaue Sekunde im Video, an der die Erklärung zu dieser konkreten Frage begonnen hat.
       STRIKTE REGEL: Maximal 10 bis maximal 30 Sekunden zurückspringen (niemals weiter als 30s zurück!). Ziel ist es, den Schüler punktgenau an die Stelle zurückzusetzen, an der die für die Frage benötigte Information genannt wird.
   - Mindestens einer der Haltepunkte sollte als didaktischer Merkkasten ('Infobox' oder 'Lückentext') gestaltet sein, der das Tafelbild hervorhebt.

Erstelle genau {task_count} passgenaue, chronologische Haltepunkte für dieses Video. Antworte ausschließlich im vorgegebenen JSON-Schema:
"""

        uploaded_gemini_files = []
        temp_files_to_remove = []
        try:
            contents, uploaded_gemini_files, temp_files_to_remove, detected_duration_sec = self._prepare_gemini_contents(
                client=client,
                files=files,
                youtube_url=youtube_url,
                video_duration=video_duration
            )

            if detected_duration_sec and detected_duration_sec > 15:
                m_dur, s_dur = divmod(detected_duration_sec, 60)
                max_stop_sec = max(15, detected_duration_sec - 8)
                m_max, s_max = divmod(max_stop_sec, 60)
                duration_header = (
                    f"ABSOLUTES ZEITLIMIT - STRENGSTE PFLICHT:\n"
                    f"- Die Gesamtlaufzeit dieses Videos beträgt EXAKT {m_dur:02d}:{s_dur:02d} ({detected_duration_sec} Sekunden)!\n"
                    f"- STRIKT VERBOTEN: Der allerletzte Haltepunkt darf HÖCHSTENS bei Sekunde {max_stop_sec} ({m_max:02d}:{s_max:02d}) liegen!\n"
                    f"- Haltepunkte danach zerstören das H5P-Video, weil sie hinter dem Videoende liegen. Verteile alle {task_count} Haltepunkte gleichmäßig zwischen 00:15 und {m_max:02d}:{s_max:02d}!\n\n"
                )
                contents.append(duration_header + prompt)
            else:
                contents.append(prompt)

            candidate_models = ['gemini-3.5-flash', 'gemini-3.5-flash-lite', 'gemini-3.1-flash-lite']
            last_err = None
            for model_name in candidate_models:
                try:
                    logger.info(f"Generating interactive video quiz with model '{model_name}' (duration constraint: {detected_duration_sec}s)...")
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
                        if detected_duration_sec:
                            parsed["video_duration_seconds"] = detected_duration_sec

                        # Validate, format, sort and CLAMP interactions strictly within video duration
                        if "interactions" in parsed and isinstance(parsed["interactions"], list):
                            interactions = parsed["interactions"]
                            for inter in interactions:
                                inter["time_seconds"] = int(inter.get("time_seconds", 0))

                            interactions.sort(key=lambda x: x.get("time_seconds", 0))

                            # Safety clamp: If video length is known, NEVER allow any checkpoint past the end!
                            if detected_duration_sec and detected_duration_sec > 15:
                                max_allowed = detected_duration_sec - 8
                                exceeds = any(inter.get("time_seconds", 0) > max_allowed for inter in interactions)
                                if exceeds:
                                    logger.warning(
                                        f"SAFETY CLAMP: Checkpoints exceeded video duration ({detected_duration_sec}s). "
                                        f"Rescaling {len(interactions)} checkpoints proportionally within [15, {max_allowed}]s."
                                    )
                                    n = len(interactions)
                                    if n > 0:
                                        step = (max_allowed - 15) / n
                                        for idx, inter in enumerate(interactions):
                                            safe_sec = int(15 + (idx + 0.5) * step)
                                            safe_sec = max(10, min(safe_sec, max_allowed - (n - 1 - idx) * 3))
                                            inter["time_seconds"] = safe_sec
                                            
                                            rw = inter.get("rewind_seconds")
                                            if rw is not None:
                                                inter["rewind_seconds"] = max(0, min(int(rw), max(0, safe_sec - 15)))

                            for inter in interactions:
                                ts = inter["time_seconds"]
                                m, s = divmod(ts, 60)
                                inter["time_formatted"] = f"{m:02d}:{s:02d}"

                        if "title" in parsed and parsed["title"]:
                            from .h5p_generator import clean_student_title
                            parsed["title"] = clean_student_title(parsed["title"])

                        logger.info(f"Successfully generated interactive video quiz for subject='{parsed.get('subject')}', title='{parsed.get('title')}' with {len(parsed.get('interactions', []))} checkpoints (duration: {detected_duration_sec}s)")
                        return parsed
                except Exception as e:
                    logger.warning(f"Interactive video generation failed with model {model_name}: {e}")
                    last_err = e

            logger.error(f"All models failed for interactive video: {last_err}")
            return self._get_mock_interactive_video(inferred_topic, subject, school_type, task_count, error_message=str(last_err), video_duration=detected_duration_sec)
        finally:
            self._cleanup_gemini_files(client, uploaded_gemini_files, temp_files_to_remove)

    def _get_mock_interactive_video(self, context: str = "", subject: str = "Informatik", school_type: str = "Mittelschule", task_count: int = 5, error_message: str = None, video_duration: int = None) -> dict:
        topic = context.strip() if context else ("IP-Adressen und Rechnernetze" if subject == "Informatik" else f"Grundlagen {subject}")
        is_ip_topic = any(k in topic.lower() for k in ['ip', 'netzwerk', 'informatik', 'subnetz', 'router'])
        
        if is_ip_topic:
            subject = "Informatik"
            interactions = [
                {
                    "time_seconds": 30,
                    "time_formatted": "00:30",
                    "title": "Aufbau einer IP-Adresse",
                    "hefteintrag_point": "Eine IP-Adresse dient zur eindeutigen Identifikation von Geräten im Netzwerk.",
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
                    "hefteintrag_point": "Eine klassische IPv4-Adresse besteht aus 32 Bit (4 Blöcken à 8 Bit, getrennt durch Punkte).",
                    "format": "Wahr/Falsch",
                    "question": "Eine klassische IPv4-Adresse besteht aus 32 Bit (4 Blöcken à 8 Bit, getrennt durch Punkte).",
                    "correct": True,
                    "explanation": "Richtig! IPv4-Adressen (z. B. 192.168.1.1) basieren auf 32 Bit und bieten etwa 4,3 Milliarden Adressen."
                },
                {
                    "time_seconds": 150,
                    "time_formatted": "02:30",
                    "title": "Lückentext-Merksatz",
                    "hefteintrag_point": "Die Subnetzmaske bestimmt, welcher Teil einer IP-Adresse das Netzwerk und welcher den Host identifiziert.",
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
                    "text": "Merke dir: Eine typische IPv4-Adresse besteht aus vier Zahlenblöcken, die durch Punkte getrennt sind (z. B. 192.168.1.45).\n\n✍️ **Aufgabe für dein Heft:** Übertrage diesen Merkkasten jetzt sauber in dein Schulheft!\n▶️ **So geht's weiter:** Klicke oben rechts auf das ✕ (Schließen) oder auf Play ▶, sobald du fertig geschrieben hast.",
                    "explanation": ""
                },
                {
                    "time_seconds": 270,
                    "time_formatted": "04:30",
                    "title": "💡 Merkkasten: IPv6 Zukunft",
                    "hefteintrag_point": "IPv6 löst IPv4 mit 128 Bit ab und bietet praktisch unbegrenzte Adressen für alle vernetzten Geräte.",
                    "format": "Multiple Choice",
                    "question": "Warum wird IPv6 weltweit als neuer Standard eingeführt?",
                    "answers": [
                        {"text": "Weil der Adressvorrat von IPv4 durch Milliarden vernetzter Geräte erschöpft ist", "correct": True},
                        {"text": "Weil IPv4 nur noch auf alten Röhrenmonitoren funktioniert", "correct": False},
                        {"text": "Weil IPv6 keine IP-Adressen mehr benötigt", "correct": False}
                    ],
                    "explanation": "Genau richtig! IPv6 bietet mit 128 Bit praktisch unbegrenzte Adressen für alle internetfähigen Geräte."
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
                    "hefteintrag_point": "Die Subnetzmaske bestimmt, welcher Teil einer IP-Adresse das Netzwerk und welcher den Host identifiziert.",
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
                },
                {
                    "time_seconds": 250,
                    "time_formatted": "04:10",
                    "title": "Abschluss-Check",
                    "format": "Multiple Choice",
                    "question": f"Welche Schlussfolgerung zieht das Video zu '{topic}'?",
                    "answers": [
                        {"text": "Das Gelernte sollte durch gezielte Übungsaufgaben vertieft werden", "correct": True},
                        {"text": "Das Thema ist ab sofort nicht mehr relevant", "correct": False},
                        {"text": "Es gibt keine weiteren Anwendungsmöglichkeiten", "correct": False}
                    ],
                    "explanation": "Richtig! Übung und Wiederholung festigen das erworbene Wissen."
                }
            ][:task_count]

        if video_duration and video_duration > 15 and interactions:
            max_limit = video_duration - 8
            step = (max_limit - 15) / len(interactions)
            for idx, inter in enumerate(interactions):
                safe_sec = int(15 + (idx + 0.5) * step)
                inter["time_seconds"] = safe_sec
                m, s = divmod(safe_sec, 60)
                inter["time_formatted"] = f"{m:02d}:{s:02d}"

        return {
            "title": topic,
            "video_mode": "interactive_video",
            "subject": subject,
            "school_type": school_type,
            "interactions": interactions,
            "error": error_message
        }


    def evaluate_essay(
        self,
        task_title: str,
        task_instruction: str,
        student_text: str,
        school_type: str = "Mittelschule",
        subject: str = "Deutsch",
        criteria: list = None,
        api_key: str = None
    ) -> dict:
        """
        Semantically evaluates a student essay / written text according to Bavarian LehrplanPLUS & ISB standards.
        Uses Gemini LLM for deep semantic reasoning, falling back to a pedagogical heuristic if offline.
        """
        student_text = (student_text or "").strip()
        if not student_text:
            return {
                "score": 0,
                "rating": "Noch kein Text",
                "praise": "Bitte tippe deinen Text ein, damit die KI ihn prüfen kann.",
                "tips": "Fange mit dem ersten Satz an!",
                "criteria_met": [],
                "corrections": [],
                "stats": {"word_count": 0, "sentence_count": 0},
                "revised_example": ""
            }

        client = None
        if api_key and api_key.strip():
            try:
                client = genai.Client(api_key=api_key.strip())
            except Exception as e:
                logger.error(f"Failed to initialize client with dynamic key: {e}")
        if not client:
            client = self.client

        if client:
            prompt = f"""Du bist ein einfühlsamer, hochkompetenter pädagogischer KI-Schreibcoach an bayerischen Schulen (LehrplanPLUS und ISB-Qualitätstableau).
Deine Aufgabe: Analysiere den Text eines Schülers der Schulart '{school_type}' im Fach '{subject}' semantisch, wertschätzend und konstruktiv.

AUFGABENSTELLUNG / THEMA:
Titel: {task_title}
Anweisung & Kriterien: {task_instruction}

TEXT DES SCHÜLERS:
<<<
{student_text}
>>>

DIDAKTISCHER AUFTRAG NACH DEM SCHREIBPROZESS-MODELL:
1. KRITERIEN-CHECK:
   - Wurde das Thema verstanden und die Anweisung beachtet?
   - Wurden geforderte sprachliche Vorgaben (z. B. Wortarten wie Präpositionen, Konjunktionen, Adverbien, Satzanzahl, Argumente) erfüllt?
   - Extrahiere die konkreten Nachweise (gefundene Wörter/Sätze) aus dem Schülertext für jedes Kriterium.
2. PÄDAGOGISCHES FEEDBACK (Wohlwollend & motivierend):
   - 'praise': Hebe ehrlich und ermutigend hervor, was dem Schüler inhaltlich, sprachlich oder kreativ schon sehr gut gelungen ist.
   - 'tips': Gib 1-2 konkrete, umsetzbare Tipps zur Überarbeitung (z. B. Satzverknüpfungen, treffende Verben/Adjektive, Satzanfänge).
3. MECHANIK & SPRACHRICHTIGKEIT:
   - 'corrections': Finde Rechtschreib- oder Grammatikfehler im Text und erkläre sie freundlich (Original, Korrektur, Erklärung).
4. GESAMTBEWERTUNG:
   - 'score': 0 bis 100 Punkte (Prozentsatz der Kriterienerfüllung & Textqualität).
   - 'rating': Z. B. 'Hervorragend! 🌟', 'Tolle Leistung! 🚀', 'Auf gutem Weg! 💡' oder 'Guter Anfang! 💪'.
   - 'stats': Anzahl Wörter ('word_count') und Sätze ('sentence_count').
   - 'revised_example': 1 beispielhaft veredelter Satz als Inspiration.

Antworte ausschließlich in folgendem validen JSON:
{{
  "score": 85,
  "rating": "Tolle Leistung! 🌟",
  "praise": "Dein Text beschreibt ... besonders anschaulich.",
  "tips": "Versuche beim nächsten Entwurf noch ...",
  "criteria_met": [
    {{"name": "Thema getroffen", "fulfilled": true, "details": "Thema gut erfasst"}},
    {{"name": "Mindestens 2 Präpositionen", "fulfilled": true, "details": "Gefunden: in, auf"}}
  ],
  "corrections": [
    {{"original": "werckstatt", "suggestion": "Werkstatt", "explanation": "'Werkstatt' schreibt man ohne c."}}
  ],
  "stats": {{
    "word_count": 42,
    "sentence_count": 5
  }},
  "revised_example": "Hier ist eine Inspiration für einen eleganten Satz..."
}}
"""
            candidate_models = ['gemini-3.5-flash', 'gemini-3.5-flash-lite', 'gemini-3.1-flash-lite']
            for model_name in candidate_models:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.3
                        )
                    )
                    if response and response.text:
                        parsed = json.loads(response.text)
                        if isinstance(parsed, dict) and "score" in parsed:
                            logger.info(f"Successfully evaluated essay with Gemini model {model_name}")
                            return parsed
                except Exception as eval_err:
                    logger.warning(f"Gemini essay eval with {model_name} failed: {eval_err}")

        # Fallback to intelligent pedagogical heuristic
        return self._evaluate_essay_heuristic(task_title, task_instruction, student_text, school_type, subject)

    def _evaluate_essay_heuristic(
        self,
        task_title: str,
        task_instruction: str,
        student_text: str,
        school_type: str = "Mittelschule",
        subject: str = "Deutsch"
    ) -> dict:
        """
        High-fidelity heuristic pedagogical evaluation for offline usage or fallback.
        Analyzes sentence structure, word counts, grammatical keywords (prepositions, conjunctions, adverbs)
        and formats encouraging ISB-compliant feedback.
        """
        clean_text = student_text.strip()
        sentences = [s.strip() for s in re.split(r'[.!?]+', clean_text) if s.strip()]
        words = re.findall(r'\b[\wÄÖÜäöüß-]+\b', clean_text)
        word_count = len(words)
        sentence_count = len(sentences)

        lower_words = [w.lower() for w in words]
        
        # Word lists
        prepositions = {"in", "an", "auf", "unter", "über", "vor", "hinter", "neben", "zwischen", "mit", "nach", "von", "zu", "aus", "bei", "seit", "durch", "für", "gegen", "ohne", "um", "trotz", "während", "wegen", "ab", "bis", "entlang"}
        conjunctions = {"weil", "da", "dass", "daß", "sodass", "obwohl", "wenn", "falls", "als", "während", "bevor", "nachdem", "und", "oder", "aber", "denn", "sondern", "doch", "jedoch", "damit"}
        adverbs = {"heute", "gestern", "morgen", "oft", "selten", "immer", "nie", "manchmal", "hier", "da", "dort", "überall", "sehr", "besonders", "vielleicht", "gerne", "leider", "deshalb", "darum", "zuerst", "dann", "schließlich", "bald", "bereits", "noch", "fast", "kaum", "wirklich"}

        found_prep = list(dict.fromkeys([w for w in lower_words if w in prepositions]))
        found_conj = list(dict.fromkeys([w for w in lower_words if w in conjunctions]))
        found_adv = list(dict.fromkeys([w for w in lower_words if w in adverbs]))

        criteria_met = []
        inst_lower = (task_instruction + " " + task_title).lower()

        # Criterion 1: General content & length
        has_min_words = word_count >= 12
        criteria_met.append({
            "name": "Themenbezug & Mindestlänge",
            "fulfilled": has_min_words,
            "details": f"{word_count} Wörter verfasst (mind. 12 empfohlen)" if has_min_words else f"Bisher erst {word_count} Wörter – schreibe noch etwas mehr!"
        })

        # Criterion 2: Sentence count if mentioned
        if "satz" in inst_lower or "sätze" in inst_lower:
            m_sc = re.search(r'(\d+)\s*sätze', inst_lower)
            target_sc = int(m_sc.group(1)) if m_sc else 4
            sc_met = sentence_count >= max(2, target_sc - 1)
            criteria_met.append({
                "name": f"Satzanzahl (Ziel: ca. {target_sc} Sätze)",
                "fulfilled": sc_met,
                "details": f"{sentence_count} vollständige Sätze erkannt" if sc_met else f"Bisher {sentence_count} Sätze – formuliere noch {target_sc - sentence_count} weitere Sätze."
            })

        # Criterion 3: Prepositions
        if "präposition" in inst_lower:
            prep_met = len(found_prep) >= 2
            criteria_met.append({
                "name": "Mindestens 2 Präpositionen",
                "fulfilled": prep_met,
                "details": f"Gefunden: {', '.join(found_prep[:4])}" if prep_met else (f"Bisher nur '{found_prep[0]}'" if found_prep else "Keine Präpositionen (z. B. in, auf, mit, bei) gefunden")
            })

        # Criterion 4: Conjunctions
        if "konjunktion" in inst_lower or "bindewort" in inst_lower:
            conj_met = len(found_conj) >= 2
            criteria_met.append({
                "name": "Mindestens 2 Konjunktionen (Bindewörter)",
                "fulfilled": conj_met,
                "details": f"Gefunden: {', '.join(found_conj[:4])}" if conj_met else (f"Bisher nur '{found_conj[0]}'" if found_conj else "Baue Bindewörter wie 'weil', 'dass' oder 'obwohl' ein")
            })

        # Criterion 5: Adverbs
        if "adverb" in inst_lower or "umstandswort" in inst_lower:
            adv_met = len(found_adv) >= 2
            criteria_met.append({
                "name": "Mindestens 2 Adverbien",
                "fulfilled": adv_met,
                "details": f"Gefunden: {', '.join(found_adv[:4])}" if adv_met else (f"Bisher nur '{found_adv[0]}'" if found_adv else "Verwende Umstandswörter wie 'oft', 'gerne', 'heute' oder 'besonders'")
            })

        # Score calculation
        met_count = sum(1 for c in criteria_met if c["fulfilled"])
        total_criteria = len(criteria_met) or 1
        score = int(round((met_count / total_criteria) * 100))
        if word_count < 10:
            score = min(score, 40)

        # Rating label
        if score >= 90:
            rating = "Hervorragend gelöst! 🌟"
            praise = f"Klasse Leistung! Du hast die Kriterien für '{task_title}' vorbildlich umgesetzt und deinen Text flüssig formuliert."
            tips = "Achte beim nächsten Mal auf noch abwechslungsreichere Satzanfänge, um deinen Text noch lebendiger zu machen."
        elif score >= 70:
            rating = "Tolle Leistung! 🚀"
            praise = f"Sehr gut! Dein Text zum Thema '{task_title}' ist verständlich geschrieben und greift wichtige Vorgaben auf."
            tips = "Schau dir die Kriterien-Checkliste an: Wenn du noch fehlende Elemente ergänzt, wird dein Text perfekt!"
        elif score >= 50:
            rating = "Auf gutem Weg! 💡"
            praise = "Du hast schon einen guten Anfang gefunden und deine Gedanken aufgeschrieben."
            tips = "Lies dir die Aufgabenstellung noch einmal genau durch und baue die noch fehlenden Wortarten oder Sätze ein."
        else:
            rating = "Guter Ansatz – erweitere deinen Text! 💪"
            praise = "Schön, dass du angefangen hast zu schreiben."
            tips = "Schreibe noch ein paar Sätze dazu und achte auf die Kriterien aus der Aufgabenstellung."

        # Detect common typos for corrections list
        corrections = []
        typo_patterns = [
            (r'\b(dass|daß)\b', "dass", "Konjunktion 'dass' mit Doppel-s."),
            (r'\bwerckstatt\b', "Werkstatt", "'Werkstatt' wird ohne c geschrieben."),
            (r'\bmaschine\b', "Maschine", "Nomen werden großgeschrieben."),
            (r'\bviel leicht\b', "vielleicht", "'vielleicht' wird zusammen geschrieben.")
        ]
        for pat, fix, rule in typo_patterns:
            m = re.search(pat, clean_text, re.IGNORECASE)
            if m and m.group(0) != fix:
                corrections.append({
                    "original": m.group(0),
                    "suggestion": fix,
                    "explanation": rule
                })

        revised = (
            f"Beispiel zur Inspiration: 'Wenn ich an {task_title} denke, "
            f"möchte ich besonders gerne mit Menschen arbeiten, weil mir das große Freude macht.'"
        )

        return {
            "score": score,
            "rating": rating,
            "praise": praise,
            "tips": tips,
            "criteria_met": criteria_met,
            "corrections": corrections,
            "stats": {
                "word_count": word_count,
                "sentence_count": sentence_count
            },
            "revised_example": revised
        }
