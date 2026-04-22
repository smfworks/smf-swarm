/** SMF Predict — Web UI Controller */

(function() {
    const STATE = {
        query: "",
        mode: "debate",
        domain: "general",
        contextText: "",
        contextFilename: "",
        jobId: null,
        running: false,
        startTime: null,
    };

    const ELS = {
        queryInput: document.getElementById("queryInput"),
        modeSelect: document.getElementById("modeSelect"),
        domainSelect: document.getElementById("domainSelect"),
        uploadZone: document.getElementById("uploadZone"),
        uploadInput: document.getElementById("uploadInput"),
        uploadFilename: document.getElementById("uploadFilename"),
        uploadPreview: document.getElementById("uploadPreview"),
        charCount: document.getElementById("charCount"),
        clearBtn: document.getElementById("clearBtn"),
        runBtn: document.getElementById("runBtn"),
        downloadBtn: document.getElementById("downloadBtn"),
        terminalBody: document.getElementById("terminalBody"),
        terminalStatus: document.getElementById("terminalStatus"),
        progressFill: document.getElementById("progressFill"),
        progressPct: document.getElementById("progressPct"),
        confidenceArc: document.getElementById("confidenceArc"),
        confidenceValue: document.getElementById("confidenceValue"),
        dataQuality: document.getElementById("dataQuality"),
        duration: document.getElementById("duration"),
        health: document.getElementById("health"),
        execSummary: document.getElementById("execSummary"),
        riskAssessment: document.getElementById("riskAssessment"),
        dissent: document.getElementById("dissent"),
        dissentSection: document.getElementById("dissentSection"),
        socialSim: document.getElementById("socialSim"),
        socialSection: document.getElementById("socialSection"),
        resultSection: document.getElementById("resultSection"),
        nodeList: document.getElementById("nodeList"),
    };

    // ─── Helpers ──────────────────────────────────
    const fmtTs = () => {
        const n = new Date();
        return `${String(n.getHours()).padStart(2,"0")}:${String(n.getMinutes()).padStart(2,"0")}:${String(n.getSeconds()).padStart(2,"0")}`;
    };

    const logLine = (text, cls = "log-info") => {
        const line = document.createElement("div");
        line.className = `terminal-line ${cls}`;
        line.innerHTML = `<span class="ts">${fmtTs()}</span><span>${escapeHtml(text)}</span>`;
        ELS.terminalBody.appendChild(line);
        ELS.terminalBody.scrollTop = ELS.terminalBody.scrollHeight;
    };

    const escapeHtml = (s) => {
        const d = document.createElement("div");
        d.textContent = s;
        return d.innerHTML;
    };

    const setTerminalStatus = (status) => {
        const map = {
            idle: ["idle", "Idle"],
            running: ["running", "Running..."],
            complete: ["complete", "Complete"],
            error: ["error", "Error"],
        };
        const [dotCls, text] = map[status] || map.idle;
        ELS.terminalStatus.innerHTML = `<span class="status-dot ${dotCls}"></span><span class="status-text">${text}</span>`;
    };

    // Build dynamic node list per mode
    const MODE_NODES = {
        standard: ["data_gatherer", "feature_engineer", "reflection", "model_runner", "validator", "reporter"],
        debate: ["data_gatherer", "feature_engineer", "debate", "reporter"],
        full: ["data_gatherer", "feature_engineer", "reflection", "model_runner", "validator", "debate", "merge", "social_simulation", "reporter"],
    };

    const NODE_LABELS = {
        data_gatherer: "Data Gatherer",
        feature_engineer: "Feature Engineer",
        reflection: "Reflection",
        model_runner: "Model Runner",
        validator: "Validator",
        debate: "Debate Engine",
        merge: "Merger",
        social_simulation: "Social Simulation",
        reporter: "Reporter",
    };

    const buildNodeList = (mode) => {
        ELS.nodeList.innerHTML = "";
        const nodes = MODE_NODES[mode] || MODE_NODES.debate;
        nodes.forEach(name => {
            const item = document.createElement("div");
            item.className = "node-item pending";
            item.id = `node-${name}`;
            item.innerHTML = `<span class="node-indicator"></span><span class="node-name">${NODE_LABELS[name]}</span><span class="node-status">—</span>`;
            ELS.nodeList.appendChild(item);
        });
    };

    const setNodeStatus = (name, status, duration = null) => {
        const el = document.getElementById(`node-${name}`);
        if (!el) return;
        el.className = `node-item ${status}`;
        const statusText = status === "complete" ? (duration ? `${duration}s` : "Done") : status === "running" ? "Running..." : "—";
        const dot = el.querySelector(".node-indicator");
        if (status === "running") {
            dot.style.background = "#f5a623";
        } else if (status === "complete") {
            dot.style.background = "#2ecc71";
        }
        el.querySelector(".node-status").textContent = statusText;
    };

    const setProgress = (pct) => {
        ELS.progressFill.style.width = `${pct}%`;
        ELS.progressPct.textContent = `${pct}%`;
    };

    const setConfidence = (conf) => {
        const arcLen = 327; // 2 * PI * 52
        const offset = arcLen - (conf * arcLen);
        ELS.confidenceArc.style.strokeDashoffset = Math.max(0, offset);
        ELS.confidenceValue.textContent = conf.toFixed(1);
    };

    // ─── Upload ────────────────────────────────────
    ELS.uploadZone.addEventListener("click", () => ELS.uploadInput.click());
    ELS.uploadZone.addEventListener("dragover", (e) => { e.preventDefault(); ELS.uploadZone.classList.add("drag-over"); });
    ELS.uploadZone.addEventListener("dragleave", () => ELS.uploadZone.classList.remove("drag-over"));
    ELS.uploadZone.addEventListener("drop", (e) => {
        e.preventDefault();
        ELS.uploadZone.classList.remove("drag-over");
        const files = e.dataTransfer.files;
        if (files.length) handleFile(files[0]);
    });
    ELS.uploadInput.addEventListener("change", () => {
        if (ELS.uploadInput.files.length) handleFile(ELS.uploadInput.files[0]);
    });

    async function handleFile(file) {
        STATE.contextFilename = file.name;
        ELS.uploadFilename.textContent = file.name;
        ELS.uploadZone.classList.add("has-file");
        logLine(`Uploading ${file.name}...`);

        const form = new FormData();
        form.append("file", file);

        try {
            const res = await fetch("/api/upload", { method: "POST", body: form });
            const data = await res.json();
            if (data.error) {
                logLine(`Upload failed: ${data.error}`, "log-error");
                return;
            }
            STATE.contextText = data.text || "";
            ELS.uploadPreview.textContent = data.text_preview || "";
            ELS.uploadPreview.classList.add("visible");
            logLine(`Ingested ${data.char_sent.toLocaleString()} chars${data.truncated ? " (truncated)" : ""}`, "log-success");
        } catch (err) {
            logLine(`Upload error: ${err.message}`, "log-error");
        }
    }

    // ─── Query ───────────────────────────────────
    ELS.queryInput.addEventListener("input", () => {
        STATE.query = ELS.queryInput.value;
        ELS.charCount.textContent = `${STATE.query.length} chars`;
    });

    ELS.modeSelect.addEventListener("change", () => {
        STATE.mode = ELS.modeSelect.value;
        buildNodeList(STATE.mode);
    });

    ELS.domainSelect.addEventListener("change", () => {
        STATE.domain = ELS.domainSelect.value;
    });

    ELS.clearBtn.addEventListener("click", () => {
        ELS.queryInput.value = "";
        STATE.query = "";
        ELS.charCount.textContent = "0 chars";
        ELS.uploadInput.value = "";
        STATE.contextText = "";
        STATE.contextFilename = "";
        ELS.uploadFilename.textContent = "";
        ELS.uploadPreview.textContent = "";
        ELS.uploadPreview.classList.remove("visible");
        ELS.uploadZone.classList.remove("has-file");
        // hide results
        ELS.resultSection.classList.add("hidden");
        ELS.downloadBtn.classList.add("hidden");
        setProgress(0);
        ELS.nodeList.querySelectorAll(".node-item").forEach(el => {
            el.className = "node-item pending";
            el.querySelector(".node-status").textContent = "—";
        });
    });

    // ─── Run ──────────────────────────────────────
    ELS.runBtn.addEventListener("click", async () => {
        if (STATE.running) return;
        const query = ELS.queryInput.value.trim();
        if (!query) {
            logLine("Enter a prediction question first.", "log-error");
            return;
        }

        STATE.query = query;
        STATE.mode = ELS.modeSelect.value;
        STATE.domain = ELS.domainSelect.value;
        STATE.running = true;
        STATE.startTime = performance.now();

        // Reset UI
        ELS.resultSection.classList.add("hidden");
        ELS.downloadBtn.classList.add("hidden");
        ELS.terminalBody.innerHTML = "";
        setTerminalStatus("running");
        setProgress(0);
        buildNodeList(STATE.mode);
        ELS.runBtn.disabled = true;
        ELS.runBtn.querySelector(".run-text").textContent = "Running...";

        logLine(`🎯 Query: ${query}`, "log-system");
        logLine(`Mode: ${STATE.mode} | Domain: ${STATE.domain}`);
        if (STATE.contextFilename) logLine(`Context: ${STATE.contextFilename}`);

        try {
            // Submit job
            const submitRes = await fetch("/api/predict", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    query: STATE.query,
                    mode: STATE.mode,
                    domain: STATE.domain,
                    context_text: STATE.contextText,
                }),
            });
            const submitData = await submitRes.json();
            if (submitData.error) {
                throw new Error(submitData.error);
            }
            STATE.jobId = submitData.job_id;
            logLine(`Job queued: ${STATE.jobId}`, "log-info");

            // SSE Stream
            const evtSource = new EventSource(`/api/stream/${STATE.jobId}`);

            evtSource.addEventListener("progress", (e) => {
                const data = JSON.parse(e.data);
                if (data.node && data.status) {
                    setNodeStatus(data.node, data.status, data.duration);
                    if (data.status === "running") {
                        logLine(`→ ${NODE_LABELS[data.node]}...`, "log-agent");
                    } else if (data.status === "complete") {
                        logLine(`✓ ${NODE_LABELS[data.node]} — ${data.duration}s`, "log-success");
                    }
                }
                // Estimate progress from completed nodes
                const completed = Array.from(ELS.nodeList.querySelectorAll(".node-item.complete")).length;
                const total = ELS.nodeList.querySelectorAll(".node-item").length;
                setProgress(Math.min(99, Math.floor((completed / total) * 100)));
            });

            evtSource.addEventListener("log", (e) => {
                const data = JSON.parse(e.data);
                if (data.message) logLine(data.message, "log-info");
            });

            evtSource.addEventListener("result", (e) => {
                const data = JSON.parse(e.data);
                displayResult(data.result || data);
                evtSource.close();
                finishRun(true);
            });

            evtSource.addEventListener("error", (e) => {
                const data = JSON.parse(e.data);
                logLine(`Error: ${data.message || "Pipeline failed"}`, "log-error");
                evtSource.close();
                finishRun(false);
            });

            evtSource.onerror = () => {
                logLine("Event stream closed.", "log-info");
                evtSource.close();
                if (STATE.running) finishRun(false);
            };

        } catch (err) {
            logLine(`Failed to start: ${err.message}`, "log-error");
            finishRun(false);
        }
    });

    function displayResult(res) {
        STATE.lastResult = res;
        ELS.resultSection.classList.remove("hidden");

        const conf = typeof res.confidence === "number" ? res.confidence : 0;
        setConfidence(conf);
        ELS.dataQuality.textContent = res.data_quality != null ? res.data_quality.toFixed(2) : "—";
        ELS.duration.textContent = res.duration_s != null ? `${res.duration_s.toFixed(0)}s` : "—";
        ELS.health.textContent = res.health_score != null ? res.health_score.toFixed(1) : "—";

        ELS.execSummary.textContent = res.summary || res.prediction_text || "No summary available.";
        ELS.riskAssessment.textContent = res.risk || "No risk assessment.";

        if (res.dissent) {
            ELS.dissent.textContent = res.dissent;
            ELS.dissentSection.classList.remove("hidden");
        } else {
            ELS.dissentSection.classList.add("hidden");
        }

        if (res.social_modifier != null) {
            ELS.socialSim.textContent = `Social Modifier: ${res.social_modifier >= 0 ? '+' : ''}${res.social_modifier.toFixed(2)}`;
            ELS.socialSection.classList.remove("hidden");
        } else {
            ELS.socialSection.classList.add("hidden");
        }
    }

    function finishRun(success) {
        STATE.running = false;
        ELS.runBtn.disabled = false;
        ELS.runBtn.querySelector(".run-text").textContent = "Run Prediction";
        setTerminalStatus(success ? "complete" : "error");
        setProgress(success ? 100 : ELS.progressFill.style.width.replace("%", ""));
        ELS.duration.textContent = `${((performance.now() - STATE.startTime) / 1000).toFixed(1)}s`;

        if (success) {
            ELS.downloadBtn.classList.remove("hidden");
            logLine("DONE — Report ready for download.", "log-success");
        } else {
            logLine("FAILED — See terminal for details.", "log-error");
        }
    }

    // ─── Download ─────────────────────────────────
    ELS.downloadBtn.addEventListener("click", () => {
        const res = STATE.lastResult;
        if (!res) return;

        const md = buildMarkdownReport(res);
        const blob = new Blob([md], { type: "text/markdown" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `smf-predict-${res.timestamp?.slice(0,10) || "report"}.md`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        logLine("Report downloaded.");
    });

    function buildMarkdownReport(res) {
        return `# SMF Predict Report

**Query:** ${res.query || "—"}  
**Mode:** ${res.mode || "—"}  
**Domain:** ${res.domain || "—"}  
**Confidence:** ${(res.confidence || 0).toFixed(2)}  
**Data Quality:** ${(res.data_quality || 0).toFixed(2)}  
**Duration:** ${res.duration_s || 0}s  
**Timestamp:** ${res.timestamp || new Date().toISOString()}  

---

## Executive Summary

${res.summary || "No summary available."}

## Risk Assessment

${res.risk || "No risk assessment."}

${res.dissent ? `## Dissent\n\n${res.dissent}\n` : ""}

${res.social_modifier != null ? `## Social Simulation\n\nModifier: ${res.social_modifier >= 0 ? '+' : ''}${res.social_modifier.toFixed(2)}\n` : ""}

---

*Generated by SMF Swarm v1.1.0*
`;
    }

    // ─── Init ────────────────────────────────────
    buildNodeList("debate");
    logLine("SMF Swarm Web UI initialized. Waiting for query.");
})();
