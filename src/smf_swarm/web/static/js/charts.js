/* SMF Predict — SVG Chart Engine (zero external deps, zero CDNs) */

/**
 * Render a line chart as pure SVG.
 * @param {string} containerId — DOM element to inject SVG into
 * @param {Array} data — [{x, y, label?}, ...]
 * @param {Object} opts — {title, color, xLabel, yLabel, height}
 */
function renderLineChart(containerId, data, opts = {}) {
    opts = Object.assign({
        title: "",
        color: "#00d4ff",
        areaColor: "rgba(0,212,255,0.08)",
        xLabel: "",
        yLabel: "",
        height: 220,
        minY: null,
        maxY: null,
    }, opts);

    const maxX = data.length > 0 ? Math.max(...data.map(d => d.x)) : 1;
    const maxY = opts.maxY != null ? opts.maxY : Math.max(
        1, Math.max(...data.map(d => d.y), 0)
    );
    const minY = opts.minY != null ? opts.minY : Math.min(0, Math.min(...data.map(d => d.y), 0));
    const rangeY = maxY - minY || 1;

    const pad = { top: opts.title ? 32 : 24, right: 24, bottom: 40, left: 48 };
    const W = 800, H = opts.height;
    const w = W - pad.left - pad.right;
    const h = H - pad.top - pad.bottom;

    const sx = x => pad.left + (x / maxX) * w;
    const sy = y => pad.top + h - ((y - minY) / rangeY) * h;

    const points = data.map(d => `${sx(d.x).toFixed(1)},${sy(d.y).toFixed(1)}`).join(" ");
    const areaPoints = `${pad.left},${pad.top + h} ${points} ${pad.left + w},${pad.top + h}`;

    // Y-axis ticks
    const yTickCount = 5;
    let yTicks = "";
    for (let i = 0; i <= yTickCount; i++) {
        const v = minY + (rangeY * (i / yTickCount));
        const y = pad.top + h - (i / yTickCount) * h;
        yTicks += `<text x="${pad.left - 8}" y="${y.toFixed(1)+4}" text-anchor="end" fill="#5a5a6a" font-size="9" font-family="monospace">${v.toFixed(1)}</text>`;
        yTicks += `<line x1="${pad.left}" y1="${y.toFixed(1)}" x2="${pad.left+w}" y2="${y.toFixed(1)}" stroke="rgba(255,255,255,0.04)"/>`;
    }

    // X-axis ticks
    const xCount = Math.min(data.length, 8);
    let xTicks = "";
    for (let i = 0; i < Math.min(data.length, xCount + 1); i++) {
        const idx = Math.floor((data.length - 1) * (i / xCount));
        const d = data[idx];
        const x = sx(d.x);
        xTicks += `<text x="${x.toFixed(1)}" y="${pad.top + h + 18}" text-anchor="middle" fill="#5a5a6a" font-size="9" font-family="monospace">${d.label != null ? d.label : d.x}</text>`;
    }

    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    svg.setAttribute("preserveAspectRatio", "none");
    svg.style.width = "100%";
    svg.style.height = "100%";

    svg.innerHTML = `
        ${opts.title ? `<text x="${pad.left}" y="16" fill="#8a8a99" font-size="11" font-weight="600" letter-spacing="0.5">${escapeHtml(opts.title)}</text>` : ''}
        <line x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${pad.top+h}" stroke="rgba(255,255,255,0.06)" stroke-width="1"/>
        <line x1="${pad.left}" y1="${pad.top+h}" x2="${pad.left+w}" y2="${pad.top+h}" stroke="rgba(255,255,255,0.06)" stroke-width="1"/>
        ${yTicks}
        ${xTicks}
        <polygon points="${areaPoints}" fill="${opts.areaColor}" stroke="none"/>
        <polyline points="${points}" fill="none" stroke="${opts.color}" stroke-width="2" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>
        ${opts.xLabel ? `<text x="${pad.left + w/2}" y="${H - 4}" text-anchor="middle" fill="#5a5a6a" font-size="9">${escapeHtml(opts.xLabel)}</text>` : ''}
        ${opts.yLabel ? `<text x="10" y="${pad.top + h/2}" text-anchor="middle" fill="#5a5a6a" font-size="9" transform="rotate(-90, 10, ${pad.top + h/2})">${escapeHtml(opts.yLabel)}</text>` : ''}
    `;

    const container = document.getElementById(containerId);
    if (container) {
        container.innerHTML = "";
        container.appendChild(svg);
    }
}

/**
 * Render a confidence bar chart (horizontal bars) as pure SVG.
 * @param {string} containerId
 * @param {Array} data — [{label, value, color}, ...]
 */
function renderBarChart(containerId, data, opts = {}) {
    opts = Object.assign({ height: 180 }, opts);
    const W = 800, H = opts.height;
    const pad = { top: 24, right: 16, bottom: 20, left: 120 };
    const w = W - pad.left - pad.right;
    const h = H - pad.top - pad.bottom;
    const maxVal = Math.max(1, ...data.map(d => d.value));
    const barH = Math.floor((h / data.length) * 0.7);
    const gap = Math.floor((h / data.length) * 0.3);

    let bars = "", labels = "";
    data.forEach((d, i) => {
        const y = pad.top + i * (barH + gap);
        const bw = (d.value / maxVal) * w;
        bars += `<rect x="${pad.left}" y="${y}" width="${bw.toFixed(1)}" height="${barH}" rx="3" fill="${d.color || '#00d4ff'}"/>`;
        bars += `<text x="${pad.left + bw + 6}" y="${y + barH/2 + 4}" fill="#8a8a99" font-size="10" font-family="monospace">${d.value.toFixed(2)}</text>`;
        labels += `<text x="${pad.left - 8}" y="${y + barH/2 + 4}" text-anchor="end" fill="#8a8a99" font-size="10">${escapeHtml(d.label)}</text>`;
    });

    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    svg.style.width = "100%";
    svg.style.height = "100%";
    svg.innerHTML = bars + labels;

    const container = document.getElementById(containerId);
    if (container) {
        container.innerHTML = "";
        container.appendChild(svg);
    }
}

function escapeHtml(s) {
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
}
