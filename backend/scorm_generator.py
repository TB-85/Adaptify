import io
import json
import zipfile

class SCORMGenerator:
    @staticmethod
    def create_scorm_zip(data: dict) -> bytes:
        """
        Creates a SCORM 1.2 compliant ZIP package containing imsmanifest.xml
        and player HTML with LMS gradebook reporting.
        """
        title = data.get("title", "Differenzierte Übung")
        safe_title = title.replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
        data_json = json.dumps(data, ensure_ascii=False)
        
        # SCORM 1.2 imsmanifest.xml
        imsmanifest_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<manifest identifier="ADAPTIFY_SCORM_{abs(hash(title))}" version="1.2"
          xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2"
          xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2"
          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
          xsi:schemaLocation="http://www.imsproject.org/xsd/imscp_rootv1p1p2 imscp_rootv1p1p2.xsd
                              http://www.adlnet.org/xsd/adlcp_rootv1p2 adlcp_rootv1p2.xsd">
  <metadata>
    <schema>ADL SCORM</schema>
    <schemaversion>1.2</schemaversion>
  </metadata>
  <organizations default="adaptify_org">
    <organization identifier="adaptify_org">
      <title>{safe_title}</title>
      <item identifier="item_1" identifierref="resource_1">
        <title>{safe_title}</title>
      </item>
    </organization>
  </organizations>
  <resources>
    <resource identifier="resource_1" type="webcontent" adlcp:scormtype="sco" href="scorm_player.html">
      <file href="scorm_player.html"/>
    </resource>
  </resources>
</manifest>
"""

        # Player HTML with SCORM 1.2 API integration
        scorm_player_html = f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{safe_title}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <script src="https://cdn.jsdelivr.net/npm/canvas-confetti@1.6.0/dist/confetti.browser.min.js"></script>
    <script>
        // SCORM 1.2 API Connector Wrapper
        let scormAPI = null;
        function findAPI(win) {{
            let attempts = 0;
            while ((win.API == null) && (win.parent != null) && (win.parent != win)) {{
                attempts++;
                if (attempts > 10) return null;
                win = win.parent;
            }}
            return win.API;
        }}
        function initSCORM() {{
            scormAPI = findAPI(window);
            if (!scormAPI && window.opener) {{
                scormAPI = findAPI(window.opener);
            }}
            if (scormAPI) {{
                scormAPI.LMSInitialize("");
                scormAPI.LMSSetValue("cmi.core.lesson_status", "incomplete");
                scormAPI.LMSCommit("");
            }}
        }}
        function reportSCORMScore(score, maxScore) {{
            if (scormAPI) {{
                scormAPI.LMSSetValue("cmi.core.score.raw", score.toString());
                scormAPI.LMSSetValue("cmi.core.score.max", maxScore.toString());
                scormAPI.LMSSetValue("cmi.core.score.min", "0");
                const percent = (score / maxScore) * 100;
                if (percent >= 50) {{
                    scormAPI.LMSSetValue("cmi.core.lesson_status", "passed");
                }} else {{
                    scormAPI.LMSSetValue("cmi.core.lesson_status", "failed");
                }}
                scormAPI.LMSCommit("");
                scormAPI.LMSFinish("");
            }}
        }}
        window.onload = initSCORM;
    </script>
</head>
<body class="bg-slate-50 text-slate-800 font-sans p-6">
    <div class="max-w-2xl mx-auto bg-white rounded-3xl shadow-xl p-6 border border-slate-200 space-y-6">
        <div class="flex items-center justify-between border-b pb-4">
            <h2 class="text-xl font-black text-slate-900">{safe_title}</h2>
            <span class="text-xs font-bold text-brand-600 bg-brand-50 px-3 py-1 rounded-full">SCORM LMS Modul</span>
        </div>
        
        <div id="scorm-content" class="space-y-4">
            <p class="text-sm text-slate-600">Willkommen zu deiner Übung! Starte mit den Fragen unten.</p>
            <div id="quiz-container" class="space-y-4"></div>
            <button id="btn-submit-scorm" onclick="submitSCORM()" class="w-full py-3 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-2xl shadow-lg transition-all text-sm">
                Antworten abgeben &amp; ins LMS eintragen
            </button>
        </div>
        <div id="scorm-feedback" class="hidden text-center py-6 space-y-3">
            <div class="text-4xl text-emerald-500 font-black" id="scorm-score-text">100%</div>
            <p class="text-sm font-bold text-slate-700">Deine Punkte wurden erfolgreich an das LMS-Notenbuch übermittelt!</p>
        </div>
    </div>

    <script>
        const sessionData = {data_json};
        let currentScore = 0;
        let maxScore = 10;

        function renderSCORMQuiz() {{
            const container = document.getElementById('quiz-container');
            const questions = sessionData.diagnostic?.questions || [];
            maxScore = questions.length * 5;
            
            container.innerHTML = questions.map((q, qIdx) => `
                <div class="p-4 bg-slate-50 border border-slate-200 rounded-2xl space-y-2">
                    <p class="text-sm font-bold text-slate-800">${{q.question}}</p>
                    <div class="space-y-1.5">
                        ${{q.options.map((opt, oIdx) => `
                            <label class="flex items-center gap-2 text-xs font-medium text-slate-700 cursor-pointer p-2 bg-white rounded-xl border hover:border-brand-300">
                                <input type="radio" name="scorm_q_${{qIdx}}" value="${{oIdx}}" class="text-brand-600">
                                <span>${{opt}}</span>
                            </label>
                        `).join('')}}
                    </div>
                </div>
            `).join('');
        }}
        renderSCORMQuiz();

        function submitSCORM() {{
            const questions = sessionData.diagnostic?.questions || [];
            currentScore = 0;
            questions.forEach((q, qIdx) => {{
                const selected = document.querySelector(`input[name="scorm_q_${{qIdx}}"]:checked`);
                if (selected && parseInt(selected.value) === q.correct) {{
                    currentScore += 5;
                }}
            }});
            
            reportSCORMScore(currentScore, maxScore);
            
            document.getElementById('scorm-content').classList.add('hidden');
            document.getElementById('scorm-feedback').classList.remove('hidden');
            document.getElementById('scorm-score-text').textContent = `Ergebnis: ${{currentScore}} / ${{maxScore}} Punkte`;
            
            if (typeof confetti === 'function') {{
                confetti({{ particleCount: 100, spread: 70, origin: {{ y: 0.6 }} }});
            }}
        }}
    </script>
</body>
</html>
"""

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("imsmanifest.xml", imsmanifest_xml)
            zf.writestr("scorm_player.html", scorm_player_html)
            
        return zip_buffer.getvalue()
