# -*- coding: utf-8 -*-
with open('frontend/www/app.js', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update SCHOOL_SUBJECTS
old_school = '''const SCHOOL_SUBJECTS = {
    "Grundschule": [
        "Deutsch", "Mathematik", "Heimat- und Sachunterricht (HSU)", "Englisch", "Religion / Ethik", "Kunst", "Musik"
    ],
    "Mittelschule": [
        "Deutsch", "Mathematik", "Englisch", "Natur und Technik (NT)", "Geschichte / Politik / Geographie (GPG)", "Wirtschaft und Beruf (WiB)", "Religion / Ethik", "Kunst / Musik"
    ],
    "Realschule": [
        "Deutsch", "Mathematik", "Englisch", "Physik", "Chemie", "Biologie", "Geschichte", "Geographie", "BwR / Wirtschaft & Recht", "Französisch", "Religion / Ethik"
    ],
    "Gymnasium": [
        "Deutsch", "Mathematik", "Englisch", "Latein", "Französisch", "Physik", "Chemie", "Biologie", "Geschichte", "Geographie", "Wirtschaft & Recht", "Religion / Ethik"
    ]
};'''

new_school = '''const SCHOOL_SUBJECTS = {
    "Grundschule": [
        "KI (Automatisch)", "Deutsch", "Mathematik", "Heimat- und Sachunterricht (HSU)", "Englisch", "Religion / Ethik", "Kunst", "Musik"
    ],
    "Mittelschule": [
        "KI (Automatisch)", "Deutsch", "Mathematik", "Englisch", "Natur und Technik (NT)", "Geschichte / Politik / Geographie (GPG)", "Wirtschaft und Beruf (WiB)", "Religion / Ethik", "Kunst / Musik"
    ],
    "Realschule": [
        "KI (Automatisch)", "Deutsch", "Mathematik", "Englisch", "Physik", "Chemie", "Biologie", "Geschichte", "Geographie", "BwR / Wirtschaft & Recht", "Französisch", "Religion / Ethik"
    ],
    "Gymnasium": [
        "KI (Automatisch)", "Deutsch", "Mathematik", "Englisch", "Latein", "Französisch", "Physik", "Chemie", "Biologie", "Geschichte", "Geographie", "Wirtschaft & Recht", "Religion / Ethik"
    ]
};'''
content = content.replace(old_school, new_school)

# 2. Update selectedSubjects
content = content.replace('let selectedSubjects = ["Deutsch"];', 'let selectedSubjects = ["KI (Automatisch)"];')

# 3. Update subjectEmojis
old_emojis = '''    const subjectEmojis = {
        "Deutsch": "📚",'''
new_emojis = '''    const subjectEmojis = {
        "KI (Automatisch)": "🤖",
        "Deutsch": "📚",'''
content = content.replace(old_emojis, new_emojis)

# 4. Update dynamicTopics init
old_topics = '''let dynamicTopics = [
    { name: "Textverständnis", count: 2 },
    { name: "Wortarten & Grammatik", count: 2 },
    { name: "Fremdwörter", count: 1 }
];'''
new_topics = '''let dynamicTopics = [
    { name: "KI wählt Schwerpunkte automatisch aus dem Text", count: 5 }
];'''
content = content.replace(old_topics, new_topics)

# 5. Update resetDefaultTopics
old_reset = '''window.resetDefaultTopics = function() {
    dynamicTopics = [
        { name: "Textverständnis", count: 2 },
        { name: "Wortarten & Grammatik", count: 2 },
        { name: "Fremdwörter", count: 1 }
    ];
    renderDynamicTopicRows();
};'''
new_reset = '''window.resetDefaultTopics = function() {
    dynamicTopics = [
        { name: "KI wählt Schwerpunkte automatisch aus dem Text", count: 5 }
    ];
    renderDynamicTopicRows();
};'''
content = content.replace(old_reset, new_reset)

with open('frontend/www/app.js', 'w', encoding='utf-8') as f:
    f.write(content)
print("Success app.js patch")
