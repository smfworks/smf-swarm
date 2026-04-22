/** SMF Swarm — UI Components (reusable helpers) */

const UI = {
    createCard(title, content, classes = "") {
        const card = document.createElement("div");
        card.className = `glass-card ${classes}`;
        card.innerHTML = `
            <div class="card-header"><span class="card-title">${title}</span></div>
            <div class="card-body">${content}</div>
        `;
        return card;
    },

    createButton(text, onClick, variant = "primary") {
        const btn = document.createElement("button");
        btn.className = `btn btn-${variant}`;
        btn.textContent = text;
        btn.addEventListener("click", onClick);
        return btn;
    },

    showToast(message, type = "info") {
        const toast = document.createElement("div");
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        document.body.appendChild(toast);
        requestAnimationFrame(() => toast.classList.add("show"));
        setTimeout(() => {
            toast.classList.remove("show");
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
};
