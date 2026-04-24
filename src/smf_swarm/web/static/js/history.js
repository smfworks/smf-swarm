/** SMF Predict — Run History, Settings, and Compare */

(function() {
    const STORAGE_KEY = "smf_swarm_history";
    const SETTINGS_KEY = "smf_swarm_settings";
    const MAX_HISTORY = 100;

    // ─── Default Settings ────────────────────────────
    const DEFAULTS = {
        social_agents: 15,
        social_rounds: 4,
        temperature: 0.3,
        multi_sample: 1,
        cache_enabled: true,
        auto_history: true,
        persona_template: "",
    };

    let settings = { ...DEFAULTS };
    loadSettings();

    // ─── Settings Modal ─────────────────────────────
    const settingsModal = document.getElementById("settingsModal");
    const settingsBtn = document.getElementById("settingsBtn");
    const settingsClose = document.getElementById("settingsClose");
    const settingsSave = document.getElementById("settingsSave");
    const settingsReset = document.getElementById("settingsReset");

    settingsBtn.addEventListener("click", () => {
        populateSettings();
        settingsModal.classList.remove("hidden");
    });
    settingsClose.addEventListener("click", () => settingsModal.classList.add("hidden"));
    settingsModal.addEventListener("click", (e) => { if (e.target === settingsModal) settingsModal.classList.add("hidden"); });

    ["sliderAgents", "sliderRounds", "sliderTemp", "sliderMulti"].forEach(id => {
        const el = document.getElementById(id);
        const valEl = document.getElementById(id.replace("slider", "val"));
        if (!el) return;
        const fmt = id === "sliderTemp" ? (v) => parseFloat(v).toFixed(2) : (v) => v;
        el.addEventListener("input", () => { valEl.textContent = fmt(el.value); });
    });

    settingsSave.addEventListener("click", () => {
        settings.social_agents = parseInt(document.getElementById("sliderAgents").value, 10);
        settings.social_rounds = parseInt(document.getElementById("sliderRounds").value, 10);
        settings.temperature = parseFloat(document.getElementById("sliderTemp").value);
        settings.multi_sample = parseInt(document.getElementById("sliderMulti").value, 10);
        settings.cache_enabled = document.getElementById("toggleCache").checked;
        settings.auto_history = document.getElementById("toggleAutoHistory").checked;
        settings.persona_template = document.getElementById("personaTemplate").value.trim();
        saveSettings();
        settingsModal.classList.add("hidden");
    });

    settingsReset.addEventListener("click", () => {
        settings = { ...DEFAULTS };
        populateSettings();
        saveSettings();
    });

    function populateSettings() {
        document.getElementById("sliderAgents").value = settings.social_agents;
        document.getElementById("valAgents").textContent = settings.social_agents;
        document.getElementById("sliderRounds").value = settings.social_rounds;
        document.getElementById("valRounds").textContent = settings.social_rounds;
        document.getElementById("sliderTemp").value = settings.temperature;
        document.getElementById("valTemp").textContent = settings.temperature.toFixed(2);
        document.getElementById("sliderMulti").value = settings.multi_sample;
        document.getElementById("valMulti").textContent = settings.multi_sample;
        document.getElementById("toggleCache").checked = settings.cache_enabled;
        document.getElementById("toggleAutoHistory").checked = settings.auto_history;
        document.getElementById("personaTemplate").value = settings.persona_template;
    }

    function loadSettings() {
        try {
            const raw = localStorage.getItem(SETTINGS_KEY);
            if (raw) Object.assign(settings, JSON.parse(raw));
        } catch (e) { /* ignore */ }
    }
    function saveSettings() {
        localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
    }

    // ─── History ────────────────────────────────────
    const historyModal = document.getElementById("historyModal");
    const historyBtn = document.getElementById("historyBtn");
    const historyClose = document.getElementById("historyClose");
    const historyList = document.getElementById("historyList");
    const historySearch = document.getElementById("historySearch");
    const historyFilterDomain = document.getElementById("historyFilterDomain");
    const historyFilterMode = document.getElementById("historyFilterMode");
    const historyCompareBtn = document.getElementById("historyCompareBtn");
    const historyClearBtn = document.getElementById("historyClearBtn");

    let selectedForCompare = new Set();

    historyBtn.addEventListener("click", () => { historyModal.classList.remove("hidden"); renderHistory(); });
    historyClose.addEventListener("click", () => historyModal.classList.add("hidden"));
    historyModal.addEventListener("click", (e) => { if (e.target === historyModal) historyModal.classList.add("hidden"); });

    [historySearch, historyFilterDomain, historyFilterMode].forEach(el => {
        el.addEventListener("input", renderHistory);
    });

    historyClearBtn.addEventListener("click", () => {
        if (confirm("Clear all run history?")) {
            localStorage.removeItem(STORAGE_KEY);
            selectedForCompare.clear();
            renderHistory();
        }
    });

    historyCompareBtn.addEventListener("click", () => {
        const ids = Array.from(selectedForCompare);
        if (ids.length !== 2) {
            alert("Select exactly 2 runs to compare.");
            return;
        }
        openCompare(ids[0], ids[1]);
    });

    function loadHistory() {
        try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]"); }
        catch (e) { return []; }
    }

    window.saveToHistory = function(res) {
        if (!settings.auto_history) return;
        const entries = loadHistory();
        entries.unshift({
            id: `${Date.now()}-${Math.random().toString(36).slice(2,6)}`,
            query: res.query || "",
            mode: res.mode || "debate",
            domain: res.domain || "general",
            confidence: res.confidence ?? 0,
            data_quality: res.data_quality ?? 0,
            duration_s: res.duration_s ?? 0,
            summary: res.summary || "",
            risk: res.risk || "",
            dissent: res.dissent || "",
            social_modifier: res.social_modifier ?? null,
            health_score: res.health_score ?? 0,
            sentiment_trajectory: res.sentiment_trajectory || null,
            multi_sample: res.multi_sample || null,
            timestamp: res.timestamp || new Date().toISOString(),
        });
        while (entries.length > MAX_HISTORY) entries.pop();
        localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
    };

    function renderHistory() {
        const entries = loadHistory();
        const term = (historySearch.value || "").toLowerCase();
        const domain = historyFilterDomain.value;
        const mode = historyFilterMode.value;

        const filtered = entries.filter(e => {
            if (term && !(e.query || "").toLowerCase().includes(term)) return false;
            if (domain && e.domain !== domain) return false;
            if (mode && e.mode !== mode) return false;
            return true;
        });

        if (filtered.length === 0) {
            historyList.innerHTML = `<div class="history-empty">No runs yet. Run a prediction to build history.</div>`;
            return;
        }

        historyList.innerHTML = filtered.map(e => `<div class="history-item" data-id="${e.id}">
            <div class="history-main">
                <input type="checkbox" class="history-check" data-id="${e.id}" ${selectedForCompare.has(e.id) ? "checked" : ""}>
                <span class="history-query">${escapeHtml((e.query || "").slice(0, 80))}${e.query && e.query.length > 80 ? "…" : ""}</span>
                <span class="history-badge mode-${e.mode}">${e.mode}</span>
                <span class="history-badge domain-${e.domain}">${e.domain}</span>
            </div>
            <div class="history-meta">
                <span>${formatDate(e.timestamp)}</span>
                <span class="history-conf">Conf: ${(e.confidence ?? 0).toFixed(2)}</span>
                <span>${(e.duration_s ?? 0).toFixed(0)}s</span>
                <button class="history-load">Load</button>
            </div>
        </div>`).join("");

        historyList.querySelectorAll(".history-check").forEach(cb => {
            cb.addEventListener("change", () => {
                if (cb.checked) selectedForCompare.add(cb.dataset.id);
                else selectedForCompare.delete(cb.dataset.id);
            });
        });

        historyList.querySelectorAll(".history-load").forEach(btn => {
            btn.addEventListener("click", () => {
                const id = btn.closest(".history-item").dataset.id;
                const entry = entries.find(e => e.id === id);
                if (entry) window.loadRunIntoUI(entry);
            });
        });
    }

    function formatDate(iso) {
        const d = new Date(iso);
        return `${d.getMonth()+1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2,"0")}`;
    }

    function escapeHtml(s) {
        const d = document.createElement("div");
        d.textContent = s;
        return d.innerHTML;
    }

    // ─── Compare ────────────────────────────────────
    const compareModal = document.getElementById("compareModal");
    const compareClose = document.getElementById("compareClose");
    const compareGrid = document.getElementById("compareGrid");
    const compareDiff = document.getElementById("compareDiff");
    const diffView = document.getElementById("diffView");

    compareClose.addEventListener("click", () => compareModal.classList.add("hidden"));
    compareModal.addEventListener("click", (e) => { if (e.target === compareModal) compareModal.classList.add("hidden"); });

    function openCompare(idA, idB) {
        const entries = loadHistory();
        const a = entries.find(e => e.id === idA);
        const b = entries.find(e => e.id === idB);
        if (!a || !b) return;

        compareGrid.innerHTML = `
            <div class="compare-col">
                <h4>${formatDate(a.timestamp)} · ${a.mode}</h4>
                <div class="compare-field"><span>Query:</span> <div>${escapeHtml(a.query)}</div></div>
                <div class="compare-field"><span>Confidence:</span> <div>${a.confidence.toFixed(2)}</div></div>
                <div class="compare-field"><span>Data Quality:</span> <div>${a.data_quality.toFixed(2)}</div></div>
                <div class="compare-field"><span>Duration:</span> <div>${a.duration_s.toFixed(0)}s</div></div>
                <div class="compare-field"><span>Summary:</span> <div>${escapeHtml(a.summary)}</div></div>
            </div>
            <div class="compare-col">
                <h4>${formatDate(b.timestamp)} · ${b.mode}</h4>
                <div class="compare-field"><span>Query:</span> <div>${escapeHtml(b.query)}</div></div>
                <div class="compare-field"><span>Confidence:</span> <div>${b.confidence.toFixed(2)}</div></div>
                <div class="compare-field"><span>Data Quality:</span> <div>${b.data_quality.toFixed(2)}</div></div>
                <div class="compare-field"><span>Duration:</span> <div>${b.duration_s.toFixed(0)}s</div></div>
                <div class="compare-field"><span>Summary:</span> <div>${escapeHtml(b.summary)}</div></div>
            </div>
        `;

        compareDiff.classList.remove("hidden");
        diffView.innerHTML = simpleDiff(a.summary || "", b.summary || "");
        historyModal.classList.add("hidden");
        compareModal.classList.remove("hidden");
    }

    function simpleDiff(a, b) {
        const wordsA = a.split(/\s+/);
        const wordsB = b.split(/\s+/);
        const maxLen = Math.max(wordsA.length, wordsB.length);
        let html = "";
        for (let i = 0; i < maxLen; i++) {
            const wa = wordsA[i] || "";
            const wb = wordsB[i] || "";
            if (wa === wb) {
                html += wa + " ";
            } else {
                html += `<span class="diff-del">${escapeHtml(wa)}</span> `;
                if (wb) html += `<span class="diff-add">${escapeHtml(wb)}</span> `;
            }
        }
        return html;
    }

    // ─── Load run into UI (replaces current state) ───
    window.loadRunIntoUI = function(entry) {
        document.getElementById("queryInput").value = entry.query || "";
        document.getElementById("modeSelect").value = entry.mode || "debate";
        document.getElementById("domainSelect").value = entry.domain || "general";

        // Trigger displayResult
        const fakeRes = {
            query: entry.query,
            mode: entry.mode,
            domain: entry.domain,
            confidence: entry.confidence,
            summary: entry.summary,
            risk: entry.risk,
            data_quality: entry.data_quality,
            duration_s: entry.duration_s,
            dissent: entry.dissent,
            social_modifier: entry.social_modifier,
            health_score: entry.health_score,
            sentiment_trajectory: entry.sentiment_trajectory,
            multi_sample: entry.multi_sample,
            timestamp: entry.timestamp,
        };
        if (typeof displayResult === "function") displayResult(fakeRes);
        historyModal.classList.add("hidden");
    };
})();
