import sys
import os
import json
import logging
import asyncio
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional

# Ensure backend directory is in sys.path for reliable module imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from h5p_generator import H5PGenerator
from ai_service import AIService
from pdf_generator import PDFGenerator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("adaptify")

# Configuration for User API Key or Promo/Subscription enforcement
REQUIRE_USER_KEY_OR_PROMO = os.environ.get("REQUIRE_USER_KEY_OR_PROMO", "False").lower() in ("true", "1", "yes")
VALID_PROMO_CODES = {"SCHULE2026", "PROMO100", "LEHRER2026", "DIDACTA", "PREMIUM_USER", "ABO_ACTIVE"}

app = FastAPI(
    title="Adaptify API",
    description="Backend API for generating differentiated H5P and PDF tasks from book pages/PDFs.",
    version="1.0.0"
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
@app.get("/api/health")
def health_check():
    return {"status": "ok", "app": "Adaptify"}

# Custom Middleware to disable stale browser caching for live classroom updates
@app.middleware("http")
async def add_no_cache_headers(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path.lower()
    if path.endswith(('.html', '.js', '.css', '.json', '.webmanifest')) or path in ['/', '/play.html']:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# Initialize AI Service
ai_service = AIService()

class DiagnosticQuestion(BaseModel):
    question: str
    options: List[str]
    correct: int

class DiagnosticQuiz(BaseModel):
    questions: List[DiagnosticQuestion]

class Task(BaseModel):
    title: str
    text: str
    format: str
    hint: Optional[str] = ""
    explanation: Optional[str] = ""

class LevelContent(BaseModel):
    title: str
    tasks: List[Task]

class Hefteintrag(BaseModel):
    title: Optional[str] = "Hefteintrag / Merkkasten"
    summary: Optional[str] = ""
    level_a_notes: Optional[str] = ""
    level_b_notes: Optional[str] = ""

class Zusatzaufgabe(BaseModel):
    title: str
    task: str

class ExportData(BaseModel):
    title: str
    target_format: str = "Lückentext"
    diagnostic: DiagnosticQuiz
    hefteintrag: Optional[Hefteintrag] = None
    zusatzaufgaben: Optional[List[Zusatzaufgabe]] = []
    level_a: LevelContent
    level_b: LevelContent
    level_c: Optional[dict] = None
    lehrplan_code: Optional[str] = ""
    lehrplan_competency: Optional[str] = ""
    solution_url: Optional[str] = ""
    session_pin: Optional[str] = ""
    pdf_teacher_name: Optional[str] = ""
    pdf_class_name: Optional[str] = ""
    pdf_accent_color: Optional[str] = "#0f172a"
    pdf_logo_base64: Optional[str] = None
    pdf_include_lehrplan: Optional[bool] = False
    pdf_include_level_c: Optional[bool] = False
    pdf_include_qr: Optional[bool] = True
    include_level_c: Optional[bool] = False

@app.post("/api/generate")
async def generate_task(
    file: UploadFile = File(...),
    subject: str = Form("Deutsch"),
    school_type: str = Form("Grundschule"),
    focus_topic: str = Form(""),
    hefteintrag_topic: str = Form(""),
    context: str = Form(""),
    target_format: str = Form("Lückentext"),
    task_count: int = Form(1),
    api_key: Optional[str] = Form(None),
    promo_code: Optional[str] = Form(None)
):
    """
    Receives an uploaded book page scan (image or PDF) and generates
    differentiated task content, board entries, and extension tasks using Gemini Vision.
    """
    logger.info(f"Received file: {file.filename}, school_type: {school_type}, subject: {subject}, focus: {focus_topic}, hefteintrag_topic: {hefteintrag_topic}, context: {context}, format: {target_format}, count: {task_count}, promo: {promo_code}")
    
    # Check subscription / BYOK credentials
    effective_api_key = api_key
    has_valid_key = bool(api_key and api_key.strip())
    has_valid_promo = bool(promo_code and promo_code.strip().upper() in VALID_PROMO_CODES)
    
    if REQUIRE_USER_KEY_OR_PROMO:
        if not (has_valid_key or has_valid_promo):
            logger.warning("Access denied: missing or invalid key/promo code.")
            raise HTTPException(
                status_code=403,
                detail="Ein gültiger Gemini API-Key (BYOK) oder ein aktiver Abo-/Schul-Code ist erforderlich. Bitte trage diesen in den Einstellungen ein."
            )
            
    if has_valid_promo:
        logger.info(f"Valid promo code / subscription applied: {promo_code}")
        # When promo code is active, force backend to use the host/server API key
        effective_api_key = None
        
    # Read file content
    contents = await file.read()
    
    # Determine MIME type
    mime_type = file.content_type
    if not mime_type:
        # Fallback based on extension
        ext = os.path.splitext(file.filename)[1].lower()
        if ext in ['.jpg', '.jpeg']:
            mime_type = 'image/jpeg'
        elif ext == '.png':
            mime_type = 'image/png'
        elif ext == '.pdf':
            mime_type = 'application/pdf'
        else:
            mime_type = 'image/jpeg'
            
    # Call Gemini API
    result = await asyncio.to_thread(
        ai_service.generate_differentiated_content,
        file_content=contents,
        mime_type=mime_type,
        context=context,
        target_format=target_format,
        task_count=task_count,
        subject=subject,
        school_type=school_type,
        focus_topic=focus_topic,
        hefteintrag_topic=hefteintrag_topic,
        api_key=effective_api_key
    )
    
    return result

import re
from urllib.parse import quote

def make_content_disposition(title: str, suffix: str) -> str:
    # Strictly limit raw_filename to ASCII characters [a-zA-Z0-9_-] so Starlette latin-1 header encoding succeeds
    clean_title = re.sub(r'[^a-zA-Z0-9_-]', '_', title).strip('_')
    if not clean_title:
        clean_title = "Adaptify_Uebung"
    raw_filename = f"{clean_title}_{suffix}"
    utf8_filename = quote(f"{title}_{suffix}")
    return f'attachment; filename="{raw_filename}"; filename*=UTF-8\'\'{utf8_filename}'

class RefineTaskRequest(BaseModel):
    task: dict
    instruction: str
    subject: str = "Deutsch"
    school_type: str = "Grundschule"
    api_key: Optional[str] = None

@app.post("/api/refine_task")
async def refine_task(req: RefineTaskRequest):
    """
    Refines a single task based on prompt instruction from teacher.
    """
    try:
        updated = await asyncio.to_thread(
            ai_service.refine_single_task,
            task_data=req.task,
            instruction=req.instruction,
            subject=req.subject,
            school_type=req.school_type,
            api_key=req.api_key
        )
        return updated
    except Exception as e:
        logger.error(f"Error in refine_task endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Aufgaben-Anpassung fehlgeschlagen: {str(e)}")

@app.post("/api/export/h5p")
async def export_h5p(data: ExportData):
    """
    Takes the structured task JSON and builds the H5P Branching Scenario zip file.
    """
    try:
        h5p_bytes = H5PGenerator.create_h5p_zip(data.dict())
        disposition = make_content_disposition(data.title, "differenziert.h5p")
        
        return Response(
            content=h5p_bytes,
            media_type="application/zip",
            headers={
                "Content-Disposition": disposition
            }
        )
    except Exception as e:
        logger.error(f"Error generating H5P: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"H5P-Generierung fehlgeschlagen: {str(e)}")

@app.post("/api/export/pdf")
async def export_pdf(data: ExportData):
    """
    Takes the structured task JSON and generates a premium print-ready PDF worksheet.
    """
    try:
        pdf_bytes = PDFGenerator.generate_worksheet_pdf(data.dict())
        disposition = make_content_disposition(data.title, "arbeitsblatt.pdf")
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": disposition
            }
        )
    except Exception as e:
        logger.error(f"Error generating PDF: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"PDF-Generierung fehlgeschlagen: {str(e)}")

from scorm_generator import SCORMGenerator

@app.post("/api/export/scorm")
async def export_scorm(data: ExportData):
    """
    Takes structured task JSON and creates a SCORM 1.2 package (.zip) for mebis/Moodle LMS import.
    """
    try:
        scorm_bytes = SCORMGenerator.create_scorm_zip(data.dict())
        disposition = make_content_disposition(data.title, "scorm_paket.zip")
        
        return Response(
            content=scorm_bytes,
            media_type="application/zip",
            headers={
                "Content-Disposition": disposition
            }
        )
    except Exception as e:
        logger.error(f"Error generating SCORM: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"SCORM-Generierung fehlgeschlagen: {str(e)}")

import socket
import random
import datetime

# Store active sessions in memory
active_sessions = {}
SESSIONS_FILE = "data/sessions_db.json"

def load_sessions():
    global active_sessions
    os.makedirs("data", exist_ok=True)
    if os.path.exists(SESSIONS_FILE):
        try:
            with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
                active_sessions = json.load(f)
            logger.info(f"Loaded {len(active_sessions)} sessions from database.")
        except Exception as e:
            logger.error(f"Failed to load sessions database: {e}")
            active_sessions = {}
    else:
        active_sessions = {}

def save_sessions():
    os.makedirs("data", exist_ok=True)
    try:
        with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(active_sessions, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save sessions database: {e}")

load_sessions()

class StudentSubmission(BaseModel):
    student_name: str
    score: int
    max_score: int
    level_reached: str
    answers_detail: Optional[list] = None

@app.get("/api/system/ip")
def get_system_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return {"ip": ip}
    except Exception:
        return {"ip": "127.0.0.1"}

@app.post("/api/sessions/create")
def create_session(data: dict):
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    for _ in range(50):
        pin = "".join(random.choices(chars, k=4))
        if pin not in active_sessions:
            active_sessions[pin] = {
                "title": data.get("title", "Direktspiel"),
                "data": data,
                "results": []
            }
            save_sessions()
            return {"pin": pin}
    raise HTTPException(status_code=500, detail="Konnte keinen eindeutigen PIN generieren.")

@app.get("/api/sessions/{pin}")
def get_session(pin: str):
    pin = pin.upper()
    if pin not in active_sessions:
        raise HTTPException(status_code=404, detail="Sitzung nicht gefunden oder abgelaufen.")
    return active_sessions[pin]["data"]

@app.post("/api/sessions/{pin}/submit")
def submit_session_result(pin: str, submission: StudentSubmission):
    pin = pin.upper()
    if pin not in active_sessions:
        raise HTTPException(status_code=404, detail="Sitzung nicht gefunden.")
    
    result_record = submission.dict()
    result_record["timestamp"] = datetime.datetime.now().strftime("%H:%M:%S")
    
    # Update existing entry if student name matches, else append
    results = active_sessions[pin]["results"]
    updated = False
    for i, r in enumerate(results):
        if r.get("student_name").lower() == submission.student_name.lower():
            results[i] = result_record
            updated = True
            break
            
    if not updated:
        results.append(result_record)
        
    save_sessions()
    return {"status": "success"}

@app.get("/api/sessions/{pin}/results")
def get_session_results(pin: str):
    pin = pin.upper()
    if pin not in active_sessions:
        raise HTTPException(status_code=404, detail="Sitzung nicht gefunden.")
    return {
        "title": active_sessions[pin]["title"],
        "results": active_sessions[pin]["results"]
    }

@app.get("/api/teacher/analytics")
def get_teacher_analytics():
    student_stats = {}
    
    for pin, session in active_sessions.items():
        title = session.get("title", "Unbenannte Übung")
        results = session.get("results", [])
        for r in results:
            name = r.get("student_name")
            if not name:
                continue
                
            if name not in student_stats:
                student_stats[name] = {
                    "student_name": name,
                    "completed_count": 0,
                    "total_score": 0,
                    "total_max_score": 0,
                    "levels": [],
                    "history": []
                }
                
            student_stats[name]["completed_count"] += 1
            student_stats[name]["total_score"] += r.get("score", 0)
            student_stats[name]["total_max_score"] += r.get("max_score", 0)
            student_stats[name]["levels"].append(r.get("level_reached", "A"))
            student_stats[name]["history"].append({
                "pin": pin,
                "title": title,
                "score": r.get("score", 0),
                "max_score": r.get("max_score", 0),
                "level_reached": r.get("level_reached", "A"),
                "timestamp": r.get("timestamp", ""),
                "answers_detail": r.get("answers_detail", [])
            })
            
    return list(student_stats.values())

# Mount static frontend directory at /
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "www"))
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
else:
    logger.warning(f"Frontend directory not found at {frontend_dir}. API endpoints are ready, but static files will not be served.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=False)
