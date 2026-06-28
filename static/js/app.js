function renderDashboardCharts() {
    if (!window.Chart || !window.chartPayload) {
        return;
    }
    document.querySelectorAll(".starChart").forEach((canvas) => {
        const child = canvas.dataset.child;
        const data = window.chartPayload[child];
        new Chart(canvas, {
            type: "line",
            data: {
                labels: data.labels,
                datasets: [
                    {
                        label: "Daily",
                        data: data.daily,
                        borderColor: "#ff5fa2",
                        backgroundColor: "rgba(255, 95, 162, 0.16)",
                        tension: 0.42,
                        fill: true,
                    },
                    {
                        label: "Weekly",
                        data: data.weekly,
                        borderColor: "#27c9a5",
                        tension: 0.42,
                    },
                    {
                        label: "Monthly",
                        data: data.monthly,
                        borderColor: "#6c63ff",
                        tension: 0.42,
                    },
                ],
            },
            options: {
                responsive: true,
                plugins: { legend: { labels: { boxWidth: 12 } } },
                scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
            },
        });
    });
}

function burstConfetti() {
    const colors = ["#ffc83d", "#ff5fa2", "#27c9a5", "#37a2ff", "#6c63ff"];
    for (let i = 0; i < 34; i += 1) {
        const piece = document.createElement("span");
        piece.className = "confetti-piece";
        piece.style.left = `${Math.random() * 100}vw`;
        piece.style.top = `${Math.random() * 30}vh`;
        piece.style.background = colors[i % colors.length];
        piece.style.animationDelay = `${Math.random() * 0.25}s`;
        document.body.appendChild(piece);
        setTimeout(() => piece.remove(), 1500);
    }
}

function flyStar(button) {
    const rect = button.getBoundingClientRect();
    const star = document.createElement("span");
    star.className = "fly-star";
    star.textContent = "★";
    star.style.left = `${rect.left + rect.width / 2}px`;
    star.style.top = `${rect.top}px`;
    document.body.appendChild(star);
    setTimeout(() => star.remove(), 900);
}

function successSound() {
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const notes = [523.25, 659.25, 783.99];
    notes.forEach((frequency, index) => {
        const oscillator = audioContext.createOscillator();
        const gain = audioContext.createGain();
        oscillator.frequency.value = frequency;
        oscillator.connect(gain);
        gain.connect(audioContext.destination);
        gain.gain.setValueAtTime(0.08, audioContext.currentTime + index * 0.08);
        gain.gain.exponentialRampToValueAtTime(
            0.001,
            audioContext.currentTime + index * 0.08 + 0.18
        );
        oscillator.start(audioContext.currentTime + index * 0.08);
        oscillator.stop(audioContext.currentTime + index * 0.08 + 0.18);
    });
}

document.addEventListener("DOMContentLoaded", () => {
    const savedTheme = localStorage.getItem("kids-star-theme") || "light";
    document.documentElement.dataset.theme = savedTheme;

    document.getElementById("themeToggle")?.addEventListener("click", () => {
        const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
        document.documentElement.dataset.theme = next;
        localStorage.setItem("kids-star-theme", next);
    });

    document.querySelectorAll(".complete-form").forEach((form) => {
        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            const button = form.querySelector("button");
            if (!button || button.disabled) {
                return;
            }
            button.disabled = true;
            button.innerHTML = '<i class="fa-solid fa-check"></i> Done';
            flyStar(button);
            burstConfetti();
            try {
                successSound();
            } catch {
                // Some browsers require a user gesture before sound; the task still completes.
            }
            await fetch(form.action, {
                method: "POST",
                headers: { "X-Requested-With": "XMLHttpRequest" },
            });
        });
    });

    document.getElementById("taskSearch")?.addEventListener("input", (event) => {
        const query = event.target.value.toLowerCase();
        document.querySelectorAll("#taskTable tr").forEach((row) => {
            row.style.display = row.textContent.toLowerCase().includes(query) ? "" : "none";
        });
    });
});
