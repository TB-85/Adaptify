# -*- coding: utf-8 -*-
with open('backend/ai_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace title instruction
old_title_prompt = '''"title": "Titel der Übung (z.B. {school_type} - {subject}: {focus_topic if focus_topic else \\'Unterrichtspaket\\'})"'''
new_title_prompt = '''"title": "Aussagekräftiger Titel der Übung (z.B. '{focus_topic if focus_topic else \\'Unterrichtspaket\\'}'). Verwende NUR den Titel, schreibe NICHT die Schulart oder das Fach dazu!"'''
content = content.replace(old_title_prompt, new_title_prompt)

# Replace summary instruction
old_summary_prompt = '''"summary": "Einheitlicher Klassen-Hefteintrag (1:1 ins Merkheft übertragbar im Format: 1. MERKREGEL, 2. SCHRITTE ZUR ANWENDUNG und 3. MUSTERBEISPIEL)"'''
new_summary_prompt = '''"summary": "Einheitlicher Klassen-Hefteintrag im HTML-Format (WICHTIG!). Aufbau zwingend so:\\n<p><strong>1. Merke:</strong> [Hier der allgemeine Merksatz]</p>\\n<p><strong>2. [Passende Frage zum Thema, z.B. Wie entstehen nun Erdöl, Erdgas oder Kohle?]:</strong> [Erklärung, wobei neue Gedanken, neue Punkte und neue Handlungen zwingend durch <br> getrennt in eine neue Zeile kommen, damit es übersichtlicher ist]</p>\\n<p><strong>3. Beispiel:</strong> [Das Beispiel]</p>\\nWichtige Begriffe im Text müssen zwingend mit <strong>fett</strong> markiert werden."'''
content = content.replace(old_summary_prompt, new_summary_prompt)

with open('backend/ai_service.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Success")
