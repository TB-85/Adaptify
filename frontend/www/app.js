// App State
let appState = {
    selectedFile: null,
    generatedData: null,
    previewDataUrl: null,
};

// DOM Elements
const screenUpload = document.getElementById('screen-upload');
const screenEditor = document.getElementById('screen-editor');
const screenExport = document.getElementById('screen-export');
const screenAnalytics = document.getElementById('screen-analytics');

const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const fileInfo = document.getElementById('file-info');
const fileName = document.getElementById('file-name');
const fileSize = document.getElementById('file-size');
const btnRemoveFile = document.getElementById('btn-remove-file');
const btnSubmit = document.getElementById('btn-submit');
const loader = document.getElementById('loader');

// Settings Inputs
const inputSchoolType = document.getElementById('input-school-type');
const subjectChipsContainer = document.getElementById('subject-chips-container');
const crossCurricularBadge = document.getElementById('cross-curricular-badge');
const crossCurricularText = document.getElementById('cross-curricular-text');
const inputFocusTopic = document.getElementById('input-focus-topic');
const inputHefteintragTopic = document.getElementById('input-hefteintrag-topic');
const inputFormat = document.getElementById('input-format');
const inputTaskCount = document.getElementById('input-task-count');
const inputPromoCode = document.getElementById('input-promo-code');
const inputApiKey = document.getElementById('input-api-key');
const inputContext = document.getElementById('input-context');

const SCHOOL_SUBJECTS = {
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
};

let selectedSubjects = ["Deutsch"];

function renderSubjectChips() {
    if (!subjectChipsContainer) return;
    const currentSchoolType = inputSchoolType ? inputSchoolType.value : "Grundschule";
    const availableSubjects = SCHOOL_SUBJECTS[currentSchoolType] || SCHOOL_SUBJECTS["Grundschule"];
    
    // Clean up selected subjects to only keep valid ones for this school type, or default to first
    selectedSubjects = selectedSubjects.filter(s => availableSubjects.includes(s));
    if (selectedSubjects.length === 0 && availableSubjects.length > 0) {
        selectedSubjects = [availableSubjects[0]];
    }

    const subjectEmojis = {
        "Deutsch": "📘",
        "Mathematik": "📙",
        "Englisch": "🟪",
        "Natur und Technik (NT)": "🟩",
        "Geschichte / Politik / Geographie (GPG)": "🟨",
        "Heimat- und Sachunterricht (HSU)": "🌱",
        "Physik": "⚡",
        "Chemie": "🧪",
        "Biologie": "🌿",
        "Geschichte": "🏛️",
        "Geographie": "🌐",
        "Wirtschaft und Beruf (WiB)": "💼",
        "BwR / Wirtschaft & Recht": "📊",
        "Wirtschaft & Recht": "⚖️",
        "Religion / Ethik": "🕊️",
        "Kunst": "🎨",
        "Musik": "🎵",
        "Kunst / Musik": "🎭",
        "Latein": "📜",
        "Französisch": "🥐"
    };

    subjectChipsContainer.innerHTML = availableSubjects.map(sub => {
        const isSelected = selectedSubjects.includes(sub);
        const activeClass = isSelected
            ? "bg-brand-600 text-white font-bold border-brand-600 shadow-sm ring-2 ring-brand-200"
            : "bg-white text-slate-700 font-semibold border-slate-200 hover:border-slate-300 hover:bg-slate-50";
        const checkIcon = isSelected ? '<i class="fa-solid fa-check ml-1.5 text-[10px]"></i>' : '';
        return `
            <button type="button" onclick="toggleSubjectChip('${sub}')" class="px-3 py-1.5 rounded-xl border text-xs transition-all flex items-center gap-1 select-none ${activeClass}">
                <span>${sub}</span>
                ${checkIcon}
            </button>
        `;
    }).join('');

    updateCrossCurricularBadge();
}

window.buildDynamicTopicsForSelectedSubjects = function(subjects) {
    if (!subjects || subjects.length === 0) {
        return [
            { name: "Textverständnis", count: 2 },
            { name: "Wortarten & Grammatik", count: 2 },
            { name: "Fremdwörter", count: 1 }
        ];
    }

    if (subjects.length === 1) {
        const sub = subjects[0];
        const preset = subjectPresets[sub] || [
            { name: "Textverständnis", count: 2 },
            { name: "Fachbegriffe & Anwendungsaufgabe", count: 2 },
            { name: "Vertiefungs- & Transferaufgabe", count: 1 }
        ];
        return JSON.parse(JSON.stringify(preset));
    }

    // 2 or more subjects selected:
    const sub1 = subjects[0];
    const sub2 = subjects[1];

    const preset1 = subjectPresets[sub1] || [
        { name: "Textverständnis", count: 2 },
        { name: "Schwerpunkt " + sub1, count: 2 }
    ];
    const preset2 = subjectPresets[sub2] || [
        { name: "Textverständnis", count: 2 },
        { name: "Schwerpunkt " + sub2, count: 2 }
    ];

    const topicSub1Obj = preset1.find(t => !t.name.toLowerCase().includes("textverständnis")) || preset1[1] || { name: sub1 + "-Schwerpunkt" };
    const topicSub2Obj = preset2.find(t => !t.name.toLowerCase().includes("textverständnis")) || preset2[1] || { name: sub2 + "-Schwerpunkt" };

    return [
        { name: "Textverständnis", count: 2 },
        { name: topicSub1Obj.name, count: 2 },
        { name: topicSub2Obj.name, count: 1 }
    ];
};

window.toggleSubjectChip = function(subjectName) {
    if (selectedSubjects.includes(subjectName)) {
        if (selectedSubjects.length > 1) {
            selectedSubjects = selectedSubjects.filter(s => s !== subjectName);
        }
    } else {
        selectedSubjects.push(subjectName);
    }
    renderSubjectChips();
    dynamicTopics = buildDynamicTopicsForSelectedSubjects(selectedSubjects);
    renderDynamicTopicRows();
};

window.handleSchoolTypeChange = function() {
    renderSubjectChips();
    dynamicTopics = buildDynamicTopicsForSelectedSubjects(selectedSubjects);
    renderDynamicTopicRows();
    const headerSchoolName = document.getElementById('header-school-name');
    if (headerSchoolName && inputSchoolType) {
        headerSchoolName.textContent = 'Testschullizenz Amperschule Olching (' + inputSchoolType.value + ')';
    }
};

function updateCrossCurricularBadge() {
    if (!crossCurricularBadge) return;
    if (selectedSubjects.length > 1) {
        crossCurricularBadge.classList.remove('hidden');
        if (crossCurricularText) {
            crossCurricularText.textContent = `Die Fächer "${selectedSubjects.join(' & ')}" werden didaktisch miteinander kombiniert (z. B. Leseverstehen + Rechenschritte).`;
        }
    } else {
        crossCurricularBadge.classList.add('hidden');
    }
}

// Initial chip render
renderSubjectChips();

// Settings Modal Handlers
window.syncTaskCountFromDropdown = function() {
    const select = document.getElementById('select-task-count');
    const hiddenInput = document.getElementById('input-task-count');
    if (select && hiddenInput) {
        hiddenInput.value = select.value;
    }
};

window.appendFocusTopic = function(topicName) {
    const focusInput = document.getElementById('input-focus-topic');
    if (focusInput) {
        const currentVal = focusInput.value.trim();
        if (!currentVal) {
            focusInput.value = topicName;
        } else if (!currentVal.includes(topicName)) {
            focusInput.value = currentVal + ', ' + topicName;
        }
    }
};

window.openSettingsModal = function() {
    const modal = document.getElementById('settings-modal');
    if (modal) modal.classList.remove('hidden');
};

window.closeSettingsModal = function() {
    const modal = document.getElementById('settings-modal');
    if (modal) modal.classList.add('hidden');
    if (inputApiKey && inputApiKey.value) {
        localStorage.setItem('gemini_api_key', inputApiKey.value.trim());
    }
    if (inputPromoCode && inputPromoCode.value) {
        localStorage.setItem('promo_code', inputPromoCode.value.trim());
    }
};

window.openDSGVOModal = function() {
    const modal = document.getElementById('dsgvo-modal');
    if (modal) modal.classList.remove('hidden');
};

window.closeDSGVOModal = function() {
    const modal = document.getElementById('dsgvo-modal');
    if (modal) modal.classList.add('hidden');
};

// Didaktische Schwerpunkte Builder State & Handlers (Default 5 Tasks, Max 20)
let dynamicTopics = [
    { name: "Textverständnis", count: 2 },
    { name: "Wortarten & Grammatik", count: 2 },
    { name: "Fremdwörter", count: 1 }
];

const subjectPresets = {
    "Deutsch": [
        { name: "Textverständnis", count: 2 },
        { name: "Wortarten & Grammatik", count: 2 },
        { name: "Fremdwörter", count: 1 }
    ],
    "Mathematik": [
        { name: "Textverständnis (Sachaufgaben)", count: 2 },
        { name: "Bruchrechnen & Anteile", count: 2 },
        { name: "Geometrie & Umfang", count: 1 }
    ],
    "Englisch": [
        { name: "Textverständnis (Reading)", count: 2 },
        { name: "Vocabulary & Phrases", count: 2 },
        { name: "Grammar & Tenses", count: 1 }
    ],
    "Natur und Technik (NT)": [
        { name: "Textverständnis (Sachtext)", count: 2 },
        { name: "Fachbegriffe Biologie/Physik", count: 2 },
        { name: "Diagramm auswerten", count: 1 }
    ],
    "Geschichte / Politik / Geographie (GPG)": [
        { name: "Textverständnis (Quellentext)", count: 2 },
        { name: "Kartenarbeit & Standort", count: 2 },
        { name: "Historische Fachbegriffe", count: 1 }
    ],
    "Wirtschaft und Beruf (WiB)": [
        { name: "Textverständnis (Fallbeispiel)", count: 2 },
        { name: "Haushaltsplanung & Budget", count: 2 },
        { name: "Wirtschaftliche Fachbegriffe", count: 1 }
    ],
    "Religion / Ethik": [
        { name: "Textverständnis (Ethische Frage)", count: 2 },
        { name: "Begriffsbedeutung & Werte", count: 2 },
        { name: "Eigene Stellungnahme", count: 1 }
    ],
    "Kunst / Musik": [
        { name: "Textverständnis (Werkbeschreibung)", count: 2 },
        { name: "Fachbegriffe & Notenlehre", count: 2 },
        { name: "Bildanalyse & Gestaltung", count: 1 }
    ],
    "Heimat- und Sachunterricht (HSU)": [
        { name: "Textverständnis (Sachtext)", count: 2 },
        { name: "Versuch & Beobachtung", count: 2 },
        { name: "Grundwissen & Fachbegriffe", count: 1 }
    ],
    "Physik": [
        { name: "Textverständnis (Sachtext)", count: 2 },
        { name: "Formeln & Berechnungen", count: 2 },
        { name: "Versuchsaufbau & Erklärung", count: 1 }
    ],
    "Chemie": [
        { name: "Textverständnis (Sachtext)", count: 2 },
        { name: "Reaktionsgleichung & Symbole", count: 2 },
        { name: "Versuchsauswertung", count: 1 }
    ],
    "Biologie": [
        { name: "Textverständnis (Sachtext)", count: 2 },
        { name: "Fachbegriffe & Vorgänge", count: 2 },
        { name: "Diagramm & Schema auswerten", count: 1 }
    ],
    "Geschichte": [
        { name: "Textverständnis (Quellentext)", count: 2 },
        { name: "Historische Einordnung", count: 2 },
        { name: "Urteilsbildung", count: 1 }
    ],
    "Geographie": [
        { name: "Textverständnis (Sachtext)", count: 2 },
        { name: "Kartenanalyse & Standort", count: 2 },
        { name: "Fachbegriffe & Diagramme", count: 1 }
    ],
    "BwR / Wirtschaft & Recht": [
        { name: "Textverständnis (Sachverhalt)", count: 2 },
        { name: "Buchungssätze & Rechnungslegung", count: 2 },
        { name: "Rechtliche Fallanalyse", count: 1 }
    ],
    "Wirtschaft & Recht": [
        { name: "Textverständnis (Gesetzestext)", count: 2 },
        { name: "Ökonomische Zusammenhänge", count: 2 },
        { name: "Fallanalyse & Urteilsbildung", count: 1 }
    ],
    "Französisch": [
        { name: "Textverständnis (Compréhension)", count: 2 },
        { name: "Vocabulaire & Expressions", count: 2 },
        { name: "Grammaire & Conjugaison", count: 1 }
    ],
    "Latein": [
        { name: "Textverständnis (Übersetzung)", count: 2 },
        { name: "Wortschatz & Formenlehre", count: 2 },
        { name: "Realien & Kultur", count: 1 }
    ],
    "Kunst": [
        { name: "Textverständnis (Werkbeschreibung)", count: 2 },
        { name: "Bildanalyse & Gestalten", count: 2 },
        { name: "Künstlerische Praxis", count: 1 }
    ],
    "Musik": [
        { name: "Textverständnis (Liedtext)", count: 2 },
        { name: "Notenlehre & Rhythmik", count: 2 },
        { name: "Höranalyse & Instrumente", count: 1 }
    ]
};

window.adjustTotalTasks = function(delta) {
    let currentTotal = dynamicTopics.reduce((sum, t) => sum + (t.count || 0), 0);
    if (currentTotal === 0) currentTotal = 5;
    
    let newTotal = Math.min(20, Math.max(1, currentTotal + delta));
    
    if (dynamicTopics.length > 0) {
        const diff = newTotal - currentTotal;
        dynamicTopics[0].count = Math.min(20, Math.max(0, dynamicTopics[0].count + diff));
    }
    renderDynamicTopicRows();
};

window.renderDynamicTopicRows = function() {
    const container = document.getElementById('topic-rows-list');
    if (!container) return;
    
    container.innerHTML = '';
    dynamicTopics.forEach((topic, idx) => {
        const row = document.createElement('div');
        row.className = 'flex items-center gap-2 bg-white p-2 rounded-xl border border-slate-200 shadow-sm';
        row.innerHTML = `
            <input type="text" value="${topic.name}" oninput="updateTopicName(${idx}, this.value)" placeholder="z. B. Wortarten, Grammatik" class="flex-1 px-2.5 py-1.5 text-xs font-bold text-slate-800 bg-transparent focus:outline-none focus:bg-slate-50 rounded-lg border border-transparent focus:border-slate-200">
            <div class="flex items-center gap-1.5 shrink-0">
                <button type="button" onclick="adjustDynamicTopicCount(${idx}, -1)" class="w-9 h-9 sm:w-8 sm:h-8 rounded-lg bg-slate-100 hover:bg-slate-200 active:scale-95 text-slate-800 font-extrabold text-sm flex items-center justify-center transition-all">-</button>
                <span class="w-6 text-center font-black text-xs text-brand-700">${topic.count}</span>
                <button type="button" onclick="adjustDynamicTopicCount(${idx}, 1)" class="w-9 h-9 sm:w-8 sm:h-8 rounded-lg bg-slate-100 hover:bg-slate-200 active:scale-95 text-slate-800 font-extrabold text-sm flex items-center justify-center transition-all">+</button>
            </div>
            ${dynamicTopics.length > 1 ? `
                <button type="button" onclick="removeDynamicTopicRow(${idx})" title="Schwerpunkt entfernen" class="w-9 h-9 sm:w-8 sm:h-8 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 flex items-center justify-center transition-all shrink-0">
                    <i class="fa-solid fa-trash-can text-xs"></i>
                </button>
            ` : ''}
        `;
        container.appendChild(row);
    });
    
    updateTopicSummary();
};

window.adjustDynamicTopicCount = function(idx, delta) {
    if (!dynamicTopics[idx]) return;
    dynamicTopics[idx].count = Math.min(20, Math.max(0, dynamicTopics[idx].count + delta));
    renderDynamicTopicRows();
};

window.updateTopicName = function(idx, val) {
    if (!dynamicTopics[idx]) return;
    dynamicTopics[idx].name = val;
    updateTopicSummary();
};

window.addCustomTopicRow = function() {
    dynamicTopics.push({ name: "", count: 1 });
    renderDynamicTopicRows();
    setTimeout(() => {
        const inputs = document.querySelectorAll('#topic-rows-list input[type="text"]');
        if (inputs.length > 0) {
            const lastInput = inputs[inputs.length - 1];
            lastInput.placeholder = "Eigenen Schwerpunkt eingeben...";
            lastInput.focus();
        }
    }, 50);
};

window.setAiAutoTopics = function() {
    dynamicTopics = [
        { name: "KI wählt Schwerpunkte automatisch aus dem Text", count: 5 }
    ];
    renderDynamicTopicRows();
};

window.removeDynamicTopicRow = function(idx) {
    if (dynamicTopics.length <= 1) return;
    dynamicTopics.splice(idx, 1);
    renderDynamicTopicRows();
};

window.resetDefaultTopics = function() {
    dynamicTopics = [
        { name: "Textverständnis", count: 2 },
        { name: "Wortarten & Grammatik", count: 2 },
        { name: "Fremdwörter", count: 1 }
    ];
    renderDynamicTopicRows();
};

window.updateTopicSummary = function() {
    const totalDisplay = document.getElementById('display-total-tasks');
    const hiddenTopicInput = document.getElementById('input-focus-topic');
    const hiddenTaskCountInput = document.getElementById('input-task-count');
    
    const totalTasks = dynamicTopics.reduce((sum, t) => sum + (t.count || 0), 0);
    if (totalDisplay) totalDisplay.textContent = totalTasks;
    if (hiddenTaskCountInput) hiddenTaskCountInput.value = totalTasks;
    
    const summaryParts = dynamicTopics
        .filter(t => t.count > 0 && t.name.trim())
        .map(t => `${t.count} ${t.name.trim()}`);
    
    if (hiddenTopicInput) {
        hiddenTopicInput.value = summaryParts.join(', ') || '5 Aufgaben';
    }
};

// Task Count Segment Selector
window.setTaskCount = function(count) {
    if (inputTaskCount) inputTaskCount.value = count;
    [1, 2, 3, 4, 5, 6, 8, 10].forEach(c => {
        const btn = document.getElementById(`btn-task-count-${c}`);
        if (btn) {
            if (c === count) {
                btn.className = "flex-1 py-1.5 rounded-lg text-xs font-bold transition-all bg-white text-brand-700 shadow-sm";
            } else {
                btn.className = "flex-1 py-1.5 rounded-lg text-xs font-bold transition-all text-slate-600 hover:text-slate-900";
            }
        }
    });
};

window.addTask = function(prefix) {
    if (!appState.generatedData) return;
    const targetKey = (prefix === 'C') ? 'level_c' : ((prefix === 'A') ? 'level_a' : 'level_b');
    if (!appState.generatedData[targetKey]) {
        appState.generatedData[targetKey] = { title: `Level ${prefix}`, tasks: [] };
    }
    const tasks = appState.generatedData[targetKey].tasks;
    const taskNum = tasks.length + 1;
    
    tasks.push({
        title: `Aufgabe ${taskNum} (${prefix === 'C' ? 'Inklusion' : (prefix === 'A' ? 'Fördern' : 'Fordern')})`,
        text: "Hier den Aufgabentext eingeben. *Lücke* mit Sternchen markieren.",
        format: inputFormat?.value || "Lückentext",
        hint: prefix === 'B' ? "" : "💡 Tipp: Hier Hinweis eingeben",
        explanation: "Erklärung der richtigen Lösung..."
    });
    
    populateEditor(appState.generatedData);
};

// Demo Presets (1-Click Instant Tryout)
window.loadDemoPreset = function(presetKey) {
    if (presetKey === 'deutsch') {
        selectedSubjects = ["Deutsch"];
        if (inputFocusTopic) inputFocusTopic.value = "Leseverständnis & Fabeln";
        if (inputHefteintragTopic) inputHefteintragTopic.value = "Moral & Kernbotschaft von Fabeln";
    } else if (presetKey === 'mathe') {
        selectedSubjects = ["Mathematik"];
        if (inputFocusTopic) inputFocusTopic.value = "Bruchrechnen & Anteile";
        if (inputHefteintragTopic) inputHefteintragTopic.value = "Brüche gleichnamig machen & kürzen";
    } else if (presetKey === 'englisch') {
        selectedSubjects = ["Englisch"];
        if (inputFocusTopic) inputFocusTopic.value = "Simple Past vs. Past Progressive";
        if (inputHefteintragTopic) inputHefteintragTopic.value = "Grammar Rule: Irregular Verbs";
    }
    renderSubjectChips();

    // Create a synthetic sample demo image file for instant processing!
    const canvas = document.createElement('canvas');
    canvas.width = 800;
    canvas.height = 1000;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, 800, 1000);
    
    ctx.fillStyle = '#1e293b';
    ctx.font = 'bold 28px sans-serif';
    ctx.fillText(`Adaptify Demo-Buchseite: ${presetKey.toUpperCase()}`, 50, 80);
    
    ctx.fillStyle = '#475569';
    ctx.font = '18px sans-serif';
    ctx.fillText(`Beispiel-Lehrbuchseite für ${selectedSubjects.join(', ')}`, 50, 120);
    
    ctx.fillStyle = '#334155';
    ctx.font = '16px serif';
    const lines = presetKey === 'deutsch' ? [
        "Der Fuchs und der Rabe (Fabel)",
        "Ein Rabe hatte einen Brocken Käse gestohlen und sich auf einen Baum gesetzt.",
        "Da kam ein schlauer Fuchs vorbei und wollte den Käse unbedingt haben.",
        "Er sprach: 'Oh schöner Rabe, wie wunderbar glänzt dein Gefieder!",
        "Wenn deine Stimme genauso schön ist, bist du der König aller Vögel.'",
        "Der stolze Rabe schmeichelte sich, öffnete den Schnabel und begann zu singen.",
        "Der Käse fiel herunter, und der Fuchs schnappte ihn sich lachend."
    ] : (presetKey === 'mathe' ? [
        "Bruchrechnen im Alltag",
        "Ein Kuchen wird in 8 gleich große Stücke geschnitten.",
        "Anna isst 2 von 8 Stücken. Das ist der Bruch 2/8 (zwei Achtel).",
        "Ben isst 3 von 8 Stücken (drei Achtel).",
        "1. Welcher Anteil des Kuchens wurde insgesamt gegessen?",
        "2. Welcher Anteil bleibt für den nächsten Tag übrig?",
        "3. Kürze den Bruch 2/8 auf seinen kleinsten Nenner."
    ] : [
        "Grammar Exercise: Simple Past vs. Past Progressive",
        "Yesterday, Sarah and Tom went to the local park after school.",
        "While Sarah was playing basketball, Tom found a golden key.",
        "Complete the sentences:",
        "1. They (leave) _____ the park at 5 o'clock.",
        "2. What (do) _____ Tom when Sarah called him?"
    ]);
    
    let y = 180;
    lines.forEach(l => {
        ctx.fillText(l, 50, y);
        y += 35;
    });

    canvas.toBlob(blob => {
        const file = new File([blob], `demo_${presetKey}.jpg`, { type: 'image/jpeg' });
        handleFile(file);
    }, 'image/jpeg');
};

// Load API Key & Promo Code from localStorage if exists, with default fallback
inputApiKey.value = localStorage.getItem('gemini_api_key') || '';
if (localStorage.getItem('promo_code')) {
    inputPromoCode.value = localStorage.getItem('promo_code');
}

// Initial render of Didaktische Schwerpunkte Builder
renderDynamicTopicRows();

inputApiKey.addEventListener('input', () => {
    localStorage.setItem('gemini_api_key', inputApiKey.value.trim ? inputApiKey.value.trim() : inputApiKey.value);
});
inputPromoCode.addEventListener('input', () => {
    localStorage.setItem('promo_code', inputPromoCode.value);
});

// Editor Inputs
const editorSourceText = document.getElementById('editor-source-text');
const editorTitle = document.getElementById('editor-title');
const editorHefteintragTitle = document.getElementById('editor-hefteintrag-title');
const editorHefteintragSummary = document.getElementById('editor-hefteintrag-summary');
const editorThreshold = document.getElementById('editor-threshold');
const editorQuestions = document.getElementById('editor-questions');
const editorLevelATasks = document.getElementById('editor-level-a-tasks');
const editorLevelBTasks = document.getElementById('editor-level-b-tasks');
const editorZusatzaufgaben = document.getElementById('editor-zusatzaufgaben');

// Buttons
const btnBackToUpload = document.getElementById('btn-back-to-upload');
const btnPackH5P = document.getElementById('btn-pack-h5p');
const btnDownloadH5P = document.getElementById('btn-download-h5p');
const btnDownloadPDF = document.getElementById('btn-download-pdf');
const btnRestart = document.getElementById('btn-restart');

// API Base URL
const API_BASE = '';

// Navigation Helpers
function showScreen(screen) {
    screenUpload.classList.add('hidden');
    screenEditor.classList.add('hidden');
    screenExport.classList.add('hidden');
    if (screenAnalytics) screenAnalytics.classList.add('hidden');
    screen.classList.remove('hidden');
    updateNavigationState();
}

window.navigateToScreen = function(screenName) {
    if (screenName === 'upload') {
        showScreen(screenUpload);
    } else if (screenName === 'editor') {
        if (appState.generatedData) {
            showScreen(screenEditor);
        }
    } else if (screenName === 'export') {
        if (appState.generatedData) {
            showScreen(screenExport);
        }
    } else if (screenName === 'analytics') {
        showScreen(screenAnalytics);
        loadAnalyticsData(); // Fetch statistics from server
    }
};

function updateNavigationState() {
    const btnEditor = document.getElementById('nav-btn-editor');
    const btnExport = document.getElementById('nav-btn-export');
    const btnAnalytics = document.getElementById('nav-btn-analytics');
    const liveIndicator = document.getElementById('nav-live-session-indicator');
    const livePinSpan = document.getElementById('nav-live-session-pin');
    
    if (!btnEditor || !btnExport) return;
    
    // Enable/disable navigation buttons based on whether generated data is present
    if (appState.generatedData) {
        btnEditor.disabled = false;
        btnEditor.classList.remove('text-slate-400', 'cursor-not-allowed');
        btnEditor.classList.add('text-slate-600', 'hover:text-slate-900');
        
        btnExport.disabled = false;
        btnExport.classList.remove('text-slate-400', 'cursor-not-allowed');
        btnExport.classList.add('text-slate-600', 'hover:text-slate-900');
    } else {
        btnEditor.disabled = true;
        btnEditor.classList.add('text-slate-400', 'cursor-not-allowed');
        btnEditor.classList.remove('text-slate-600', 'hover:text-slate-900');
        
        btnExport.disabled = true;
        btnExport.classList.add('text-slate-400', 'cursor-not-allowed');
        btnExport.classList.remove('text-slate-600', 'hover:text-slate-900');
    }
    
    // Show/hide live session indicator
    if (liveSessionInterval && liveSessionPin) {
        if (liveIndicator) {
            liveIndicator.classList.remove('hidden');
            liveIndicator.classList.add('flex');
        }
        if (livePinSpan) livePinSpan.textContent = liveSessionPin;
    } else {
        if (liveIndicator) {
            liveIndicator.classList.remove('flex');
            liveIndicator.classList.add('hidden');
        }
    }
    
    // Highlight active screen link
    const screens = [
        { el: screenUpload, btnId: 'nav-btn-upload' },
        { el: screenEditor, btnId: 'nav-btn-editor' },
        { el: screenExport, btnId: 'nav-btn-export' },
        { el: screenAnalytics, btnId: 'nav-btn-analytics' }
    ];
    
    screens.forEach(s => {
        if (!s.el) return;
        const btn = document.getElementById(s.btnId);
        if (!btn) return;
        const isCurrent = !s.el.classList.contains('hidden');
        if (isCurrent) {
            btn.classList.add('bg-brand-50', 'text-brand-700');
            btn.classList.remove('text-slate-600');
        } else {
            btn.classList.remove('bg-brand-50', 'text-brand-700');
            if (!btn.disabled) {
                btn.classList.add('text-slate-600');
            }
        }
    });
}

// ----------------------------------------------------
// FILE UPLOAD EVENT LISTENERS
// ----------------------------------------------------
dropZone.addEventListener('click', (e) => {
    if (e.target !== fileInput && e.target !== btnRemoveFile && e.target !== btnSubmit && !btnSubmit.contains(e.target) && !btnRemoveFile.contains(e.target)) {
        fileInput.click();
    }
});

fileInput.addEventListener('click', (e) => {
    e.stopPropagation();
});

dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('border-brand-500', 'bg-brand-50/20');
});

dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('border-brand-500', 'bg-brand-50/20');
});

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('border-brand-500', 'bg-brand-50/20');
    if (e.dataTransfer.files.length > 0) {
        handleFile(e.dataTransfer.files[0]);
    }
});

fileInput.addEventListener('change', () => {
    if (fileInput.files.length > 0) {
        handleFile(fileInput.files[0]);
    }
});

btnRemoveFile.addEventListener('click', (e) => {
    e.stopPropagation();
    resetFileSelection();
});

const imageEditorModal = document.getElementById('image-editor-modal');
const btnCloseImageEditor = document.getElementById('btn-close-image-editor');
const btnSkipImageEdit = document.getElementById('btn-skip-image-edit');
const btnSaveImageEdit = document.getElementById('btn-save-image-edit');
const btnEditCurrentImage = document.getElementById('btn-edit-current-image');
const filePreviewThumb = document.getElementById('file-preview-thumb');
const fileIconPlaceholder = document.getElementById('file-icon-placeholder');

let currentEditImage = null;
let currentRotation = 0;
let currentFilter = 'none'; // 'none' | 'contrast' | 'grayscale'
let activeDragMode = null; // null | 'move' | 'nw' | 'ne' | 'sw' | 'se'
let dragStartX, dragStartY, dragStartLeft, dragStartTop, dragStartWidth, dragStartHeight;

function compressImageFile(file, maxDimension = 1600, quality = 0.85) {
    return new Promise((resolve) => {
        if (!file) return resolve(file);
        const isImage = (file.type && file.type.startsWith('image/')) || 
                        /\.(jpg|jpeg|png|heic|heif|webp)$/i.test(file.name || '');
        if (!isImage) return resolve(file);
        const reader = new FileReader();
        reader.onload = (e) => {
            const img = new Image();
            img.onload = () => {
                let w = img.width;
                let h = img.height;
                if (w <= maxDimension && h <= maxDimension && file.size < 800 * 1024) {
                    return resolve(file);
                }
                if (w > maxDimension || h > maxDimension) {
                    if (w > h) {
                        h = Math.round((h * maxDimension) / w);
                        w = maxDimension;
                    } else {
                        w = Math.round((w * maxDimension) / h);
                        h = maxDimension;
                    }
                }
                const canvas = document.createElement('canvas');
                canvas.width = w;
                canvas.height = h;
                const ctx = canvas.getContext('2d');
                ctx.fillStyle = '#ffffff';
                ctx.fillRect(0, 0, w, h);
                ctx.drawImage(img, 0, 0, w, h);
                canvas.toBlob((blob) => {
                    if (!blob) return resolve(file);
                    const compressedFile = new File([blob], file.name.replace(/\.[^/.]+$/, "") + ".jpg", {
                        type: 'image/jpeg',
                        lastModified: Date.now()
                    });
                    console.log(`Compressed photo from ${(file.size / 1024 / 1024).toFixed(2)}MB to ${(compressedFile.size / 1024).toFixed(1)}KB`);
                    resolve(compressedFile);
                }, 'image/jpeg', quality);
            };
            img.onerror = () => resolve(file);
            img.src = e.target.result;
        };
        reader.onerror = () => resolve(file);
        reader.readAsDataURL(file);
    });
}

async function handleFile(file) {
    let processedFile = file;
    if (file && file.type.startsWith('image/')) {
        processedFile = await compressImageFile(file);
    }
    appState.selectedFile = processedFile;
    fileName.textContent = processedFile.name;
    
    // Format file size
    fileSize.textContent = processedFile.size > 1024 * 1024 ? `${(processedFile.size / (1024 * 1024)).toFixed(2)} MB` : `${(processedFile.size / 1024).toFixed(0)} KB`;
    
    fileInfo.classList.remove('hidden');

    // Read image preview if file is an image
    if (file.type.startsWith('image/')) {
        const reader = new FileReader();
        reader.onload = (e) => {
            appState.originalDataUrl = e.target.result;
            appState.previewDataUrl = e.target.result;
            
            // Show thumbnail preview
            if (filePreviewThumb) {
                filePreviewThumb.src = e.target.result;
                filePreviewThumb.classList.remove('hidden');
            }
            if (fileIconPlaceholder) fileIconPlaceholder.classList.add('hidden');
            if (btnEditCurrentImage) btnEditCurrentImage.classList.remove('hidden');
            
            openImageEditor(e.target.result);
        };
        reader.readAsDataURL(file);
    } else {
        appState.originalDataUrl = null;
        appState.previewDataUrl = null;
        if (filePreviewThumb) filePreviewThumb.classList.add('hidden');
        if (fileIconPlaceholder) fileIconPlaceholder.classList.remove('hidden');
        if (btnEditCurrentImage) btnEditCurrentImage.classList.add('hidden');
    }
}

window.reopenImageEditor = function() {
    const src = appState.originalDataUrl || appState.previewDataUrl;
    if (src) {
        openImageEditor(src);
    }
};

function resetFileSelection() {
    appState.selectedFile = null;
    appState.originalDataUrl = null;
    appState.previewDataUrl = null;
    fileInput.value = '';
    fileInfo.classList.add('hidden');
    if (filePreviewThumb) filePreviewThumb.classList.add('hidden');
    if (fileIconPlaceholder) fileIconPlaceholder.classList.remove('hidden');
    if (btnEditCurrentImage) btnEditCurrentImage.classList.add('hidden');
}

function openImageEditor(dataUrl) {
    if (!imageEditorModal) return;
    currentRotation = 0;
    currentFilter = 'none';
    updateFilterButtonUI();
    
    currentEditImage = new Image();
    currentEditImage.onload = () => {
        drawCanvasImage();
        setCropPreset('full');
        imageEditorModal.classList.remove('hidden');
    };
    currentEditImage.src = dataUrl;
}

function drawCanvasImage() {
    const canvas = document.getElementById('img-edit-canvas');
    if (!canvas || !currentEditImage) return;
    
    const ctx = canvas.getContext('2d');
    const angle = (currentRotation * Math.PI) / 180;
    const isHorizontal = Math.abs(currentRotation % 180) === 90;
    
    canvas.width = isHorizontal ? currentEditImage.height : currentEditImage.width;
    canvas.height = isHorizontal ? currentEditImage.width : currentEditImage.height;
    
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Apply visual OCR enhancement filters
    if (currentFilter === 'contrast') {
        ctx.filter = 'contrast(160%) brightness(105%)';
    } else if (currentFilter === 'grayscale') {
        ctx.filter = 'grayscale(100%) contrast(180%) brightness(110%)';
    } else {
        ctx.filter = 'none';
    }
    
    ctx.save();
    ctx.translate(canvas.width / 2, canvas.height / 2);
    ctx.rotate(angle);
    ctx.drawImage(currentEditImage, -currentEditImage.width / 2, -currentEditImage.height / 2);
    ctx.restore();
}

window.rotateImage = function(degrees) {
    currentRotation = (currentRotation + degrees + 360) % 360;
    drawCanvasImage();
};

window.toggleImageFilter = function(filterType) {
    if (currentFilter === filterType) {
        currentFilter = 'none';
    } else {
        currentFilter = filterType;
    }
    updateFilterButtonUI();
    drawCanvasImage();
};

function updateFilterButtonUI() {
    const btnContrast = document.getElementById('btn-filter-contrast');
    const btnBW = document.getElementById('btn-filter-bw');
    if (btnContrast) {
        if (currentFilter === 'contrast') {
            btnContrast.classList.add('bg-amber-100', 'border-amber-300', 'text-amber-800');
        } else {
            btnContrast.classList.remove('bg-amber-100', 'border-amber-300', 'text-amber-800');
        }
    }
    if (btnBW) {
        if (currentFilter === 'grayscale') {
            btnBW.classList.add('bg-slate-200', 'border-slate-400', 'text-slate-900');
        } else {
            btnBW.classList.remove('bg-slate-200', 'border-slate-400', 'text-slate-900');
        }
    }
}

window.setCropPreset = function(preset) {
    const cropBox = document.getElementById('crop-box');
    if (!cropBox) return;
    if (preset === 'full') {
        cropBox.style.width = '90%';
        cropBox.style.height = '90%';
        cropBox.style.left = '5%';
        cropBox.style.top = '5%';
    } else if (preset === 'top') {
        cropBox.style.width = '90%';
        cropBox.style.height = '45%';
        cropBox.style.left = '5%';
        cropBox.style.top = '5%';
    } else if (preset === 'bottom') {
        cropBox.style.width = '90%';
        cropBox.style.height = '45%';
        cropBox.style.left = '5%';
        cropBox.style.top = '50%';
    }
};

// ----------------------------------------------------
// TOUCH & MOUSE POINTER HANDLERS FOR CROP BOX
// ----------------------------------------------------
const cropBox = document.getElementById('crop-box');
const imgWorkspace = document.getElementById('img-edit-workspace');

function getPointerPos(e) {
    if (e.touches && e.touches.length > 0) {
        return { x: e.touches[0].clientX, y: e.touches[0].clientY };
    }
    return { x: e.clientX, y: e.clientY };
}

function startCropDrag(mode, e) {
    if (e.cancelable) e.preventDefault();
    e.stopPropagation();
    
    activeDragMode = mode;
    const pos = getPointerPos(e);
    dragStartX = pos.x;
    dragStartY = pos.y;
    
    if (cropBox && imgWorkspace) {
        const rect = cropBox.getBoundingClientRect();
        const wsRect = imgWorkspace.getBoundingClientRect();
        dragStartLeft = rect.left - wsRect.left;
        dragStartTop = rect.top - wsRect.top;
        dragStartWidth = rect.width;
        dragStartHeight = rect.height;
    }
}

if (cropBox && imgWorkspace) {
    // Box Move (Touch & Mouse)
    cropBox.addEventListener('pointerdown', (e) => {
        if (e.target.id && e.target.id.startsWith('crop-handle')) return;
        startCropDrag('move', e);
    });
    cropBox.addEventListener('touchstart', (e) => {
        if (e.target.id && e.target.id.startsWith('crop-handle')) return;
        startCropDrag('move', e);
    }, { passive: false });

    // Corner Handles
    ['nw', 'ne', 'sw', 'se'].forEach(dir => {
        const handle = document.getElementById(`crop-handle-${dir}`);
        if (handle) {
            handle.addEventListener('pointerdown', (e) => startCropDrag(dir, e));
            handle.addEventListener('touchstart', (e) => startCropDrag(dir, e), { passive: false });
        }
    });

    // Global Move Handler (Pointer & Touch)
    function onPointerMove(e) {
        if (!activeDragMode || !cropBox || !imgWorkspace) return;
        if (e.cancelable) e.preventDefault();
        
        const pos = getPointerPos(e);
        const dx = pos.x - dragStartX;
        const dy = pos.y - dragStartY;
        const wsRect = imgWorkspace.getBoundingClientRect();
        
        if (activeDragMode === 'move') {
            let newLeft = dragStartLeft + dx;
            let newTop = dragStartTop + dy;
            newLeft = Math.max(0, Math.min(newLeft, wsRect.width - dragStartWidth));
            newTop = Math.max(0, Math.min(newTop, wsRect.height - dragStartHeight));
            cropBox.style.left = `${(newLeft / wsRect.width) * 100}%`;
            cropBox.style.top = `${(newTop / wsRect.height) * 100}%`;
            cropBox.style.width = `${(dragStartWidth / wsRect.width) * 100}%`;
            cropBox.style.height = `${(dragStartHeight / wsRect.height) * 100}%`;
        } else if (activeDragMode === 'se') {
            let newW = Math.max(40, Math.min(dragStartWidth + dx, wsRect.width - dragStartLeft));
            let newH = Math.max(40, Math.min(dragStartHeight + dy, wsRect.height - dragStartTop));
            cropBox.style.width = `${(newW / wsRect.width) * 100}%`;
            cropBox.style.height = `${(newH / wsRect.height) * 100}%`;
        } else if (activeDragMode === 'sw') {
            let newLeft = Math.max(0, Math.min(dragStartLeft + dx, dragStartLeft + dragStartWidth - 40));
            let newW = dragStartWidth - (newLeft - dragStartLeft);
            let newH = Math.max(40, Math.min(dragStartHeight + dy, wsRect.height - dragStartTop));
            cropBox.style.left = `${(newLeft / wsRect.width) * 100}%`;
            cropBox.style.width = `${(newW / wsRect.width) * 100}%`;
            cropBox.style.height = `${(newH / wsRect.height) * 100}%`;
        } else if (activeDragMode === 'ne') {
            let newTop = Math.max(0, Math.min(dragStartTop + dy, dragStartTop + dragStartHeight - 40));
            let newH = dragStartHeight - (newTop - dragStartTop);
            let newW = Math.max(40, Math.min(dragStartWidth + dx, wsRect.width - dragStartLeft));
            cropBox.style.top = `${(newTop / wsRect.height) * 100}%`;
            cropBox.style.height = `${(newH / wsRect.height) * 100}%`;
            cropBox.style.width = `${(newW / wsRect.width) * 100}%`;
        } else if (activeDragMode === 'nw') {
            let newLeft = Math.max(0, Math.min(dragStartLeft + dx, dragStartLeft + dragStartWidth - 40));
            let newTop = Math.max(0, Math.min(dragStartTop + dy, dragStartTop + dragStartHeight - 40));
            let newW = dragStartWidth - (newLeft - dragStartLeft);
            let newH = dragStartHeight - (newTop - dragStartTop);
            cropBox.style.left = `${(newLeft / wsRect.width) * 100}%`;
            cropBox.style.top = `${(newTop / wsRect.height) * 100}%`;
            cropBox.style.width = `${(newW / wsRect.width) * 100}%`;
            cropBox.style.height = `${(newH / wsRect.height) * 100}%`;
        }
    }

    function onPointerEnd() {
        activeDragMode = null;
    }

    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', onPointerEnd);
    window.addEventListener('touchmove', onPointerMove, { passive: false });
    window.addEventListener('touchend', onPointerEnd);
}

// Close and skip listeners
if (btnCloseImageEditor) {
    btnCloseImageEditor.addEventListener('click', () => {
        imageEditorModal.classList.add('hidden');
    });
}

if (btnSkipImageEdit) {
    btnSkipImageEdit.addEventListener('click', () => {
        imageEditorModal.classList.add('hidden');
    });
}

if (btnSaveImageEdit) {
    btnSaveImageEdit.addEventListener('click', () => {
        const canvas = document.getElementById('img-edit-canvas');
        const cropBox = document.getElementById('crop-box');
        if (!canvas || !cropBox) return;
        
        const canvasRect = canvas.getBoundingClientRect();
        const cropBoxRect = cropBox.getBoundingClientRect();
        
        // Intersect cropbox and canvas client rects
        const left = Math.max(canvasRect.left, cropBoxRect.left);
        const top = Math.max(canvasRect.top, cropBoxRect.top);
        const right = Math.min(canvasRect.right, cropBoxRect.right);
        const bottom = Math.min(canvasRect.bottom, cropBoxRect.bottom);
        
        if (right <= left || bottom <= top) {
            alert("Hinweis: Bitte ziehe den grünen Rahmen auf den gewünschten Bildbereich.");
            return;
        }
        
        const scaleX = canvas.width / canvasRect.width;
        const scaleY = canvas.height / canvasRect.height;
        
        const cropX = (left - canvasRect.left) * scaleX;
        const cropY = (top - canvasRect.top) * scaleY;
        const cropW = (right - left) * scaleX;
        const cropH = (bottom - top) * scaleY;
        
        // Create temp canvas to extract cropped image
        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = cropW;
        tempCanvas.height = cropH;
        const tempCtx = tempCanvas.getContext('2d');
        
        tempCtx.drawImage(canvas, cropX, cropY, cropW, cropH, 0, 0, cropW, cropH);
        
        // Get data URL
        const croppedDataUrl = tempCanvas.toDataURL('image/jpeg', 0.92);
        appState.previewDataUrl = croppedDataUrl;
        
        // Update thumbnail preview in upload screen
        if (filePreviewThumb) {
            filePreviewThumb.src = croppedDataUrl;
            filePreviewThumb.classList.remove('hidden');
        }
        
        // Convert base64 to File object to override appState.selectedFile
        function dataURLtoFile(dataurl, filename) {
            let arr = dataurl.split(','), mime = arr[0].match(/:(.*?);/)[1],
                bstr = atob(arr[1]), n = bstr.length, u8arr = new Uint8Array(n);
            while(n--){
                u8arr[n] = bstr.charCodeAt(n);
            }
            return new File([u8arr], filename, {type:mime});
        }
        
        const originalName = appState.selectedFile ? appState.selectedFile.name : "aufgabe.jpg";
        appState.selectedFile = dataURLtoFile(croppedDataUrl, originalName);
        
        // Update size indicator
        const sizeInMB = (appState.selectedFile.size / (1024 * 1024)).toFixed(2);
        fileSize.textContent = `${sizeInMB} MB`;
        
        imageEditorModal.classList.add('hidden');
    });
}

// ----------------------------------------------------
// GENERATION FLOW (SUBMIT)
// ----------------------------------------------------
btnSubmit.addEventListener('click', async (e) => {
    if (e) e.stopPropagation();
    
    if (!appState.selectedFile) {
        alert("Bitte wählen Sie zuerst eine Buchseite aus oder machen Sie ein Foto mit der Kamera.");
        if (dropZone) {
            dropZone.scrollIntoView({ behavior: 'smooth', block: 'center' });
            dropZone.classList.add('ring-4', 'ring-amber-400');
            setTimeout(() => dropZone.classList.remove('ring-4', 'ring-amber-400'), 2500);
        }
        return;
    }

    if (loader) loader.classList.remove('hidden');
    
    // Dynamic loader status indicator for long requests (e.g. Render cold start)
    const loaderTextEl = document.querySelector('#loader p') || document.querySelector('#loader span');
    if (loaderTextEl) loaderTextEl.textContent = "Analysiere Buchseite mit KI...";
    
    const slowTimer1 = setTimeout(() => {
        if (loaderTextEl) loaderTextEl.textContent = "Server wird aufgeweckt & KI verarbeitet Dokument...";
    }, 6000);
    const slowTimer2 = setTimeout(() => {
        if (loaderTextEl) loaderTextEl.textContent = "Erstelle differenzierte H5P- & PDF-Aufgaben...";
    }, 18000);
    
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 90000);

    // Compute focus topic from dynamicTopics or hidden input
    let focusTopicValue = "";
    if (typeof dynamicTopics !== 'undefined' && Array.isArray(dynamicTopics) && dynamicTopics.length > 0) {
        const parts = dynamicTopics
            .filter(t => t.name && t.name.trim() !== "")
            .map(t => (t.count && t.count > 1) ? `${t.count}x ${t.name.trim()}` : t.name.trim());
        focusTopicValue = parts.join(', ');
    }
    if (!focusTopicValue && typeof inputFocusTopic !== 'undefined' && inputFocusTopic) {
        focusTopicValue = inputFocusTopic.value || "";
    }
    if (!focusTopicValue) {
        const hiddenEl = document.getElementById('input-focus-topic');
        if (hiddenEl) focusTopicValue = hiddenEl.value || "";
    }

    const apiKeyVal = (typeof inputApiKey !== 'undefined' && inputApiKey) ? (inputApiKey.value || '').trim() : '';
    const promoCodeVal = (typeof inputPromoCode !== 'undefined' && inputPromoCode) ? (inputPromoCode.value || '').trim() : '';

    // Save API key & promo code to localStorage
    if (apiKeyVal) localStorage.setItem('gemini_api_key', apiKeyVal);
    if (promoCodeVal) localStorage.setItem('promo_code', promoCodeVal);

    const formData = new FormData();
    formData.append('file', appState.selectedFile);
    formData.append('school_type', (typeof inputSchoolType !== 'undefined' && inputSchoolType) ? inputSchoolType.value : 'Grundschule');
    formData.append('subject', (Array.isArray(selectedSubjects) && selectedSubjects.length > 0) ? selectedSubjects.join(', ') : 'Deutsch');
    formData.append('focus_topic', focusTopicValue);
    formData.append('hefteintrag_topic', (typeof inputHefteintragTopic !== 'undefined' && inputHefteintragTopic) ? inputHefteintragTopic.value : '');
    formData.append('context', (typeof inputContext !== 'undefined' && inputContext) ? inputContext.value : '');
    formData.append('target_format', (typeof inputFormat !== 'undefined' && inputFormat) ? inputFormat.value : 'Lückentext');
    formData.append('task_count', (typeof inputTaskCount !== 'undefined' && inputTaskCount) ? inputTaskCount.value : 1);
    formData.append('api_key', apiKeyVal);
    formData.append('promo_code', promoCodeVal);

    try {
        const response = await fetch(`${API_BASE}/api/generate`, {
            method: 'POST',
            body: formData,
            signal: controller.signal
        });
        
        clearTimeout(slowTimer1);
        clearTimeout(slowTimer2);
        clearTimeout(timeoutId);

        if (!response.ok) {
            let errMsg = `Server-Fehler (${response.status})`;
            try {
                const errData = await response.json();
                if (errData && errData.detail) {
                    errMsg = errData.detail;
                }
            } catch (e) {
                if (response.statusText) {
                    errMsg += `: ${response.statusText}`;
                }
            }
            throw new Error(errMsg);
        }

        const data = await response.json();
        appState.generatedData = data;
        
        // Save to IndexedDB history
        try {
            await saveExerciseToHistory(data);
            renderHistoryList();
        } catch (e) {
            console.error("Failed to save generated exercise to IndexedDB:", e);
        }
        
        // Populate Editor Screen
        populateEditor(data);
        showScreen(screenEditor);

    } catch (err) {
        console.error("Failed to generate task:", err);
        alert("Fehler bei der Generierung:\n\n" + err.message);
    } finally {
        if (loader) loader.classList.add('hidden');
    }
});

// ----------------------------------------------------
// EDITOR SCREEN POPULATION & RENDERING
// ----------------------------------------------------
window.openCameraCapture = function(event) {
    if (event) event.stopPropagation();
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    input.capture = 'environment';
    input.style.display = 'none';
    input.onchange = (e) => {
        const file = e.target.files && e.target.files[0];
        if (file) handleFile(file);
    };
    document.body.appendChild(input);
    input.click();
    setTimeout(() => {
        if (input && input.parentNode) input.parentNode.removeChild(input);
    }, 1000);
};

window.moveTask = function(prefix, index, direction) {
    if (!appState.generatedData) return;
    const targetKey = (prefix === 'C') ? 'level_c' : ((prefix === 'A') ? 'level_a' : 'level_b');
    const tasks = appState.generatedData[targetKey]?.tasks;
    if (!tasks) return;
    
    const newIndex = index + direction;
    if (newIndex >= 0 && newIndex < tasks.length) {
        const temp = tasks[index];
        tasks[index] = tasks[newIndex];
        tasks[newIndex] = temp;
        populateEditor(appState.generatedData);
    }
};

window.deleteTask = function(prefix, index) {
    if (!appState.generatedData) return;
    const targetKey = (prefix === 'C') ? 'level_c' : ((prefix === 'A') ? 'level_a' : 'level_b');
    const tasks = appState.generatedData[targetKey]?.tasks;
    if (!tasks) return;
    if (tasks.length > 1) {
        tasks.splice(index, 1);
        populateEditor(appState.generatedData);
    }
};

window.refineTaskWithAI = async function(prefix, index) {
    if (!appState.generatedData) return;
    const targetKey = (prefix === 'C') ? 'level_c' : ((prefix === 'A') ? 'level_a' : 'level_b');
    const tasks = appState.generatedData[targetKey]?.tasks;
    if (!tasks || !tasks[index]) return;

    const currentTask = tasks[index];
    const instruction = prompt(
        "Wie möchtest du diese Aufgabe per KI anpassen?\n\n" +
        "Beispiele:\n" +
        "• 'Füge den Schwerpunkt Großschreibung hinzu'\n" +
        "• 'Mach die Sätze etwas kürzer und einfacher'\n" +
        "• 'Verwende Alltagsbeispiele aus der Lebenswelt der Kinder'",
        ""
    );

    if (!instruction || !instruction.trim()) return;

    showLoader(true);
    try {
        const response = await fetch('/api/refine_task', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                task: currentTask,
                instruction: instruction.trim(),
                subject: inputSubject?.value || "Deutsch",
                school_type: inputSchoolType?.value || "Grundschule",
                api_key: inputApiKey?.value || null
            })
        });

        if (!response.ok) throw new Error("Fehler bei der KI-Anpassung");
        const updatedTask = await response.json();
        
        tasks[index] = updatedTask;
        populateEditor(appState.generatedData);
    } catch (err) {
        console.error("Task refinement error:", err);
        alert("Anpassung fehlgeschlagen: " + err.message);
    } finally {
        showLoader(false);
    }
};

function populateEditor(data) {
    editorTitle.value = data.title || "Differenzierte Übung";
    editorSourceText.value = data.extracted_text || "";
    
    // Populate LehrplanPlus Badge
    const lehrplanBadge = document.getElementById('editor-lehrplan-badge');
    const lehrplanCodeSpan = document.getElementById('editor-lehrplan-code');
    const lehrplanTextSpan = document.getElementById('editor-lehrplan-text');
    if (lehrplanBadge && (data.lehrplan_code || data.lehrplan_competency)) {
        lehrplanBadge.classList.remove('hidden');
        if (lehrplanCodeSpan) lehrplanCodeSpan.textContent = data.lehrplan_code || 'LehrplanPlus';
        if (lehrplanTextSpan) lehrplanTextSpan.textContent = data.lehrplan_competency || 'Kompetenzen';
    } else if (lehrplanBadge) {
        lehrplanBadge.classList.add('hidden');
    }

    // Populate Hefteintrag
    if (editorHefteintragTitle && data.hefteintrag) {
        editorHefteintragTitle.value = data.hefteintrag.title || "Wie führe ich die Aufgabe aus?";
    }
    if (editorHefteintragSummary && data.hefteintrag) {
        editorHefteintragSummary.value = data.hefteintrag.summary || data.hefteintrag.level_a_notes || "";
    }

    // Render Level Tasks Helper
    function renderTasks(tasks, container, prefix) {
        if (!container) return;
        container.innerHTML = '';
        (tasks || []).forEach((t, i) => {
            const card = document.createElement('div');
            card.className = 'task-card p-4 bg-white border border-slate-200 rounded-xl shadow-sm space-y-3';
            
            const isLevelA = (prefix === 'A');
            const isLevelC = (prefix === 'C');
            const hintHtml = (isLevelA || isLevelC) ? `
                <div>
                    <label class="block text-xxs font-bold text-amber-700 uppercase tracking-wider mb-0.5">💡 Vorab-Tipp / Sprachhilfe</label>
                    <input type="text" class="task-hint w-full px-3 py-1.5 bg-amber-50/50 border border-amber-200 rounded-lg text-xs text-amber-900 focus:outline-none focus:ring-1 focus:ring-amber-500" value="${t.hint || ''}" placeholder="z. B. Tipp: Achte auf Wörter in Zeile 2">
                </div>
            ` : `
                <input type="hidden" class="task-hint" value="">
            `;

            card.innerHTML = `
                <div class="flex items-center gap-2">
                    <input type="text" class="task-title flex-1 px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs font-bold text-slate-700 focus:outline-none focus:ring-1 focus:ring-brand-500" value="${t.title}">
                    <select class="task-format w-1/3 px-2 py-1.5 bg-white border border-slate-200 rounded-lg text-xs font-semibold text-brand-600 focus:outline-none focus:ring-1 focus:ring-brand-500">
                        <option value="Lückentext" ${t.format === 'Lückentext' ? 'selected' : ''}>Lückentext</option>
                        <option value="Drag the Words" ${t.format === 'Drag the Words' ? 'selected' : ''}>Drag the Words</option>
                        <option value="Wahr/Falsch" ${t.format === 'Wahr/Falsch' ? 'selected' : ''}>Wahr/Falsch</option>
                        <option value="Multiple Choice" ${t.format === 'Multiple Choice' ? 'selected' : ''}>Multiple Choice</option>
                        <option value="Vokabelkarten" ${t.format === 'Vokabelkarten' ? 'selected' : ''}>Vokabelkarten</option>
                        <option value="Wörter markieren" ${t.format === 'Wörter markieren' ? 'selected' : ''}>Wörter markieren</option>
                    </select>
                    <div class="flex items-center gap-1">
                        <button type="button" onclick="moveTask('${prefix}', ${i}, -1)" class="p-1 text-slate-400 hover:text-slate-800 text-xs font-bold" title="Nach oben">▲</button>
                        <button type="button" onclick="moveTask('${prefix}', ${i}, 1)" class="p-1 text-slate-400 hover:text-slate-800 text-xs font-bold" title="Nach unten">▼</button>
                        <button type="button" onclick="deleteTask('${prefix}', ${i})" class="p-1 text-slate-400 hover:text-rose-600 text-xs font-bold" title="Löschen">🗑️</button>
                    </div>
                </div>
                <textarea class="task-text w-full p-3 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-brand-500 font-sans" rows="3">${t.text}</textarea>
                ${hintHtml}
                <div>
                    <label class="block text-xxs font-bold text-teal-700 uppercase tracking-wider mb-0.5">💬 Erklärung bei Fehler (Feedback)</label>
                    <input type="text" class="task-explanation w-full px-3 py-1.5 bg-teal-50/50 border border-teal-200 rounded-lg text-xs text-teal-900 focus:outline-none focus:ring-1 focus:ring-teal-500" value="${t.explanation || ''}" placeholder="Erklärung der richtigen Lösung...">
                </div>
                <div class="flex items-center justify-between pt-1 border-t border-slate-100">
                    <button type="button" onclick="refineTaskWithAI('${prefix}', ${i})" class="px-2.5 py-1 bg-brand-50 hover:bg-brand-100 text-brand-700 border border-brand-200 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5">
                        <i class="fa-solid fa-wand-magic-sparkles text-brand-600"></i> 🪄 Per KI anpassen / Schwerpunkt ergänzen
                    </button>
                </div>
            `;
            container.appendChild(card);
        });
    }

    const editorLevelCTasks = document.getElementById('editor-level-c-tasks');
    if (editorLevelCTasks) renderTasks(data.level_c?.tasks, editorLevelCTasks, 'C');
    renderTasks(data.level_a?.tasks, editorLevelATasks, 'A');
    renderTasks(data.level_b?.tasks, editorLevelBTasks, 'B');
    
    // Render Zusatzaufgaben
    if (editorZusatzaufgaben) {
        editorZusatzaufgaben.innerHTML = '';
        (data.zusatzaufgaben || []).forEach((z, zIdx) => {
            const zCard = document.createElement('div');
            zCard.className = 'zusatz-card p-3 bg-amber-50/60 border border-amber-200 rounded-xl space-y-2';
            zCard.innerHTML = `
                <input type="text" class="zusatz-title w-full px-3 py-1 bg-white border border-amber-200 rounded-lg text-xs font-bold text-amber-800" value="${z.title || 'Experten-Aufgabe ' + (zIdx+1)}">
                <textarea class="zusatz-text w-full p-2 bg-white border border-amber-200 rounded-lg text-xs text-slate-700 font-sans" rows="2">${z.task || ''}</textarea>
            `;
            editorZusatzaufgaben.appendChild(zCard);
        });
    }

    // Image preview handling
    const editorImagePreviewContainer = document.getElementById('editor-image-preview-container');
    const editorImagePreview = document.getElementById('editor-image-preview');
    if (appState.previewDataUrl) {
        editorImagePreview.src = appState.previewDataUrl;
        editorImagePreviewContainer.classList.remove('hidden');
    } else {
        editorImagePreview.src = '';
        editorImagePreviewContainer.classList.add('hidden');
    }
    
    // Clear and render diagnostic questions
    editorQuestions.innerHTML = '';
    const questions = data.diagnostic?.questions || [];
    
    questions.forEach((q, qIndex) => {
        const qCard = document.createElement('div');
        qCard.className = 'p-4 bg-slate-50 border border-slate-200 rounded-2xl space-y-3';
        
        qCard.innerHTML = `
            <div>
                <label class="block text-xs font-bold text-slate-500 mb-1">Frage ${qIndex + 1}</label>
                <input type="text" class="question-text w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-brand-500 font-medium" value="${q.question}">
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                    <label class="block text-xxs font-bold text-slate-400 mb-0.5">Option A</label>
                    <div class="flex items-center gap-2">
                        <input type="radio" name="correct_${qIndex}" value="0" ${q.correct === 0 ? 'checked' : ''} class="w-4 h-4 text-brand-600 border-slate-300 focus:ring-brand-500">
                        <input type="text" class="option-a w-full px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs font-medium focus:outline-none" value="${q.options[0] || ''}">
                    </div>
                </div>
                <div>
                    <label class="block text-xxs font-bold text-slate-400 mb-0.5">Option B</label>
                    <div class="flex items-center gap-2">
                        <input type="radio" name="correct_${qIndex}" value="1" ${q.correct === 1 ? 'checked' : ''} class="w-4 h-4 text-brand-600 border-slate-300 focus:ring-brand-500">
                        <input type="text" class="option-b w-full px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs font-medium focus:outline-none" value="${q.options[1] || ''}">
                    </div>
                </div>
            </div>
        `;
        editorQuestions.appendChild(qCard);
    });
}

btnBackToUpload.addEventListener('click', () => {
    showScreen(screenUpload);
});

// ----------------------------------------------------
// PACK & EXPORT FLOW
// ----------------------------------------------------
function getEditedData() {
    // Reconstruct the JSON model from editor inputs
    const questions = [];
    const questionCards = editorQuestions.querySelectorAll('.p-4');
    
    questionCards.forEach((card, qIndex) => {
        const questionText = card.querySelector('.question-text').value;
        const optionA = card.querySelector('.option-a').value;
        const optionB = card.querySelector('.option-b').value;
        const correctRadio = card.querySelector(`input[name="correct_${qIndex}"]:checked`);
        const correctVal = correctRadio ? parseInt(correctRadio.value) : 0;
        
        questions.push({
            question: questionText,
            options: [optionA, optionB],
            correct: correctVal
        });
    });

    // Reconstruct level tasks
    function extractTasks(container) {
        const tasks = [];
        container.querySelectorAll('.task-card').forEach(card => {
            const hintInput = card.querySelector('.task-hint');
            const expInput = card.querySelector('.task-explanation');
            tasks.push({
                title: card.querySelector('.task-title').value,
                text: card.querySelector('.task-text').value,
                format: card.querySelector('.task-format').value,
                hint: hintInput ? hintInput.value : '',
                explanation: expInput ? expInput.value : ''
            });
        });
        return tasks;
    }

    // Reconstruct zusatzaufgaben
    const zusatz = [];
    if (editorZusatzaufgaben) {
        editorZusatzaufgaben.querySelectorAll('.zusatz-card').forEach(card => {
            zusatz.push({
                title: card.querySelector('.zusatz-title').value,
                task: card.querySelector('.zusatz-text').value
            });
        });
    }

    const editorLevelCTasks = document.getElementById('editor-level-c-tasks');
    return {
        title: editorTitle.value,
        target_format: inputFormat.value,
        lehrplan_code: appState.generatedData?.lehrplan_code || "",
        lehrplan_competency: appState.generatedData?.lehrplan_competency || "",
        diagnostic: {
            questions: questions,
            threshold_pass_percent: parseInt(editorThreshold.value)
        },
        hefteintrag: {
            title: editorHefteintragTitle ? editorHefteintragTitle.value : "Hefteintrag / Merkkasten",
            summary: editorHefteintragSummary ? editorHefteintragSummary.value : "",
            level_a_notes: editorHefteintragSummary ? editorHefteintragSummary.value : "",
            level_b_notes: editorHefteintragSummary ? editorHefteintragSummary.value : ""
        },
        zusatzaufgaben: zusatz,
        level_c: {
            title: "Level C - Inklusion & DaZ",
            tasks: editorLevelCTasks ? extractTasks(editorLevelCTasks) : (appState.generatedData?.level_c?.tasks || [])
        },
        level_a: {
            title: "Level A - Grundlagen",
            tasks: extractTasks(editorLevelATasks)
        },
        level_b: {
            title: "Level B - Vertiefung",
            tasks: extractTasks(editorLevelBTasks)
        }
    };
}

btnPackH5P.addEventListener('click', () => {
    showScreen(screenExport);
});

// ----------------------------------------------------
// DOWNLOAD ACTIONS
// ----------------------------------------------------
btnDownloadH5P.addEventListener('click', async () => {
    const payload = getEditedData();
    
    try {
        const response = await fetch(`${API_BASE}/api/export/h5p`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
        });

        if (!response.ok) throw new Error("Failed to download H5P");

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${payload.title.replace(/\s+/g, '_')}_differenziert.h5p`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

    } catch (err) {
        console.error("H5P Download error:", err);
        alert("Herunterladen der H5P-Datei fehlgeschlagen.");
    }
});

let pdfLogoBase64 = null;
const pdfLogoFile = document.getElementById('pdf-logo-file');
if (pdfLogoFile) {
    pdfLogoFile.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (!file) {
            pdfLogoBase64 = null;
            return;
        }
        const reader = new FileReader();
        reader.onload = (event) => {
            pdfLogoBase64 = event.target.result;
        };
        reader.readAsDataURL(file);
    });
}

window.downloadSCORMPackage = async function() {
    const payload = getEditedData();
    try {
        const response = await fetch(`${API_BASE}/api/export/scorm`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (!response.ok) throw new Error("SCORM Export failed");
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${payload.title.replace(/\s+/g, '_')}_SCORM_LMS.zip`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    } catch (err) {
        console.error("SCORM export error:", err);
        alert("SCORM-Export fehlgeschlagen: " + err.message);
    }
};

window.copyIframeEmbedCode = function() {
    const pin = liveSessionPin || 'XXXX';
    const embedUrl = `${window.location.origin}/play.html?pin=${pin}`;
    const iframeCode = `<iframe src="${embedUrl}" width="100%" height="600" style="border:0; border-radius:16px; overflow:hidden;" allow="camera; microphone; autoplay"></iframe>`;
    
    if (navigator.clipboard) {
        navigator.clipboard.writeText(iframeCode).then(() => {
            alert("📋 mebis / ByCS iFrame-Einbettungscode kopiert!\n\nFüge ihn einfach in dein mebis- oder Moodle-Textfeld ein.");
        }).catch(() => {
            prompt("Kopiere diesen iFrame-Code für mebis / ByCS:", iframeCode);
        });
    } else {
        prompt("Kopiere diesen iFrame-Code für mebis / ByCS:", iframeCode);
    }
};

btnDownloadPDF.addEventListener('click', async () => {
    const payload = getEditedData();
    
    // Inject PDF customization parameters
    payload.pdf_teacher_name = document.getElementById('pdf-teacher-name')?.value || "";
    payload.pdf_class_name = document.getElementById('pdf-class-name')?.value || "";
    payload.pdf_accent_color = document.getElementById('pdf-accent-color')?.value || "#0284c7";
    payload.pdf_include_lehrplan = document.getElementById('pdf-include-lehrplan')?.checked ?? false;
    payload.pdf_include_level_c = document.getElementById('pdf-include-level-c')?.checked ?? false;
    payload.pdf_logo_base64 = pdfLogoBase64;
    
    const includeQR = document.getElementById('pdf-include-qr')?.checked ?? true;
    if (includeQR) {
        try {
            // Create session to generate live QR solution URL
            const sessRes = await fetch(`${API_BASE}/api/sessions/create`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title: payload.title, data: payload })
            });
            if (sessRes.ok) {
                const sessData = await sessRes.json();
                payload.session_pin = sessData.pin;
                payload.solution_url = `${window.location.origin}/play.html?pin=${sessData.pin}`;
            }
        } catch (e) {
            console.warn("Could not register live session for QR-Code:", e);
        }
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/export/pdf`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
        });

        if (!response.ok) throw new Error("Failed to download PDF");

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${payload.title.replace(/\s+/g, '_')}_arbeitsblatt.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

    } catch (err) {
        console.error("PDF Download error:", err);
        alert("Herunterladen des PDF-Arbeitsblattes fehlgeschlagen.");
    }
});

btnRestart.addEventListener('click', () => {
    resetFileSelection();
    inputContext.value = '';
    showScreen(screenUpload);
});

// ====================================================
// H5P BRANCHING-SCENARIO SIMULATOR
// ====================================================

// PARSER HELPERS FOR SIMULATOR
const SimParsers = {
    parseMultipleChoiceText(text) {
        const questions = [];
        const blocks = text.split(/Frage:\s*/i);
        blocks.forEach(block => {
            if (!block.trim()) return;
            const lines = block.trim().split("\n");
            const q_text = lines[0].trim();
            const answers = [];
            lines.slice(1).forEach(line => {
                const trimmed = line.trim();
                if (trimmed.startsWith("[ ]") || trimmed.startsWith("[X]") || trimmed.startsWith("[x]")) {
                    const is_correct = trimmed.startsWith("[X]") || trimmed.startsWith("[x]");
                    const ans_text = trimmed.substring(3).trim();
                    answers.push({
                        text: ans_text,
                        correct: is_correct
                    });
                }
            });
            if (q_text && answers.length > 0) {
                questions.push({
                    question: `<p>${q_text}</p>\n`,
                    answers: answers
                });
            }
        });
        
        // Fallback if formatting doesn't use "Frage:"
        if (questions.length === 0) {
            const lines = text.trim().split("\n");
            let q_text = "";
            const answers = [];
            lines.forEach(line => {
                const trimmed = line.trim();
                if (trimmed.startsWith("[ ]") || trimmed.startsWith("[X]") || trimmed.startsWith("[x]")) {
                    const is_correct = trimmed.startsWith("[X]") || trimmed.startsWith("[x]");
                    const ans_text = trimmed.substring(3).trim();
                    answers.push({ text: ans_text, correct: is_correct });
                } else if (trimmed) {
                    if (q_text) q_text += " " + trimmed;
                    else q_text = trimmed;
                }
            });
            if (q_text && answers.length > 0) {
                questions.push({ question: `<p>${q_text}</p>\n`, answers: answers });
            }
        }
        return questions;
    },

    parseTrueFalseText(text) {
        const statements = [];
        const blocks = text.split("---");
        blocks.forEach(block => {
            if (!block.trim()) return;
            const lines = block.trim().split("\n").map(l => l.trim()).filter(l => l);
            let statement = "";
            let answer = true;
            lines.forEach(line => {
                if (line.toLowerCase().startsWith("aussage:")) {
                    statement = line.substring(8).trim();
                } else if (line.toLowerCase().startsWith("antwort:")) {
                    const ans_str = line.substring(8).trim().toLowerCase();
                    answer = ans_str.includes("wahr") || ans_str.includes("true") || ans_str.includes("richtig");
                }
            });
            
            // Fallback
            if (!statement && lines.length > 0) {
                for (let line of lines) {
                    if (!line.toLowerCase().startsWith("antwort:")) {
                        statement = line;
                        break;
                    }
                }
            }
            if (statement) {
                statements.push({
                    question: `<p>${statement}</p>\n`,
                    correct: answer
                });
            }
        });
        return statements;
    },

    parseDialogcardsText(text) {
        const cards = [];
        const blocks = text.split("---");
        blocks.forEach(block => {
            if (!block.trim()) return;
            const lines = block.trim().split("\n").map(l => l.trim()).filter(l => l);
            let front = "";
            let back = "";
            lines.forEach(line => {
                if (line.startsWith("Vorderseite:")) {
                    front = line.substring(12).trim();
                } else if (line.toLowerCase().startsWith("rückseite:")) {
                    back = line.substring(10).trim();
                }
            });
            if (front && back) {
                cards.push({
                    text: front,
                    answer: back
                });
            }
        });
        return cards;
    },

    cleanSlashesForDragText(text) {
        function repl(match, content) {
            let word = content;
            let hint = "";
            if (word.includes(":")) {
                const idx = word.indexOf(":");
                hint = word.substring(idx);
                word = word.substring(0, idx);
            }
            if (word.includes("/")) {
                word = word.split("/", 1)[0];
            }
            return `*${word}${hint}*`;
        }
        return text.replace(/\*([^*]+)\*/g, repl);
    }
};

const previewModal = document.getElementById('preview-modal');
const btnSimulatePreview = document.getElementById('btn-simulate-preview');
const btnClosePreview = document.getElementById('btn-close-preview');
let simFrame = document.getElementById('sim-frame');
let simPathIndicator = document.getElementById('sim-path-indicator');
let simScoreIndicator = document.getElementById('sim-score-indicator');

function updateSimulatorDOMTargets() {
    const previewTabContent = document.getElementById('editor-content-preview');
    if (previewTabContent && !previewTabContent.classList.contains('hidden')) {
        simFrame = document.getElementById('editor-preview-sim-frame');
        simPathIndicator = document.getElementById('editor-preview-path');
        simScoreIndicator = document.getElementById('editor-preview-score');
    } else {
        simFrame = document.getElementById('sim-frame');
        simPathIndicator = document.getElementById('sim-path-indicator');
        simScoreIndicator = document.getElementById('sim-score-indicator');
    }
}

let simState = {
    currentStep: 'start', // 'start', 'quiz', 'level-intro', 'tasks', 'experts', 'end'
    diagnosticIndex: 0,
    diagnosticAnswers: [],
    correctQuizCount: 0,
    levelRoute: 'A',
    taskIndex: 0,
    tasks: [],
    score: 0,
    maxScore: 0,
    data: null,
    checkedCurrentTask: false,
    userAnswers: {}
};

if (btnSimulatePreview) {
    btnSimulatePreview.addEventListener('click', () => {
        // If large screen, switch tab. Otherwise, open modal.
        if (window.innerWidth >= 1024) { // 1024px is lg breakpoint
            switchEditorTab('preview');
            document.getElementById('screen-editor').scrollIntoView({ behavior: 'smooth' });
        } else {
            const data = getEditedData();
            if (!data) return;
            
            simState.data = data;
            simState.currentStep = 'start';
            simState.diagnosticIndex = 0;
            simState.diagnosticAnswers = [];
            simState.correctQuizCount = 0;
            simState.taskIndex = 0;
            simState.score = 0;
            simState.maxScore = 0;
            simState.checkedCurrentTask = false;
            simState.userAnswers = {};
            
            previewModal.classList.remove('hidden');
            renderSimulator();
        }
    });
}

window.switchEditorTab = function(tabName) {
    const tabSource = document.getElementById('editor-tab-source');
    const tabPreview = document.getElementById('editor-tab-preview');
    const contentSource = document.getElementById('editor-content-source');
    const contentPreview = document.getElementById('editor-content-preview');
    
    if (!tabSource || !tabPreview || !contentSource || !contentPreview) return;
    
    if (tabName === 'source') {
        tabSource.classList.add('text-brand-600', 'border-brand-500');
        tabSource.classList.remove('text-slate-400', 'border-transparent');
        tabPreview.classList.add('text-slate-400', 'border-transparent');
        tabPreview.classList.remove('text-brand-600', 'border-brand-500');
        
        contentSource.classList.remove('hidden');
        contentPreview.classList.add('hidden');
    } else {
        tabPreview.classList.add('text-brand-600', 'border-brand-500');
        tabPreview.classList.remove('text-slate-400', 'border-transparent');
        tabSource.classList.add('text-slate-400', 'border-transparent');
        tabSource.classList.remove('text-brand-600', 'border-brand-500');
        
        contentPreview.classList.remove('hidden');
        contentSource.classList.add('hidden');
        
        // Sync simulator data and start preview
        simState.data = getEditedData();
        
        // Restart simulator state if not initialized or on end screen
        if (!simState.currentStep || simState.currentStep === 'end') {
            simState.currentStep = 'start';
            simState.diagnosticIndex = 0;
            simState.diagnosticAnswers = [];
            simState.correctQuizCount = 0;
            simState.taskIndex = 0;
            simState.score = 0;
            simState.maxScore = 0;
            simState.checkedCurrentTask = false;
            simState.userAnswers = {};
        }
        
        // Match current route tasks
        const isB = (simState.levelRoute === 'B');
        simState.tasks = isB ? (simState.data.level_b.tasks || []) : (simState.data.level_a.tasks || []);
        
        renderSimulator();
    }
};

function initLivePreviewSync() {
    const editorContainer = document.getElementById('screen-editor');
    if (!editorContainer) return;
    
    editorContainer.addEventListener('input', () => {
        const previewTabContent = document.getElementById('editor-content-preview');
        // Only sync if the live preview tab is actually visible
        if (previewTabContent && !previewTabContent.classList.contains('hidden') && simState.data) {
            const edited = getEditedData();
            simState.data.title = edited.title;
            simState.data.diagnostic = edited.diagnostic;
            simState.data.hefteintrag = edited.hefteintrag;
            simState.data.zusatzaufgaben = edited.zusatzaufgaben;
            simState.data.level_a = edited.level_a;
            simState.data.level_b = edited.level_b;
            
            const currentRoute = simState.levelRoute;
            if (currentRoute === 'A') {
                simState.tasks = edited.level_a.tasks || [];
            } else if (currentRoute === 'B') {
                simState.tasks = edited.level_b.tasks || [];
            }
            
            renderSimulator();
        }
    });
}

if (btnClosePreview) {
    btnClosePreview.addEventListener('click', () => {
        previewModal.classList.add('hidden');
    });
}

if (previewModal) {
    // Close modal when clicking outside
    previewModal.addEventListener('click', (e) => {
        if (e.target === previewModal) {
            previewModal.classList.add('hidden');
        }
    });
}

function renderSimulator() {
    updateSimulatorDOMTargets();
    const frame = simFrame;
    const step = simState.currentStep;
    const data = simState.data;
    if (!frame || !data) return;
    
    // Update Indicators
    if (step === 'start') {
        simPathIndicator.textContent = "Aktueller Pfad: Startbildschirm";
        simScoreIndicator.textContent = "Ergebnis: -";
    } else if (step === 'quiz') {
        simPathIndicator.textContent = `Aktueller Pfad: Diagnose (Frage ${simState.diagnosticIndex + 1}/${data.diagnostic.questions.length})`;
        simScoreIndicator.textContent = `Ergebnis: -`;
    } else if (step === 'level-intro') {
        simPathIndicator.textContent = `Aktueller Pfad: Einstufung (Level ${simState.levelRoute})`;
        simScoreIndicator.textContent = `Ergebnis: -`;
    } else if (step === 'tasks') {
        simPathIndicator.textContent = `Aktueller Pfad: Level ${simState.levelRoute} (Aufgabe ${simState.taskIndex + 1}/${simState.tasks.length})`;
        simScoreIndicator.textContent = `Punkte: ${simState.score}/${simState.maxScore}`;
    } else if (step === 'experts') {
        simPathIndicator.textContent = `Aktueller Pfad: Zusatzaufgaben (Experten-Modus)`;
        simScoreIndicator.textContent = `Punkte: ${simState.score}/${simState.maxScore}`;
    } else if (step === 'end') {
        simPathIndicator.textContent = `Aktueller Pfad: Abschluss`;
        simScoreIndicator.textContent = `Punkte: ${simState.score}/${simState.maxScore}`;
    }

    // Render Steps
    if (step === 'start') {
        frame.innerHTML = `
            <div class="flex-1 flex flex-col justify-between p-8 text-center bg-gradient-to-b from-brand-50/50 to-white min-h-[480px]">
                <div class="space-y-4 my-auto">
                    <div class="h-16 w-16 bg-brand-600 text-white rounded-2xl flex items-center justify-center text-2xl mx-auto shadow-md">
                        <i class="fa-solid fa-graduation-cap"></i>
                    </div>
                    <h4 class="text-xl font-black text-slate-800">${data.title}</h4>
                    <p class="text-xs text-slate-500 max-w-md mx-auto">
                        Beantworte zuerst ein paar kurze Fragen, um deinen aktuellen Wissensstand zu prüfen. Danach geht es automatisch auf dem passenden Niveau weiter!
                    </p>
                </div>
                <button onclick="startQuiz()" class="w-full py-3 bg-brand-600 hover:bg-brand-700 text-white font-bold rounded-xl shadow-lg transition-all flex items-center justify-center gap-2 text-sm">
                    Kurs starten <i class="fa-solid fa-arrow-right"></i>
                </button>
            </div>
        `;
    } else if (step === 'quiz') {
        const question = data.diagnostic.questions[simState.diagnosticIndex];
        frame.innerHTML = `
            <div class="flex-1 flex flex-col justify-between p-6 bg-white min-h-[480px]">
                <div class="space-y-4 my-auto">
                    <div class="flex justify-between items-center text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                        <span>Diagnosefrage ${simState.diagnosticIndex + 1} von ${data.diagnostic.questions.length}</span>
                    </div>
                    <h5 class="text-sm font-bold text-slate-800 leading-snug">${question.question}</h5>
                    <div class="grid grid-cols-1 gap-2.5">
                        ${question.options.map((opt, i) => `
                            <button onclick="answerQuiz(${i})" class="w-full py-2.5 px-4 bg-slate-50 hover:bg-brand-50 hover:text-brand-800 text-slate-700 font-semibold text-xs text-left rounded-xl border border-slate-200 hover:border-brand-300 transition-all flex items-center justify-between group">
                                <span>${opt}</span>
                                <i class="fa-regular fa-circle text-slate-300 group-hover:text-brand-500"></i>
                            </button>
                        `).join('')}
                    </div>
                </div>
                <div class="h-1.5 bg-slate-100 rounded-full overflow-hidden mt-4">
                    <div class="h-full bg-brand-500 transition-all" style="width: ${(simState.diagnosticIndex / data.diagnostic.questions.length) * 100}%"></div>
                </div>
            </div>
        `;
    } else if (step === 'level-intro') {
        const isB = (simState.levelRoute === 'B');
        const levelTitle = isB ? data.level_b.title : data.level_a.title;
        frame.innerHTML = `
            <div class="flex-1 flex flex-col justify-between p-8 text-center bg-gradient-to-b ${isB ? 'from-indigo-50/50 to-white' : 'from-teal-50/50 to-white'} min-h-[480px]">
                <div class="space-y-4 my-auto">
                    <div class="h-14 w-14 ${isB ? 'bg-indigo-600 text-white' : 'bg-teal-600 text-white'} rounded-full flex items-center justify-center text-2xl mx-auto shadow-md">
                        <i class="fa-solid ${isB ? 'fa-circle-chevron-up' : 'fa-circle-chevron-down'}"></i>
                    </div>
                    <div class="space-y-1">
                        <span class="text-[10px] font-bold uppercase tracking-widest ${isB ? 'text-indigo-600' : 'text-teal-600'}">Diagnose abgeschlossen</span>
                        <h4 class="text-lg font-black text-slate-800">${levelTitle}</h4>
                    </div>
                    <p class="text-xs text-slate-500 max-w-sm mx-auto leading-relaxed">
                        ${isB 
                            ? 'Hervorragend! Du hast die Fragen fehlerfrei oder fast fehlerfrei gelöst und wirst direkt zur anspruchsvollen Vertiefung geleitet.' 
                            : 'Alles klar! Wir starten mit den Grundlagen und führen dich Schritt für Schritt an die Übungen heran. Du erhältst hilfreiche Tipps.'}
                    </p>
                </div>
                <button onclick="startLevelTasks()" class="w-full py-3 ${isB ? 'bg-indigo-600 hover:bg-indigo-700' : 'bg-teal-600 hover:bg-teal-700'} text-white font-bold rounded-xl shadow-lg transition-all flex items-center justify-center gap-2 text-sm">
                    Mit den Übungen starten <i class="fa-solid fa-arrow-right"></i>
                </button>
            </div>
        `;
    } else if (step === 'tasks') {
        const task = simState.tasks[simState.taskIndex];
        const isLevelA = (simState.levelRoute === 'A');
        
        let taskWidgetHtml = '';
        if (task.format === 'Multiple Choice') {
            taskWidgetHtml = renderSimMultipleChoice(task);
        } else if (task.format === 'Wahr/Falsch') {
            taskWidgetHtml = renderSimTrueFalse(task);
        } else if (task.format === 'Vokabelkarten') {
            taskWidgetHtml = renderSimDialogCards(task);
        } else if (task.format === 'Drag the Words') {
            taskWidgetHtml = renderSimDragText(task);
        } else if (task.format === 'Wörter markieren') {
            taskWidgetHtml = renderSimMarkTheWords(task);
        } else { // Lückentext
            taskWidgetHtml = renderSimBlanks(task);
        }

        frame.innerHTML = `
            <div class="flex-1 flex flex-col justify-between p-6 bg-white min-h-[480px]">
                <div class="flex items-center justify-between border-b pb-3 mb-4">
                    <span class="text-[10px] font-bold ${isLevelA ? 'text-teal-600 bg-teal-50 border border-teal-200' : 'text-indigo-600 bg-indigo-50 border border-indigo-200'} px-2.5 py-1 rounded-full uppercase tracking-wider">
                        ${isLevelA ? 'Level A – Grundlagen' : 'Level B – Vertiefung'}
                    </span>
                    <span class="text-xs text-slate-400 font-semibold">Aufgabe ${simState.taskIndex + 1} von ${simState.tasks.length}</span>
                </div>
                
                <div class="flex-1 flex flex-col justify-center space-y-4 my-auto select-none">
                    <h5 class="text-sm font-extrabold text-slate-800 flex items-center gap-2">
                        <i class="fa-solid fa-circle-question ${isLevelA ? 'text-teal-600' : 'text-indigo-600'}"></i>
                        ${task.title}
                    </h5>
                    
                    <div class="task-widget bg-slate-50/50 p-4 border border-slate-200 rounded-xl">
                        ${taskWidgetHtml}
                    </div>
                    
                    <div id="sim-feedback-box" class="hidden p-3 rounded-xl text-xs font-semibold"></div>
                </div>
                
                <div class="flex gap-4 mt-6 border-t pt-4">
                    <button id="sim-btn-check" onclick="checkCurrentTask()" class="flex-1 py-2.5 bg-brand-600 hover:bg-brand-700 text-white font-bold rounded-xl shadow-md transition-all text-xs">
                        Überprüfen
                    </button>
                    <button id="sim-btn-next" onclick="nextTask()" class="flex-1 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold rounded-xl transition-all flex items-center justify-center gap-1.5 opacity-50 cursor-not-allowed text-xs" disabled>
                        Weiter <i class="fa-solid fa-arrow-right text-[10px]"></i>
                    </button>
                </div>
            </div>
        `;
        
        if (simState.checkedCurrentTask) {
            restoreCheckedTaskState(task);
        }
    } else if (step === 'experts') {
        const experts = data.zusatzaufgaben || [];
        frame.innerHTML = `
            <div class="flex-1 flex flex-col justify-between p-6 bg-white min-h-[480px]">
                <div class="space-y-4 my-auto">
                    <div class="text-center space-y-2">
                        <div class="h-12 w-14 bg-amber-100 text-amber-600 rounded-2xl flex items-center justify-center text-xl mx-auto shadow-inner">
                            <i class="fa-solid fa-star"></i>
                        </div>
                        <h4 class="text-base font-black text-slate-800">Experten-Zone (Zusatzaufgaben)</h4>
                        <p class="text-[10px] text-slate-500 max-w-sm mx-auto">
                            Diese Aufgaben sind für Schnellarbeiter gedacht. Überlege dir eine Lösung im Kopf.
                        </p>
                    </div>
                    <div class="space-y-2.5 max-h-[220px] overflow-y-auto pr-2">
                        ${experts.map((exp, idx) => `
                            <div class="p-3 bg-amber-50/50 border border-amber-200 rounded-xl space-y-1">
                                <h6 class="text-[10px] font-extrabold text-amber-900">${exp.title || `Experten-Aufgabe ${idx+1}`}</h6>
                                <p class="text-xs text-slate-600 font-medium leading-relaxed">${exp.task}</p>
                            </div>
                        `).join('')}
                    </div>
                </div>
                <button onclick="goToEnd()" class="w-full py-3 bg-slate-900 hover:bg-slate-800 text-white font-bold rounded-xl shadow-lg transition-all flex items-center justify-center gap-2 text-sm mt-4">
                    Kurs abschließen <i class="fa-solid fa-check-double"></i>
                </button>
            </div>
        `;
    } else if (step === 'end') {
        frame.innerHTML = `
            <div class="flex-1 flex flex-col justify-between p-8 text-center bg-gradient-to-b from-teal-50/30 to-white min-h-[480px]">
                <div class="space-y-4 my-auto">
                    <div class="h-14 w-14 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center text-2xl mx-auto shadow-md">
                        <i class="fa-solid fa-trophy"></i>
                    </div>
                    <h4 class="text-xl font-black text-slate-800">Glückwunsch!</h4>
                    <p class="text-xs text-slate-600 max-w-xs mx-auto font-medium leading-relaxed">
                        Du hast das adaptive Branching-Szenario erfolgreich beendet.
                    </p>
                    <div class="inline-block p-4 bg-slate-50 border border-slate-200 rounded-2xl shadow-inner my-2">
                        <span class="block text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Deine Gesamtpunktzahl</span>
                        <span class="text-2xl font-black text-brand-600">${simState.score}</span>
                        <span class="text-xs text-slate-400 font-bold">/ ${simState.maxScore} Punkten</span>
                    </div>
                </div>
                <button onclick="resetSimulator()" class="w-full py-3 border border-slate-200 hover:bg-slate-50 text-slate-700 font-bold rounded-xl transition-all flex items-center justify-center gap-2 text-sm">
                    Vorschau wiederholen <i class="fa-solid fa-rotate-right"></i>
                </button>
            </div>
        `;
    }
}

// Global functions exposed to onclick attributes
window.startQuiz = function() {
    simState.currentStep = 'quiz';
    renderSimulator();
};

window.answerQuiz = function(selectedOptionIndex) {
    const data = simState.data;
    const question = data.diagnostic.questions[simState.diagnosticIndex];
    
    simState.diagnosticAnswers.push(selectedOptionIndex);
    if (selectedOptionIndex === question.correct) {
        simState.correctQuizCount++;
    }
    
    simState.diagnosticIndex++;
    if (simState.diagnosticIndex < data.diagnostic.questions.length) {
        renderSimulator();
    } else {
        const scorePercent = (simState.correctQuizCount / data.diagnostic.questions.length) * 100;
        const threshold = parseInt(document.getElementById('editor-threshold')?.value || data.diagnostic.threshold_pass_percent || 60);
        
        if (scorePercent >= threshold) {
            simState.levelRoute = 'B';
            simState.tasks = data.level_b.tasks || [];
        } else {
            simState.levelRoute = 'A';
            simState.tasks = data.level_a.tasks || [];
        }
        
        simState.currentStep = 'level-intro';
        renderSimulator();
    }
};

window.startLevelTasks = function() {
    simState.currentStep = 'tasks';
    simState.taskIndex = 0;
    simState.score = 0;
    simState.maxScore = 0;
    simState.checkedCurrentTask = false;
    renderSimulator();
};

window.goToEnd = function() {
    simState.currentStep = 'end';
    renderSimulator();
    triggerConfetti();
};

window.resetSimulator = function() {
    simState.currentStep = 'start';
    simState.diagnosticIndex = 0;
    simState.diagnosticAnswers = [];
    simState.correctQuizCount = 0;
    simState.taskIndex = 0;
    simState.score = 0;
    simState.maxScore = 0;
    simState.checkedCurrentTask = false;
    simState.userAnswers = {};
    renderSimulator();
};

window.toggleSimMCCheckbox = function(event, labelEl) {
    if (simState.checkedCurrentTask) return;
    const checkbox = labelEl.querySelector('input[type="checkbox"]');
    if (checkbox && event.target !== checkbox) {
        checkbox.checked = !checkbox.checked;
    }
};

function renderSimMultipleChoice(task) {
    const mc_questions = SimParsers.parseMultipleChoiceText(task.text);
    const q = mc_questions[0] || { 
        question: task.title || "Optionen auswählen", 
        answers: [
            { text: "Antwort Option 1 (Standard)", correct: true },
            { text: "Antwort Option 2 (Standard)", correct: false }
        ] 
    };
    
    return `
        <div class="space-y-3">
            <p class="text-xs font-semibold text-slate-700">${q.question.replace(/<[^>]+>/g, '')}</p>
            <div class="space-y-2" id="sim-mc-options">
                ${q.answers.map((ans, i) => `
                    <label onclick="toggleSimMCCheckbox(event, this)" class="flex items-center gap-3 p-2.5 bg-white border border-slate-200 rounded-xl cursor-pointer hover:bg-slate-50 transition-all select-none text-xs">
                        <input type="checkbox" value="${i}" onclick="event.stopPropagation();" class="w-4 h-4 text-brand-600 border-slate-300 rounded focus:ring-brand-500">
                        <span class="font-semibold text-slate-700">${ans.text}</span>
                    </label>
                `).join('')}
            </div>
        </div>
    `;
}

function renderSimTrueFalse(task) {
    const tf = SimParsers.parseTrueFalseText(task.text);
    const q = tf[0] || { 
        question: task.title || "Aussage", 
        correct: true 
    };
    
    return `
        <div class="space-y-3 text-center">
            <p class="text-xs font-semibold text-slate-700">${q.question.replace(/<[^>]+>/g, '')}</p>
            <div class="flex gap-4 justify-center" id="sim-tf-options">
                <button onclick="selectSimTF(true)" id="sim-tf-true" class="py-2 px-5 border border-slate-200 bg-white hover:bg-slate-50 rounded-xl text-xs font-bold text-slate-700 transition-all">Wahr</button>
                <button onclick="selectSimTF(false)" id="sim-tf-false" class="py-2 px-5 border border-slate-200 bg-white hover:bg-slate-50 rounded-xl text-xs font-bold text-slate-700 transition-all">Falsch</button>
            </div>
        </div>
    `;
}

window.selectSimTF = function(val) {
    if (simState.checkedCurrentTask) return;
    simState.userAnswers['tf'] = val;
    document.getElementById('sim-tf-true').classList.toggle('bg-brand-600', val);
    document.getElementById('sim-tf-true').classList.toggle('text-white', val);
    document.getElementById('sim-tf-false').classList.toggle('bg-brand-600', !val);
    document.getElementById('sim-tf-false').classList.toggle('text-white', !val);
};

function renderSimDialogCards(task) {
    const cards = SimParsers.parseDialogcardsText(task.text) || [];
    const card = cards[0] || { 
        text: task.title || "Vorderseite", 
        answer: "Rückseite (Kein Text generiert)" 
    };
    
    return `
        <div class="space-y-4 text-center">
            <div onclick="flipSimCard()" class="h-28 w-full bg-white border border-slate-200 rounded-xl flex flex-col items-center justify-center p-4 cursor-pointer shadow-sm hover:shadow transition-all relative" id="sim-card-body">
                <p class="text-xs font-bold text-slate-800" id="sim-card-text">${card.text}</p>
                <span class="absolute bottom-1.5 right-2 text-[8px] font-bold text-slate-400 uppercase tracking-widest"><i class="fa-solid fa-rotate"></i> Drehen</span>
            </div>
            <div class="flex justify-center gap-3 hidden" id="sim-card-fb-buttons">
                <button onclick="selectSimCardFeedback(false)" class="py-1.5 px-3.5 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 rounded-xl text-[10px] font-bold transition-all">Falsch</button>
                <button onclick="selectSimCardFeedback(true)" class="py-1.5 px-3.5 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200 rounded-xl text-[10px] font-bold transition-all">Gewusst</button>
            </div>
        </div>
    `;
}

window.flipSimCard = function() {
    const textEl = document.getElementById('sim-card-text');
    const task = simState.tasks[simState.taskIndex];
    const cards = SimParsers.parseDialogcardsText(task.text) || [];
    const card = cards[0] || { text: "Front", answer: "Back" };
    const isShowingFront = (textEl.textContent === card.text);
    
    textEl.textContent = isShowingFront ? card.answer : card.text;
    textEl.classList.toggle('text-brand-600', isShowingFront);
    textEl.classList.toggle('font-black', isShowingFront);
    
    if (isShowingFront) {
        document.getElementById('sim-card-fb-buttons').classList.remove('hidden');
    }
};

window.selectSimCardFeedback = function(val) {
    if (simState.checkedCurrentTask) return;
    simState.userAnswers['card'] = val;
    checkCurrentTask();
};

function renderSimBlanks(task) {
    let cleanText = task.text;
    let gapIndex = 0;
    const processed = cleanText.replace(/\*([^*]+)\*/g, (match, word) => {
        let content = word;
        if (!content.trim() || ['*', '/', '+', '-', '=', '•'].includes(content.trim())) {
            return match;
        }
        if (content.includes(':')) {
            content = content.split(':', 1)[0];
        }
        const size = Math.max(content.split('/')[0].length + 2, 8);
        const inputHtml = `<input type="text" data-gap="${gapIndex}" class="sim-blank px-2 py-0.5 border border-slate-300 rounded focus:outline-none focus:ring-1 focus:ring-brand-500 font-bold text-center text-xs text-brand-700" style="width: ${size * 7}px;">`;
        gapIndex++;
        return inputHtml;
    });
    
    return `
        <div class="text-xs leading-relaxed text-slate-600 text-left font-medium space-y-2">
            <p>${processed.replace(/\n/g, '<br/>')}</p>
        </div>
    `;
}

function renderSimMarkTheWords(task) {
    const rawText = SimParsers.cleanSlashesForDragText(task.text);
    let correctIndices = [];
    let wordCounter = 0;
    
    const tokenized = rawText.replace(/\*([^*]+)\*/g, (match, word) => {
        const id = wordCounter++;
        correctIndices.push(id);
        return `__CORRECT_${id}_${word}__`;
    });
    
    const tokens = tokenized.split(/(\s+)/);
    
    const renderedHtml = tokens.map(token => {
        if (!token.trim()) return token;
        
        const match = token.match(/__CORRECT_(\d+)_(.+)__/);
        if (match) {
            const id = match[1];
            const text = match[2];
            return `<span data-word-id="${id}" data-correct="true" onclick="toggleSimMarkWord(this)" class="sim-mark-word px-1 py-0.5 rounded cursor-pointer hover:bg-brand-100 transition-all font-bold text-slate-800 border border-transparent select-none">${text}</span>`;
        } else {
            return `<span data-correct="false" onclick="toggleSimMarkWord(this)" class="sim-mark-word px-1 py-0.5 rounded cursor-pointer hover:bg-brand-100 transition-all text-slate-700 border border-transparent select-none">${token}</span>`;
        }
    }).join('');

    return `
        <div class="space-y-3">
            <p class="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">Klicke auf die gesuchten Wörter:</p>
            <div class="leading-relaxed text-xs p-3 bg-white border border-slate-200 rounded-xl font-medium text-left" id="sim-mark-text-container">
                ${renderedHtml}
            </div>
        </div>
    `;
}

window.toggleSimMarkWord = function(el) {
    if (simState.checkedCurrentTask) return;
    el.classList.toggle('bg-brand-600');
    el.classList.toggle('text-white');
    el.classList.toggle('selected');
};

function renderSimDragText(task) {
    const dragTextField = SimParsers.cleanSlashesForDragText(task.text);
    let gapIndex = 0;
    const words = [];
    
    const processed = dragTextField.replace(/\*([^*]+)\*/g, (match, content) => {
        let word = content;
        if (!word.trim() || ['*', '/', '+', '-', '=', '•'].includes(word.trim())) {
            return match;
        }
        if (word.includes(':')) {
            word = word.split(':', 1)[0];
        }
        words.push(word);
        const dropHtml = `<div data-gap="${gapIndex}" onclick="handleDropzoneClick(this)" class="sim-dropzone inline-block w-24 h-6 border border-dashed border-slate-300 rounded bg-slate-100/50 align-middle text-center text-xs font-bold text-slate-800 cursor-pointer" ondragover="allowSimDrop(event)" ondrop="simDrop(event)"></div>`;
        gapIndex++;
        return dropHtml;
    });
    
    const shuffledWords = [...words].sort(() => Math.random() - 0.5);
    
    return `
        <div class="space-y-4 text-left">
            <div class="text-xs leading-relaxed text-slate-600 font-medium space-y-2">
                <p>${processed.replace(/\n/g, '<br/>')}</p>
            </div>
            <div class="flex flex-wrap gap-2 pt-3 border-t border-slate-200/50" id="sim-drag-words-pool">
                ${shuffledWords.map((word, i) => `
                    <div id="sim-word-${i}" onclick="handleWordClick(this)" draggable="true" ondragstart="simDrag(event)" class="px-2.5 py-1 bg-white border border-slate-200 rounded-lg shadow-sm font-bold text-xs text-brand-700 cursor-grab hover:bg-slate-50 transition-all select-none">${word}</div>
                `).join('')}
            </div>
        </div>
    `;
}

// --- Drag and Drop & Touch Tap Fallback Polyfill ---
let selectedDragWord = null;

window.handleWordClick = function(el) {
    if (simState.checkedCurrentTask) return;
    
    if (selectedDragWord === el) {
        el.classList.remove('ring-4', 'ring-brand-500', 'bg-brand-50');
        selectedDragWord = null;
        return;
    }
    
    if (selectedDragWord) {
        selectedDragWord.classList.remove('ring-4', 'ring-brand-500', 'bg-brand-50');
    }
    
    selectedDragWord = el;
    el.classList.add('ring-4', 'ring-brand-500', 'bg-brand-50');
};

window.handleDropzoneClick = function(dz) {
    if (simState.checkedCurrentTask) return;
    
    if (dz.textContent.trim()) {
        const text = dz.textContent.trim();
        const poolWords = document.querySelectorAll('#sim-drag-words-pool div');
        for (let pw of poolWords) {
            if (pw.textContent.trim() === text && (pw.style.opacity === '0.5' || pw.classList.contains('opacity-50'))) {
                pw.style.opacity = '1';
                pw.classList.remove('opacity-50');
                pw.setAttribute('draggable', 'true');
                break;
            }
        }
        dz.textContent = '';
        dz.classList.add('bg-slate-100/50', 'border-dashed');
        dz.classList.remove('bg-white', 'border-solid', 'shadow-inner');
        return;
    }
    
    if (selectedDragWord) {
        dz.textContent = selectedDragWord.textContent;
        dz.classList.remove('bg-slate-100/50', 'border-dashed');
        dz.classList.add('bg-white', 'border-solid', 'border-slate-300', 'shadow-inner');
        
        selectedDragWord.style.opacity = '0.5';
        selectedDragWord.classList.add('opacity-50');
        selectedDragWord.classList.remove('ring-4', 'ring-brand-500', 'bg-brand-50');
        selectedDragWord.setAttribute('draggable', 'false');
        selectedDragWord = null;
    }
};

window.allowSimDrop = function(e) {
    e.preventDefault();
};

window.simDrag = function(e) {
    if (simState.checkedCurrentTask) return;
    e.dataTransfer.setData("text", e.target.id);
};

window.simDrop = function(e) {
    e.preventDefault();
    if (simState.checkedCurrentTask) return;
    
    const data = e.dataTransfer.getData("text");
    const dragged = document.getElementById(data);
    if (!dragged) return;
    
    const dz = e.target.closest('.sim-dropzone');
    if (dz && !dz.textContent.trim()) {
        dz.textContent = dragged.textContent;
        dz.classList.remove('bg-slate-100/50', 'border-dashed');
        dz.classList.add('bg-white', 'border-solid', 'border-slate-300', 'shadow-inner');
        dragged.style.opacity = '0.5';
        dragged.classList.add('opacity-50');
        dragged.setAttribute('draggable', 'false');
    }
};

window.checkCurrentTask = function() {
    if (simState.checkedCurrentTask) return;
    
    const task = simState.tasks[simState.taskIndex];
    let correct = false;
    let earnedPoints = 0;
    let taskMax = 0;
    
    const fbBox = document.getElementById('sim-feedback-box');
    fbBox.classList.remove('hidden', 'bg-rose-50', 'text-rose-700', 'bg-emerald-50', 'text-emerald-700');
    
    if (task.format === 'Multiple Choice') {
        const mc_questions = SimParsers.parseMultipleChoiceText(task.text);
        const q = mc_questions[0];
        const checkedOptions = Array.from(document.querySelectorAll('#sim-mc-options input[type="checkbox"]:checked')).map(el => parseInt(el.value));
        
        let allCorrect = true;
        q.answers.forEach((ans, i) => {
            const isChecked = checkedOptions.includes(i);
            if (ans.correct !== isChecked) {
                allCorrect = false;
            }
        });
        
        earnedPoints = allCorrect ? 1 : 0;
        taskMax = 1;
        correct = allCorrect;
        
        document.querySelectorAll('#sim-mc-options label').forEach((label, i) => {
            const isCorrect = q.answers[i].correct;
            label.classList.add(isCorrect ? 'border-emerald-400' : 'border-rose-200');
            label.classList.add(isCorrect ? 'bg-emerald-50/10' : 'bg-rose-50/10');
        });
        
    } else if (task.format === 'Wahr/Falsch') {
        const tf = SimParsers.parseTrueFalseText(task.text);
        const q = tf[0];
        const userChoice = simState.userAnswers['tf'];
        
        correct = (userChoice === q.correct);
        earnedPoints = correct ? 1 : 0;
        taskMax = 1;
        
        document.getElementById('sim-tf-true').classList.add(q.correct ? 'border-emerald-500' : 'border-rose-300');
        document.getElementById('sim-tf-false').classList.add(!q.correct ? 'border-emerald-500' : 'border-rose-300');
        
    } else if (task.format === 'Vokabelkarten') {
        const userChoice = simState.userAnswers['card'];
        correct = (userChoice === true);
        earnedPoints = correct ? 1 : 0;
        taskMax = 1;
        
    } else if (task.format === 'Drag the Words') {
        const dragTextField = SimParsers.cleanSlashesForDragText(task.text);
        const words = [];
        dragTextField.replace(/\*([^*]+)\*/g, (match, content) => {
            let word = content;
            if (!word.trim() || ['*', '/', '+', '-', '=', '•'].includes(word.trim())) {
                return match;
            }
            if (word.includes(':')) {
                word = word.split(':', 1)[0];
            }
            words.push(word.trim().toLowerCase());
            return '';
        });
        
        let dropzones = document.querySelectorAll('.sim-dropzone');
        dropzones.forEach((dz, i) => {
            const userText = dz.textContent.trim().toLowerCase();
            const correctText = words[i];
            const isCorrect = (userText === correctText);
            dz.classList.add(isCorrect ? 'border-emerald-400' : 'border-rose-400');
            dz.classList.add(isCorrect ? 'bg-emerald-50' : 'bg-rose-50');
            dz.classList.remove('bg-white');
            if (isCorrect) {
                earnedPoints++;
            }
            taskMax++;
        });
        correct = (earnedPoints === taskMax);
        
    } else if (task.format === 'Wörter markieren') {
        let correctCount = 0;
        let incorrectCount = 0;
        let totalCorrectWords = 0;
        
        document.querySelectorAll('#sim-mark-text-container .sim-mark-word').forEach(span => {
            const isCorrect = (span.getAttribute('data-correct') === 'true');
            const isSelected = span.classList.contains('selected');
            
            if (isCorrect) {
                totalCorrectWords++;
            }
            
            if (isSelected) {
                if (isCorrect) {
                    correctCount++;
                    span.classList.add('bg-emerald-500', 'border-emerald-600', 'text-white');
                    span.classList.remove('bg-brand-600');
                } else {
                    incorrectCount++;
                    span.classList.add('bg-rose-500', 'border-rose-600', 'text-white');
                    span.classList.remove('bg-brand-600');
                }
            } else {
                if (isCorrect) {
                    span.classList.add('border-dotted', 'border-emerald-500', 'text-emerald-700', 'font-black');
                }
            }
        });
        
        earnedPoints = Math.max(0, correctCount - incorrectCount);
        taskMax = totalCorrectWords || 1;
        correct = (earnedPoints === taskMax);

    } else { // Lückentext
        let cleanText = task.text;
        const correctAnswers = [];
        cleanText.replace(/\*([^*]+)\*/g, (match, word) => {
            let content = word;
            if (!content.trim() || ['*', '/', '+', '-', '=', '•'].includes(content.trim())) {
                return match;
            }
            if (content.includes(':')) {
                content = content.split(':', 1)[0];
            }
            const alts = content.split('/').map(s => s.trim().toLowerCase());
            correctAnswers.push(alts);
            return '';
        });
        
        let inputs = document.querySelectorAll('.sim-blank');
        inputs.forEach((input, i) => {
            const val = input.value.trim().toLowerCase();
            const alts = correctAnswers[i];
            const isCorrect = alts.includes(val);
            input.classList.add(isCorrect ? 'border-emerald-400' : 'border-rose-400');
            input.classList.add(isCorrect ? 'bg-emerald-50' : 'bg-rose-50');
            if (isCorrect) {
                earnedPoints++;
            }
            taskMax++;
        });
        correct = (earnedPoints === taskMax);
    }
    
    simState.score += earnedPoints;
    simState.maxScore += taskMax;
    simState.checkedCurrentTask = true;
    
    if (correct) {
        fbBox.textContent = getRandomSuccessPhrase();
        fbBox.classList.add('bg-emerald-50', 'text-emerald-700');
        triggerConfetti();
    } else {
        const explanationText = task.explanation ? ` 💬 Erklärung: ${task.explanation}` : "";
        fbBox.textContent = `${getRandomWrongPhrase()}${explanationText}`;
        fbBox.classList.add('bg-rose-50', 'text-rose-700');
    }
    fbBox.classList.remove('hidden');
    
    // Enable Proceed Button
    const nextBtn = document.getElementById('sim-btn-next');
    nextBtn.disabled = false;
    nextBtn.classList.remove('opacity-50', 'cursor-not-allowed');
    nextBtn.classList.add('bg-brand-600', 'text-white', 'hover:bg-brand-700');
    nextBtn.classList.remove('bg-slate-100', 'text-slate-700');
    
    // Disable Check Button
    const checkBtn = document.getElementById('sim-btn-check');
    checkBtn.disabled = true;
    checkBtn.classList.add('opacity-50', 'cursor-not-allowed');
    
    // Update Indicators
    simScoreIndicator.textContent = `Punkte: ${simState.score}/${simState.maxScore}`;
};

window.nextTask = function() {
    simState.taskIndex++;
    simState.checkedCurrentTask = false;
    
    if (simState.taskIndex < simState.tasks.length) {
        renderSimulator();
    } else {
        simState.currentStep = 'experts';
        renderSimulator();
    }
};

function restoreCheckedTaskState(task) {
    const nextBtn = document.getElementById('sim-btn-next');
    nextBtn.disabled = false;
    nextBtn.classList.remove('opacity-50', 'cursor-not-allowed');
    nextBtn.classList.add('bg-brand-600', 'text-white', 'hover:bg-brand-700');
    nextBtn.classList.remove('bg-slate-100', 'text-slate-700');
    
    const checkBtn = document.getElementById('sim-btn-check');
    checkBtn.disabled = true;
    checkBtn.classList.add('opacity-50', 'cursor-not-allowed');
}

// ----------------------------------------------------
// LOCAL HISTORY (INDEXEDDB) IMPLEMENTATION
// ----------------------------------------------------
const DB_NAME = 'AdaptiH5P_DB';
const DB_VERSION = 1;
const STORE_NAME = 'exercises';

function initDB() {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open(DB_NAME, DB_VERSION);
        request.onerror = () => reject(request.error);
        request.onsuccess = () => resolve(request.result);
        request.onupgradeneeded = (e) => {
            const db = e.target.result;
            if (!db.objectStoreNames.contains(STORE_NAME)) {
                db.createObjectStore(STORE_NAME, { keyPath: 'id', autoIncrement: true });
            }
        };
    });
}

function saveExerciseToHistory(exerciseData) {
    return initDB().then(db => {
        return new Promise((resolve, reject) => {
            const transaction = db.transaction([STORE_NAME], 'readwrite');
            const store = transaction.objectStore(STORE_NAME);
            
            const record = {
                title: exerciseData.title,
                target_format: exerciseData.target_format,
                timestamp: new Date().toISOString(),
                data: exerciseData
            };
            
            const request = store.add(record);
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    });
}

function getExerciseHistory() {
    return initDB().then(db => {
        return new Promise((resolve, reject) => {
            const transaction = db.transaction([STORE_NAME], 'readonly');
            const store = transaction.objectStore(STORE_NAME);
            const request = store.getAll();
            request.onsuccess = () => {
                const history = request.result.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
                resolve(history);
            };
            request.onerror = () => reject(request.error);
        });
    });
}

function deleteExerciseFromHistory(id) {
    return initDB().then(db => {
        return new Promise((resolve, reject) => {
            const transaction = db.transaction([STORE_NAME], 'readwrite');
            const store = transaction.objectStore(STORE_NAME);
            const request = store.delete(id);
            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    });
}

function renderHistoryList() {
    const listEl = document.getElementById('history-list');
    if (!listEl) return;
    
    getExerciseHistory().then(history => {
        if (history.length === 0) {
            listEl.innerHTML = `
                <div class="col-span-full py-12 px-4 border border-dashed border-slate-300/80 rounded-3xl text-center space-y-3 bg-white/40 glass-panel">
                    <div class="h-12 w-12 rounded-2xl bg-gradient-to-tr from-slate-100 to-slate-200/50 flex items-center justify-center mx-auto text-slate-400 border border-slate-200/60 shadow-inner">
                        <i class="fa-solid fa-box-archive text-lg"></i>
                    </div>
                    <div class="space-y-1">
                        <h5 class="text-xs font-extrabold text-slate-700">Dein Verlauf ist noch leer</h5>
                        <p class="text-[10px] text-slate-400 font-medium max-w-xs mx-auto leading-relaxed">
                            Erstelle deine erste Differenzierung oder lade ein Dokument hoch, um Aufgaben automatisch hier abzuspeichern.
                        </p>
                    </div>
                </div>
            `;
            return;
        }
        
        listEl.innerHTML = history.map(item => {
            const dateStr = new Date(item.timestamp).toLocaleDateString('de-DE', {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
            const iconMap = {
                "Lückentext": "fa-align-left text-blue-500",
                "Drag the Words": "fa-hand-pointer text-teal-500",
                "Wahr/Falsch": "fa-circle-check text-emerald-500",
                "Multiple Choice": "fa-list-check text-purple-500",
                "Vokabelkarten": "fa-clone text-orange-500",
                "KI-Mix": "fa-wand-magic-sparkles text-indigo-500"
            };
            const icon = iconMap[item.target_format] || "fa-file-lines text-slate-500";
            
            return `
                <div class="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm hover:shadow-md transition-all flex flex-col justify-between group">
                    <div class="space-y-2">
                        <div class="flex justify-between items-start">
                            <span class="inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-[9px] font-bold bg-slate-50 text-slate-600 border border-slate-200 uppercase tracking-wider">
                                <i class="fa-solid ${icon}"></i> ${item.target_format}
                            </span>
                            <button onclick="deleteHistoryItem(event, ${item.id})" class="text-slate-300 hover:text-red-500 transition-all opacity-0 group-hover:opacity-100 p-1">
                                <i class="fa-solid fa-trash text-[11px]"></i>
                            </button>
                        </div>
                        <h4 class="font-bold text-slate-800 text-xs line-clamp-2">${item.title}</h4>
                        <p class="text-[9px] font-bold text-slate-400"><i class="fa-regular fa-clock"></i> ${dateStr}</p>
                    </div>
                    <button onclick="loadHistoryItem(${item.id})" class="w-full mt-4 py-2 bg-slate-50 hover:bg-brand-50 hover:text-brand-700 text-slate-700 text-xxs font-bold rounded-xl border border-slate-200 hover:border-brand-200 transition-all flex items-center justify-center gap-1.5">
                        <i class="fa-solid fa-folder-open text-[10px]"></i> Öffnen
                    </button>
                </div>
            `;
        }).join('');
    }).catch(err => {
        console.error("Error rendering history list:", err);
    });
}

window.loadHistoryItem = function(id) {
    initDB().then(db => {
        const transaction = db.transaction([STORE_NAME], 'readonly');
        const store = transaction.objectStore(STORE_NAME);
        const request = store.get(id);
        request.onsuccess = () => {
            const item = request.result;
            if (item) {
                appState.generatedData = item.data;
                populateEditor(item.data);
                showScreen(screenEditor);
            }
        };
    });
};

window.deleteHistoryItem = function(event, id) {
    event.stopPropagation();
    if (!confirm("Möchtest du diese Übung wirklich aus dem Verlauf löschen?")) return;
    deleteExerciseFromHistory(id).then(() => {
        renderHistoryList();
    }).catch(err => {
        console.error("Error deleting history item:", err);
    });
};

// Initialize DB and load history
initDB().then(() => {
    renderHistoryList();
    initLivePreviewSync();
}).catch(err => {
    console.error("Failed to initialize IndexedDB:", err);
    initLivePreviewSync();
});

// ----------------------------------------------------
// CLASSROOM LIVE SESSION MANAGEMENT
// ----------------------------------------------------
let liveSessionInterval = null;
let liveSessionPin = '';

window.startLiveSession = async function() {
    const data = getEditedData();
    if (!data) return;
    
    // Append teacher branding configuration
    const teacherInput = document.getElementById('pdf-teacher-name');
    const classInput = document.getElementById('pdf-class-name');
    const logoInput = document.getElementById('pdf-logo-base64');
    
    data.teacher_name = teacherInput ? teacherInput.value : '';
    data.class_name = classInput ? classInput.value : '';
    data.logo_base64 = logoInput ? logoInput.value : '';
    
    const btn = document.getElementById('btn-start-live-session');
    btn.disabled = true;
    btn.innerHTML = `<i class="fa-solid fa-spinner animate-spin"></i> Erzeuge Sitzung...`;
    
    try {
        // 1. Create session in backend
        const sessionRes = await fetch(`${API_BASE}/api/sessions/create`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!sessionRes.ok) throw new Error("Could not create session");
        const sessionJson = await sessionRes.json();
        liveSessionPin = sessionJson.pin;
        
        // 2. Fetch network IP address
        const ipRes = await fetch(`${API_BASE}/api/system/ip`);
        const ipJson = await ipRes.json();
        const localIp = ipJson.ip;
        
        // 3. Build Student link
        const port = window.location.port ? `:${window.location.port}` : '';
        const playUrl = `${window.location.protocol}//${localIp}${port}/play.html?pin=${liveSessionPin}`;
        
        // 4. Update UI
        document.getElementById('live-session-pin').textContent = liveSessionPin;
        const pinTipEl = document.getElementById('live-session-pin-tip');
        if (pinTipEl) pinTipEl.textContent = liveSessionPin;
        document.getElementById('live-session-ip-label').textContent = localIp;
        document.getElementById('live-session-link').href = playUrl;
        document.getElementById('live-session-link').textContent = playUrl;
        
        document.getElementById('live-session-qrcode').src = `https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(playUrl)}`;
        
        document.getElementById('live-session-setup').classList.add('hidden');
        document.getElementById('live-session-active').classList.remove('hidden');
        
        // 5. Start Polling scoreboard
        pollLiveResults();
        liveSessionInterval = setInterval(pollLiveResults, 3000);
        updateNavigationState();
        
    } catch (err) {
        console.error("Failed to start live session:", err);
        alert("Fehler beim Starten der Live-Sitzung. Bitte überprüfe die Verbindung.");
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<i class="fa-solid fa-play"></i> Live-Sitzung starten (QR-Code generieren)`;
    }
};

window.stopLiveSession = function() {
    if (liveSessionInterval) {
        clearInterval(liveSessionInterval);
        liveSessionInterval = null;
    }
    document.getElementById('live-session-active').classList.add('hidden');
    document.getElementById('live-session-setup').classList.remove('hidden');
    
    document.getElementById('live-results-table-body').innerHTML = `
        <tr id="live-results-empty">
            <td colspan="4" class="px-3 py-6 text-center text-slate-400 font-semibold">
                Warten auf erste Abgaben...
            </td>
        </tr>
    `;
    document.getElementById('live-results-count').textContent = '0';
    updateNavigationState();
};

let lastLiveResults = [];

const ADJECTIVES = ["Schlaue", "Flinke", "Kreative", "Mutige", "Freundliche", "Wilde", "Starke", "Wissbegierige", "Geduldige", "Schnelle", "Aufgeweckte", "Fröhliche", "Fleißige", "Geschickte"];
const ANIMALS = ["Eule", "Eichhörnchen", "Biber", "Fuchs", "Katze", "Dachs", "Luchs", "Bär", "Koala", "Panda", "Affe", "Löwe", "Tiger", "Pinguin"];

function getAnonymizedName(name) {
    if (!name) return "Gast";
    let hash = 0;
    for (let i = 0; i < name.length; i++) {
        hash = name.charCodeAt(i) + ((hash << 5) - hash);
    }
    hash = Math.abs(hash);
    const adj = ADJECTIVES[hash % ADJECTIVES.length];
    const anim = ANIMALS[(hash >> 2) % ANIMALS.length];
    return `${adj} ${anim}`;
}

window.toggleAnonymizeNames = function() {
    renderScoreboardBody();
};

async function pollLiveResults() {
    if (!liveSessionPin) return;
    try {
        const response = await fetch(`${API_BASE}/api/sessions/${liveSessionPin}/results`);
        if (!response.ok) return;
        const resData = await response.json();
        lastLiveResults = resData.results || [];
        renderScoreboardBody();
        updateProjectorView();
    } catch (err) {
        console.error("Scoreboard polling failed:", err);
    }
}

function renderScoreboardBody() {
    const results = lastLiveResults;
    const countEl = document.getElementById('live-results-count');
    if (countEl) countEl.textContent = results.length;
    const tbody = document.getElementById('live-results-table-body');
    if (!tbody) return;
    
    if (results.length === 0) {
        tbody.innerHTML = `
            <tr id="live-results-empty">
                <td colspan="4" class="px-3 py-6 text-center text-slate-400 font-semibold">
                    Warten auf erste Abgaben...
                </td>
            </tr>
        `;
        return;
    }

    // Calculate Error Heatmap and Sentiment Distribution
    let wrongDiagCount = 0;
    let easyCount = 0, okCount = 0, hardCount = 0, totalFeedback = 0;

    results.forEach(r => {
        if (r.answers_detail) {
            r.answers_detail.forEach(a => {
                if (!a.correct) wrongDiagCount++;
            });
        }
        if (r.feedback) {
            totalFeedback++;
            if (r.feedback === 'leicht') easyCount++;
            else if (r.feedback === 'passend' || r.feedback === 'richtig') okCount++;
            else if (r.feedback === 'schwer') hardCount++;
        }
    });

    const heatmapAlert = document.getElementById('live-heatmap-alert');
    const heatmapText = document.getElementById('live-heatmap-text');
    const totalDetailItems = results.reduce((acc, r) => acc + (r.answers_detail ? r.answers_detail.length : 0), 0);
    const errorPercent = totalDetailItems > 0 ? Math.round((wrongDiagCount / totalDetailItems) * 100) : 0;
    
    if (heatmapAlert && heatmapText) {
        if (errorPercent >= 35) {
            heatmapAlert.classList.remove('hidden');
            heatmapText.textContent = `Achtung: ${errorPercent}% der Aufgaben wurden im ersten Versuch falsch beantwortet! Thema erfordert nochmalige Erklärung an der Tafel.`;
        } else {
            heatmapAlert.classList.add('hidden');
        }
    }

    const easyPercent = totalFeedback > 0 ? Math.round((easyCount / totalFeedback) * 100) : 60;
    const okPercent = totalFeedback > 0 ? Math.round((okCount / totalFeedback) * 100) : 30;
    const hardPercent = totalFeedback > 0 ? Math.round((hardCount / totalFeedback) * 100) : 10;

    if (document.getElementById('sentiment-easy')) document.getElementById('sentiment-easy').textContent = easyPercent;
    if (document.getElementById('sentiment-ok')) document.getElementById('sentiment-ok').textContent = okPercent;
    if (document.getElementById('sentiment-hard')) document.getElementById('sentiment-hard').textContent = hardPercent;

    // Classroom Team Goal progress calculation
    const teamGoalText = document.getElementById('live-team-goal-text');
    const teamGoalBar = document.getElementById('live-team-goal-bar');
    if (teamGoalText && teamGoalBar) {
        let totalScoreSum = results.reduce((sum, r) => sum + (r.score || 0), 0);
        let maxScoreSum = results.reduce((sum, r) => sum + (r.max_score || 1), 0);
        let teamPercent = maxScoreSum > 0 ? Math.min(100, Math.round((totalScoreSum / maxScoreSum) * 100)) : 0;
        teamGoalText.textContent = `${teamPercent}% gemeistert 🚀`;
        teamGoalBar.style.width = `${teamPercent}%`;
    }
    
    const anonymizeCheckbox = document.getElementById('toggle-anonymize');
    const isAnonymized = anonymizeCheckbox ? anonymizeCheckbox.checked : false;
    
    tbody.innerHTML = results.map((r, idx) => {
        const isB = (r.level_reached === 'B');
        const pathBadge = isB 
            ? `<span class="px-1.5 py-0.5 bg-indigo-50 border border-indigo-200 text-indigo-700 font-bold rounded-full">Level B</span>`
            : `<span class="px-1.5 py-0.5 bg-teal-50 border border-teal-200 text-teal-700 font-bold rounded-full">Level A</span>`;
            
        const displayName = isAnonymized ? getAnonymizedName(r.student_name) : r.student_name;
        
        return `
            <tr onclick="toggleStudentDetails(${idx})" class="border-b border-slate-100 hover:bg-slate-50 font-medium cursor-pointer transition-all">
                <td class="px-3 py-2.5 font-bold text-slate-800 flex items-center gap-1.5">
                    <i class="fa-solid fa-chevron-right text-[8px] text-slate-400 transition-transform duration-200" id="chevron-${idx}"></i>
                    <span>${displayName}</span>
                </td>
                <td class="px-3 py-2.5">${pathBadge}</td>
                <td class="px-3 py-2.5 text-right font-black text-brand-600">${r.score} <span class="text-slate-400">/ ${r.max_score}</span></td>
                <td class="px-3 py-2.5 text-right text-[10px] text-slate-400 font-bold">${r.timestamp}</td>
            </tr>
            <tr id="details-${idx}" class="hidden bg-slate-50/50">
                <td colspan="4" class="px-4 py-3 border-b border-slate-200/50 text-[10px] text-slate-600">
                    <div class="space-y-1.5 font-semibold">
                        <!-- Header -->
                        <div class="flex justify-between items-center text-[8px] font-bold text-slate-400 uppercase tracking-wider pb-1 border-b border-slate-100 mb-1">
                            <span>Aufgabe / Frage</span>
                            <span>Ergebnis</span>
                        </div>
                        ${r.answers_detail && r.answers_detail.length > 0 ? r.answers_detail.map(a => {
                            const icon = a.correct ? 'fa-circle-check text-emerald-500' : 'fa-circle-xmark text-rose-500';
                            return `
                                <div class="flex justify-between items-center py-1 border-b border-slate-100/50 last:border-0">
                                    <span class="truncate max-w-[220px] text-slate-700"><i class="fa-solid ${icon} mr-1"></i> ${a.title}</span>
                                    <span class="font-bold ${a.correct ? 'text-emerald-700' : 'text-rose-600'}">${a.points}/${a.max_points}</span>
                                </div>
                            `;
                        }).join('') : `
                            <div class="text-center text-slate-400 py-2">Keine detaillierten Ergebnisse vorhanden</div>
                        `}
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

window.toggleStudentDetails = function(idx) {
    const detailsRow = document.getElementById(`details-${idx}`);
    const chevron = document.getElementById(`chevron-${idx}`);
    if (detailsRow && chevron) {
        const isHidden = detailsRow.classList.contains('hidden');
        if (isHidden) {
            detailsRow.classList.remove('hidden');
            chevron.classList.add('rotate-90');
        } else {
            detailsRow.classList.add('hidden');
            chevron.classList.remove('rotate-90');
        }
    }
};

window.downloadResultsCSV = function() {
    if (!lastLiveResults || lastLiveResults.length === 0) {
        alert("Keine Ergebnisse zum Herunterladen vorhanden.");
        return;
    }
    
    // Header line
    let csvContent = "\uFEFF"; // UTF-8 BOM to ensure proper character rendering in Excel
    csvContent += "Name;Anonymisierter Name;Zugeordnetes Level;Erreichte Punkte;Maximalpunkte;Abgabezeit;Detailierte Ergebnisse\r\n";
    
    lastLiveResults.forEach(r => {
        const anonName = getAnonymizedName(r.student_name);
        const level = r.level_reached;
        const score = r.score;
        const maxScore = r.max_score;
        const time = r.timestamp || "";
        
        let details = "";
        if (r.answers_detail && r.answers_detail.length > 0) {
            details = r.answers_detail.map(a => `${a.title}: ${a.points}/${a.max_points} (${a.correct ? 'Richtig' : 'Falsch'})`).join(" | ");
        } else {
            details = "Keine Detail-Daten";
        }
        
        const cleanName = r.student_name.replace(/;/g, ",").replace(/"/g, '""');
        const cleanAnonName = anonName.replace(/;/g, ",").replace(/"/g, '""');
        const cleanDetails = details.replace(/;/g, ",").replace(/"/g, '""');
        
        csvContent += `"${cleanName}";"${cleanAnonName}";"Level ${level}";${score};${maxScore};"${time}";"${cleanDetails}"\r\n`;
    });
    
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const encodedUrl = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUrl);
    link.setAttribute("download", `Adaptify_Ergebnisse_${liveSessionPin || 'Sitzung'}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
};

const SUCCESS_PHRASES = [
    "Klasse! Das ist vollkommen richtig! 🎉",
    "Großartig gemacht! Weiter so! ✨",
    "Spitzenklasse! Genau richtig! 🚀",
    "Super! Du hast es verstanden! 🌟",
    "Perfekt gelöst! Fantastisch! 🏆"
];

const WRONG_PHRASES = [
    "Knapp daneben! Probier es noch einmal. 💪",
    "Nicht aufgeben! Jeder Fehler bringt dich weiter. 🧩",
    "Guter Versuch! Schau es dir noch mal an. 🔍",
    "Da war ein kleiner Dreher drin. Versuch's noch mal! 🧠"
];

function getRandomSuccessPhrase() {
    return SUCCESS_PHRASES[Math.floor(Math.random() * SUCCESS_PHRASES.length)];
}

function getRandomWrongPhrase() {
    return WRONG_PHRASES[Math.floor(Math.random() * WRONG_PHRASES.length)];
}

function triggerConfetti() {
    let canvas = document.getElementById('confetti-canvas');
    if (!canvas) {
        canvas = document.createElement('canvas');
        canvas.id = 'confetti-canvas';
        canvas.className = 'pointer-events-none fixed inset-0 z-[100] w-full h-full';
        document.body.appendChild(canvas);
    }
    
    const ctx = canvas.getContext('2d');
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    
    let particles = [];
    const colors = ['#a855f7', '#8b5cf6', '#3b82f6', '#14b8a6', '#10b981', '#f59e0b', '#ef4444'];
    
    for (let i = 0; i < 100; i++) {
        particles.push({
            x: Math.random() * canvas.width,
            y: canvas.height + 20,
            vx: (Math.random() - 0.5) * 8,
            vy: -Math.random() * 14 - 10,
            color: colors[Math.floor(Math.random() * colors.length)],
            size: Math.random() * 6 + 4,
            rotation: Math.random() * 360,
            rotationSpeed: (Math.random() - 0.5) * 12
        });
    }
    
    function update() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        let active = false;
        
        particles.forEach(p => {
            p.x += p.vx;
            p.y += p.vy;
            p.vy += 0.35; // Gravity
            p.rotation += p.rotationSpeed;
            
            if (p.y < canvas.height + 20 && p.x > -20 && p.x < canvas.width + 20) {
                active = true;
                ctx.save();
                ctx.translate(p.x, p.y);
                ctx.rotate((p.rotation * Math.PI) / 180);
                ctx.fillStyle = p.color;
                ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size);
                ctx.restore();
            }
        });
        
        if (active) {
            requestAnimationFrame(update);
        } else {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
        }
    }
    
    requestAnimationFrame(update);
}

window.toggleUserProfileDropdown = function(event) {
    if (event) event.stopPropagation();
    const panel = document.getElementById('user-dropdown-panel');
    if (panel) panel.classList.toggle('hidden');
};

document.addEventListener('click', (e) => {
    const dropdown = document.getElementById('user-dropdown-panel');
    const profileMenu = document.getElementById('user-profile-menu');
    if (dropdown && profileMenu && !profileMenu.contains(e.target)) {
        dropdown.classList.add('hidden');
    }
});

window.openBrandingSettingsModal = function(event) {
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }
    const modal = document.getElementById('branding-settings-modal');
    if (modal) {
        // Sync values from existing hidden/PDF settings input
        const teacherInput = document.getElementById('pdf-teacher-name');
        const classInput = document.getElementById('pdf-class-name');
        
        document.getElementById('branding-teacher-name').value = teacherInput ? teacherInput.value : '';
        document.getElementById('branding-class-name').value = classInput ? classInput.value : '';
        
        modal.classList.remove('hidden');
    }
};

window.closeBrandingSettingsModal = function(event) {
    if (event) event.stopPropagation();
    const modal = document.getElementById('branding-settings-modal');
    if (modal) modal.classList.add('hidden');
};

window.syncBrandingInputs = function() {
    const bTeacher = document.getElementById('branding-teacher-name').value;
    const bClass = document.getElementById('branding-class-name').value;
    
    // Write back to PDF generation inputs
    const teacherInput = document.getElementById('pdf-teacher-name');
    const classInput = document.getElementById('pdf-class-name');
    
    if (teacherInput) teacherInput.value = bTeacher;
    if (classInput) classInput.value = bClass;
};

window.handleBrandingLogoUpload = function(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = function(e) {
        const base64 = e.target.result;
        
        // Sync to PDF logo input
        const pdfLogoInput = document.getElementById('pdf-logo-base64');
        if (pdfLogoInput) pdfLogoInput.value = base64;
        
        // Update Preview inside settings modal
        const previewImg = document.getElementById('branding-logo-preview');
        const previewContainer = document.getElementById('branding-logo-preview-container');
        if (previewImg && previewContainer) {
            previewImg.src = base64;
            previewContainer.classList.remove('hidden');
            previewContainer.classList.add('flex');
        }
    };
    reader.readAsDataURL(file);
};

window.removeBrandingLogo = function(event) {
    if (event) event.stopPropagation();
    
    const pdfLogoInput = document.getElementById('pdf-logo-base64');
    if (pdfLogoInput) pdfLogoInput.value = '';
    
    const previewContainer = document.getElementById('branding-logo-preview-container');
    if (previewContainer) previewContainer.classList.add('hidden');
    
    const fileInput = document.getElementById('branding-school-logo');
    if (fileInput) fileInput.value = '';
};

let lastAnalyticsData = [];

window.loadAnalyticsData = async function() {
    const listContainer = document.getElementById('analytics-student-list');
    if (!listContainer) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/teacher/analytics`);
        if (!response.ok) throw new Error("Could not load analytics");
        const students = await response.json();
        lastAnalyticsData = students;
        
        if (students.length === 0) {
            listContainer.innerHTML = `
                <div class="text-center text-slate-400 py-8 text-xxs font-semibold">
                    <i class="fa-solid fa-users text-2xl text-slate-300 mb-2 block"></i>
                    Noch keine Abgaben verzeichnet.
                </div>
            `;
            // Reset detail panel
            document.getElementById('analytics-detail-empty').classList.remove('hidden');
            document.getElementById('analytics-detail-dashboard').classList.add('hidden');
            return;
        }
        
        listContainer.innerHTML = students.map((s, idx) => {
            const avgPct = Math.round((s.total_score / s.total_max_score) * 100) || 0;
            return `
                <div onclick="selectStudentAnalytics(${idx})" class="p-3 bg-slate-50 border border-slate-100 rounded-2xl hover:bg-slate-100/50 hover:border-slate-200 cursor-pointer transition-all flex justify-between items-center" id="student-card-${idx}">
                    <div>
                        <h4 class="font-bold text-slate-800 text-[11px]">${s.student_name}</h4>
                        <p class="text-[9px] text-slate-400 font-bold mt-0.5">${s.completed_count} ${s.completed_count === 1 ? 'Übung' : 'Übungen'}</p>
                    </div>
                    <div class="text-right">
                        <span class="block text-[11px] font-black text-brand-600">${avgPct}%</span>
                        <span class="text-[7px] font-bold text-slate-400 uppercase">Schnitt</span>
                    </div>
                </div>
            `;
        }).join('');
        
    } catch (err) {
        console.error("Failed to fetch analytics:", err);
        listContainer.innerHTML = `
            <div class="text-center text-rose-500 py-6 text-xxs font-semibold">
                <i class="fa-solid fa-circle-exclamation text-xl mb-1 block"></i>
                Fehler beim Laden.
            </div>
        `;
    }
};

window.selectStudentAnalytics = function(idx) {
    const s = lastAnalyticsData[idx];
    if (!s) return;
    
    // Highlight selected card
    lastAnalyticsData.forEach((_, i) => {
        const card = document.getElementById(`student-card-${i}`);
        if (card) {
            card.classList.toggle('border-brand-500', i === idx);
            card.classList.toggle('bg-brand-50/20', i === idx);
        }
    });
    
    // Show dashboard pane
    document.getElementById('analytics-detail-empty').classList.add('hidden');
    const dashboard = document.getElementById('analytics-detail-dashboard');
    dashboard.classList.remove('hidden');
    
    // Populate header metrics
    document.getElementById('analytics-student-name').textContent = s.student_name;
    document.getElementById('analytics-stat-completed').textContent = s.completed_count;
    
    const avgPct = Math.round((s.total_score / s.total_max_score) * 100) || 0;
    document.getElementById('analytics-stat-avg-score').textContent = `${avgPct}%`;
    
    // Level ratio & distribution
    const levelA = s.levels.filter(l => l === 'A').length;
    const levelB = s.levels.filter(l => l === 'B').length;
    document.getElementById('analytics-level-a-count').textContent = levelA;
    document.getElementById('analytics-level-b-count').textContent = levelB;
    document.getElementById('analytics-level-ratio').textContent = `${levelA} / ${levelB}`;
    
    // Trend & Form
    const trendProgress = document.getElementById('analytics-trend-progress-bar');
    const trendBadge = document.getElementById('analytics-trend-badge');
    if (trendProgress && trendBadge) {
        trendProgress.style.width = `${avgPct}%`;
        
        let label = "Ausbaufähig";
        let colorClass = ["bg-rose-50", "text-rose-700", "border-rose-200"];
        if (avgPct >= 85) {
            label = "Hervorragend";
            colorClass = ["bg-emerald-50", "text-emerald-700", "border-emerald-200"];
        } else if (avgPct >= 70) {
            label = "Gut";
            colorClass = ["bg-teal-50", "text-teal-700", "border-teal-200"];
        } else if (avgPct >= 50) {
            label = "Befriedigend";
            colorClass = ["bg-amber-50", "text-amber-700", "border-amber-200"];
        }
        
        trendBadge.className = `px-2 py-0.5 rounded-full font-bold border text-xxs ${colorClass.join(' ')}`;
        trendBadge.textContent = label;
    }
    
    // Render timeline list
    const tbody = document.getElementById('analytics-history-tbody');
    if (tbody) {
        tbody.innerHTML = s.history.map((h, hIdx) => {
            const isB = (h.level_reached === 'B');
            const pathBadge = isB 
                ? `<span class="px-1.5 py-0.5 bg-indigo-50 border border-indigo-200 text-indigo-700 font-bold rounded-full text-[8px]">Level B</span>`
                : `<span class="px-1.5 py-0.5 bg-teal-50 border border-teal-200 text-teal-700 font-bold rounded-full text-[8px]">Level A</span>`;
            
            return `
                <tr class="border-b border-slate-100 hover:bg-slate-50 transition-all cursor-pointer font-medium" onclick="toggleAnalyticsHistoryDetails(${hIdx})">
                    <td class="px-4 py-2.5 font-bold text-slate-800 flex items-center gap-1.5">
                        <i class="fa-solid fa-chevron-right text-[7px] text-slate-400 transition-transform duration-200" id="hist-chevron-${hIdx}"></i>
                        <span>${h.title} <span class="text-slate-400 font-normal">(${h.pin})</span></span>
                    </td>
                    <td class="px-4 py-2.5">${pathBadge}</td>
                    <td class="px-4 py-2.5 text-right font-black text-brand-600">${h.score} <span class="text-slate-400">/ ${h.max_score}</span></td>
                    <td class="px-4 py-2.5 text-right text-[10px] text-slate-400 font-bold">${h.timestamp}</td>
                </tr>
                <tr id="hist-details-${hIdx}" class="hidden bg-slate-50/50">
                    <td colspan="4" class="px-5 py-3 border-b border-slate-200/50 text-[10px] text-slate-600">
                        <div class="space-y-1.5 font-semibold">
                            <!-- Header -->
                            <div class="flex justify-between items-center text-[8px] font-bold text-slate-400 uppercase tracking-wider pb-1 border-b border-slate-100 mb-1">
                                <span>Aufgabe / Frage</span>
                                <span>Ergebnis</span>
                            </div>
                            ${h.answers_detail && h.answers_detail.length > 0 ? h.answers_detail.map(a => {
                                const icon = a.correct ? 'fa-circle-check text-emerald-500' : 'fa-circle-xmark text-rose-500';
                                return `
                                    <div class="flex justify-between items-center py-1 border-b border-slate-100/50 last:border-0">
                                        <span class="truncate max-w-[300px] text-slate-700"><i class="fa-solid ${icon} mr-1"></i> ${a.title}</span>
                                        <span class="font-bold ${a.correct ? 'text-emerald-700' : 'text-rose-600'}">${a.points}/${a.max_points}</span>
                                    </div>
                                `;
                            }).join('') : `
                                <div class="text-center text-slate-400 py-2">Keine detaillierten Ergebnisse vorhanden</div>
                            `}
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
    }
};

window.toggleAnalyticsHistoryDetails = function(hIdx) {
    const detailsRow = document.getElementById(`hist-details-${hIdx}`);
    const chevron = document.getElementById(`hist-chevron-${hIdx}`);
    if (detailsRow && chevron) {
        const isHidden = detailsRow.classList.contains('hidden');
        if (isHidden) {
            detailsRow.classList.remove('hidden');
            chevron.classList.add('rotate-90');
        } else {
            detailsRow.classList.add('hidden');
            chevron.classList.remove('rotate-90');
        }
    }
};

let currentProjView = 'track'; // 'track', 'class', 'leader'

window.openProjectorView = function(event) {
    if (event) event.stopPropagation();
    const modal = document.getElementById('projector-view-modal');
    if (!modal) return;
    
    // Set PIN and IP
    document.getElementById('proj-pin').textContent = liveSessionPin || 'CODE';
    
    const ipLabel = document.getElementById('live-session-ip-label');
    document.getElementById('proj-ip').textContent = ipLabel ? ipLabel.textContent : '127.0.0.1';
    
    modal.classList.remove('hidden');
    updateProjectorView();
};

window.closeProjectorView = function() {
    const modal = document.getElementById('projector-view-modal');
    if (modal) modal.classList.add('hidden');
};

window.switchProjView = function(viewName) {
    currentProjView = viewName;
    
    // Update active button state
    const btnTrack = document.getElementById('proj-btn-track');
    const btnClass = document.getElementById('proj-btn-class');
    const btnLeader = document.getElementById('proj-btn-leader');
    
    if (btnTrack) {
        btnTrack.className = `px-3 py-1.5 rounded-lg transition-all ${viewName === 'track' ? 'bg-slate-800 text-white' : 'text-slate-400 hover:text-slate-200'}`;
    }
    if (btnClass) {
        btnClass.className = `px-3 py-1.5 rounded-lg transition-all ${viewName === 'class' ? 'bg-slate-800 text-white' : 'text-slate-400 hover:text-slate-200'}`;
    }
    if (btnLeader) {
        btnLeader.className = `px-3 py-1.5 rounded-lg transition-all ${viewName === 'leader' ? 'bg-slate-800 text-white' : 'text-slate-400 hover:text-slate-200'}`;
    }
    
    // Toggle containers
    document.getElementById('proj-view-track').classList.toggle('hidden', viewName !== 'track');
    document.getElementById('proj-view-class').classList.toggle('hidden', viewName !== 'class');
    document.getElementById('proj-view-leader').classList.toggle('hidden', viewName !== 'leader');
    
    updateProjectorView();
};

window.updateProjectorView = function() {
    const modal = document.getElementById('projector-view-modal');
    if (!modal || modal.classList.contains('hidden')) return;
    
    const results = lastLiveResults;
    
    // 1. UPDATE TRACK VIEW (LERN-RENNBAHN)
    const trackContainer = document.getElementById('proj-track-container');
    if (trackContainer) {
        if (results.length === 0) {
            trackContainer.innerHTML = `
                <div class="text-center text-slate-500 py-12 text-xxs font-semibold">
                    <i class="fa-solid fa-car-side text-3xl text-slate-700 animate-pulse mb-3 block"></i>
                    Warten auf den Start der ersten Schüler...
                </div>
            `;
        } else {
            trackContainer.innerHTML = results.map(r => {
                const anonName = getAnonymizedName(r.student_name);
                const scorePercent = Math.round((r.score / r.max_score) * 100) || 0;
                
                // Get deterministic animal icon class
                let hash = 0;
                for (let i = 0; i < r.student_name.length; i++) {
                    hash = r.student_name.charCodeAt(i) + ((hash << 5) - hash);
                }
                hash = Math.abs(hash);
                const iconClasses = [
                    "fa-crow text-amber-400", "fa-otter text-teal-400", "fa-dove text-sky-400", 
                    "fa-spider text-rose-400", "fa-frog text-emerald-400", "fa-hippo text-indigo-400",
                    "fa-fish text-blue-400", "fa-dragon text-purple-400"
                ];
                const icon = iconClasses[hash % iconClasses.length];
                
                const levelColor = r.level_reached === 'B' ? 'border-indigo-500 text-indigo-400' : 'border-teal-500 text-teal-400';
                
                return `
                    <div class="py-3 flex items-center gap-4 relative">
                        <!-- Track grid background lines -->
                        <div class="absolute inset-0 flex justify-between pointer-events-none opacity-10">
                            <div class="border-l border-slate-700 h-full w-px"></div>
                            <div class="border-l border-slate-700 h-full w-px"></div>
                            <div class="border-l border-slate-700 h-full w-px"></div>
                            <div class="border-l border-slate-700 h-full w-px"></div>
                        </div>
                        
                        <!-- Student Avatar/Label -->
                        <div class="w-32 truncate shrink-0">
                            <span class="text-xxs font-black text-slate-300 block text-left">${anonName}</span>
                            <span class="px-1 py-0.5 rounded text-[7px] font-bold border ${levelColor} uppercase tracking-wider mt-0.5 inline-block">Level ${r.level_reached}</span>
                        </div>
                        
                        <!-- Track Line & Running Animal -->
                        <div class="flex-1 h-3 bg-slate-950 rounded-full border border-slate-800 relative flex items-center shadow-inner">
                            <!-- Progress Bar track trail -->
                            <div class="h-full bg-slate-800/80 rounded-full transition-all duration-500" style="width: ${scorePercent}%"></div>
                            
                            <!-- Animal indicator moving along the track -->
                            <div class="absolute -top-2.5 transition-all duration-500 flex flex-col items-center" style="left: calc(${scorePercent}% - 8px)">
                                <i class="fa-solid ${icon} text-sm filter drop-shadow-[0_0_8px_rgba(255,255,255,0.4)] animate-bounce"></i>
                            </div>
                        </div>
                        
                        <!-- Score Indicator -->
                        <div class="w-16 text-right shrink-0">
                            <span class="text-xxs font-black text-emerald-400">${r.score}</span>
                            <span class="text-[9px] text-slate-500">/ ${r.max_score}</span>
                        </div>
                    </div>
                `;
            }).join('');
        }
    }
    
    // 2. UPDATE COOPERATIVE GOAL (KLASSENZIEL)
    const classCurrent = document.getElementById('proj-class-current');
    const classProgress = document.getElementById('proj-class-progress-bar');
    const classTarget = document.getElementById('proj-class-target');
    const classTargetLabel = document.getElementById('proj-class-target-label');
    
    if (classCurrent && classProgress && classTarget && classTargetLabel) {
        // Calculate classroom sum
        const totalPoints = results.reduce((acc, curr) => acc + curr.score, 0);
        
        // Dynamic target: default 50 points or 12 points per active student
        const activeCount = Math.max(results.length, 1);
        const dynamicTarget = activeCount * 12;
        
        classTarget.textContent = dynamicTarget;
        classTargetLabel.textContent = dynamicTarget;
        classCurrent.textContent = totalPoints;
        
        const targetPercent = Math.min(Math.round((totalPoints / dynamicTarget) * 100), 100);
        classProgress.style.width = `${targetPercent}%`;
    }
    
    // 3. UPDATE LEADERBOARD TABLE
    const leaderTbody = document.getElementById('proj-leaderboard-tbody');
    if (leaderTbody) {
        if (results.length === 0) {
            leaderTbody.innerHTML = `
                <tr>
                    <td colspan="4" class="px-4 py-8 text-center text-slate-500 font-semibold">
                        Noch keine Abgaben eingegangen.
                    </td>
                </tr>
            `;
        } else {
            // Sort by score descending
            const sortedResults = [...results].sort((a, b) => b.score - a.score);
            
            leaderTbody.innerHTML = sortedResults.map((r, rankIdx) => {
                const anonName = getAnonymizedName(r.student_name);
                const pathBadge = r.level_reached === 'B' 
                    ? `<span class="px-1.5 py-0.5 bg-indigo-950/80 border border-indigo-800 text-indigo-300 font-bold rounded-full text-[8px]">Level B</span>`
                    : `<span class="px-1.5 py-0.5 bg-teal-950/80 border border-teal-800 text-teal-300 font-bold rounded-full text-[8px]">Level A</span>`;
                
                let medal = `${rankIdx + 1}.`;
                if (rankIdx === 0) medal = '🥇';
                else if (rankIdx === 1) medal = '🥈';
                else if (rankIdx === 2) medal = '🥉';
                
                return `
                    <tr class="border-b border-slate-900 hover:bg-slate-900/30 transition-all font-medium text-slate-300">
                        <td class="px-4 py-3 font-bold flex items-center gap-2">
                            <span class="w-5 text-center text-xs font-black">${medal}</span>
                            <span>${anonName}</span>
                        </td>
                        <td class="px-4 py-3">${pathBadge}</td>
                        <td class="px-4 py-3 text-right font-black text-emerald-400">${r.score} <span class="text-slate-600">/ ${r.max_score}</span></td>
                        <td class="px-4 py-3 text-right text-[10px] text-slate-500 font-bold">${r.timestamp}</td>
                    </tr>
                `;
            }).join('');
        }
    }
};

// ----------------------------------------------------
// LEGAL MODALS (DATENSCHUTZ & IMPRESSUM)
// ----------------------------------------------------
window.openPrivacyModal = function(event) {
    if (event) event.preventDefault();
    const modal = document.getElementById('privacy-modal');
    if (modal) modal.classList.remove('hidden');
};

window.closePrivacyModal = function(event) {
    if (event) event.preventDefault();
    const modal = document.getElementById('privacy-modal');
    if (modal) modal.classList.add('hidden');
};

window.openImprintModal = function(event) {
    if (event) event.preventDefault();
    const modal = document.getElementById('imprint-modal');
    if (modal) modal.classList.remove('hidden');
};

window.closeImprintModal = function(event) {
    if (event) event.preventDefault();
    const modal = document.getElementById('imprint-modal');
    if (modal) modal.classList.add('hidden');
};

// ----------------------------------------------------
// PWA STANDALONE APP INSTALLATION
// ----------------------------------------------------
let deferredInstallPrompt = null;
window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredInstallPrompt = e;
    const btn = document.getElementById('btn-install-app');
    if (btn) {
        btn.classList.remove('hidden');
        btn.classList.add('flex');
    }
});

window.promptInstallApp = async function() {
    if (deferredInstallPrompt) {
        deferredInstallPrompt.prompt();
        const { outcome } = await deferredInstallPrompt.userChoice;
        if (outcome === 'accepted') {
            const btn = document.getElementById('btn-install-app');
            if (btn) btn.classList.add('hidden');
        }
        deferredInstallPrompt = null;
    } else {
        alert("📲 So installierst du Adaptify als App auf deinem iPad/Tablet/PC:\n\n1. Auf iPads: Tippe in Safari auf das Teilen-Symbol ⬆️ und wähle 'Zum Home-Bildschirm' ➕.\n2. In Chrome/Edge: Klicke in der Adressleiste auf das App-Installieren-Symbol.");
    }
};


