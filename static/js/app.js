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

function celebrationMessage(childName) {
    const messages = [
        `Hey ${childName}! You have done a great job!`,
        `Amazing work, ${childName}! Keep shining bright!`,
        `Wow ${childName}! You are a superstar today!`,
        `Fantastic, ${childName}! I am so proud of you!`,
    ];
    return messages[Math.floor(Math.random() * messages.length)];
}

function pickFriendlyVoice() {
    const voices = window.speechSynthesis?.getVoices() || [];
    return (
        voices.find((voice) => voice.lang.startsWith("en") && /female|samantha|zira|google uk english female/i.test(voice.name))
        || voices.find((voice) => voice.lang.startsWith("en"))
        || voices[0]
    );
}

function speakCelebration(childName) {
    if (!childName || !window.speechSynthesis) {
        successSound();
        return;
    }

    successSound();

    const speak = () => {
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(celebrationMessage(childName));
        utterance.rate = 0.92;
        utterance.pitch = 1.15;
        utterance.volume = 1;
        const voice = pickFriendlyVoice();
        if (voice) {
            utterance.voice = voice;
        }
        window.speechSynthesis.speak(utterance);
    };

    const voices = window.speechSynthesis.getVoices();
    if (voices.length) {
        speak();
        return;
    }

    window.speechSynthesis.addEventListener("voiceschanged", speak, { once: true });
}

async function fetchTaskIconSuggestions(query, suggestUrl) {
    if (!suggestUrl) {
        return ["fa-solid fa-star"];
    }

    const response = await fetch(`${suggestUrl}?q=${encodeURIComponent(query)}`);
    if (!response.ok) {
        return ["fa-solid fa-star"];
    }

    const payload = await response.json();
    return payload.icons?.length ? payload.icons : ["fa-solid fa-star"];
}

function renderIconSuggestions(container, icons, selectedIcon, onSelect) {
    if (!container) {
        return;
    }

    container.innerHTML = "";
    icons.forEach((iconClass) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "icon-suggestion-btn";
        if (iconClass === selectedIcon) {
            button.classList.add("selected");
        }
        button.innerHTML = `<i class="${iconClass}"></i>`;
        button.title = "Use this icon";
        button.addEventListener("click", () => onSelect(iconClass, container));
        container.appendChild(button);
    });
}

function setSelectedIcon(iconClass, hiddenInput, previewElement, container) {
    if (hiddenInput) {
        hiddenInput.value = iconClass;
    }

    if (previewElement) {
        previewElement.innerHTML = `<i class="${iconClass}"></i>`;
    }

    container?.querySelectorAll(".icon-suggestion-btn").forEach((button) => {
        button.classList.toggle("selected", button.querySelector("i")?.className === iconClass);
    });
}

function setupTaskIconPicker({
    titleInput,
    hiddenInput,
    previewElement,
    suggestionsContainer,
    suggestUrl,
    rowElement,
    loadOnInit = true,
}) {
    let debounceTimer;

    const updatePreviewInRow = (iconClass) => {
        rowElement?.querySelector(".edit-task-icon i")?.setAttribute("class", iconClass);
    };

    const applyIcons = (icons, selectedIcon) => {
        renderIconSuggestions(suggestionsContainer, icons, selectedIcon, (iconClass, container) => {
            setSelectedIcon(iconClass, hiddenInput, previewElement, container);
            updatePreviewInRow(iconClass);
        });
    };

    const refreshSuggestions = async () => {
        const query = titleInput.value.trim();
        const icons = await fetchTaskIconSuggestions(query, suggestUrl);
        const selectedIcon = hiddenInput?.value || icons[0];
        const nextIcon = icons.includes(selectedIcon) ? selectedIcon : icons[0];
        setSelectedIcon(nextIcon, hiddenInput, previewElement, suggestionsContainer);
        updatePreviewInRow(nextIcon);
        applyIcons(icons, nextIcon);
    };

    const showCurrentSelection = () => {
        const selectedIcon = hiddenInput?.value || "fa-solid fa-star";
        setSelectedIcon(selectedIcon, hiddenInput, previewElement, suggestionsContainer);
        updatePreviewInRow(selectedIcon);
        if (suggestionsContainer) {
            applyIcons([selectedIcon], selectedIcon);
        }
    };

    titleInput.addEventListener("input", () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(refreshSuggestions, 250);
    });

    if (loadOnInit) {
        refreshSuggestions();
    } else {
        showCurrentSelection();
    }
}

function initTaskIconPickers() {
    const picker = document.querySelector(".task-icon-picker");
    if (picker) {
        setupTaskIconPicker({
            titleInput: document.getElementById("taskTitleInput"),
            hiddenInput: document.getElementById("taskIconInput"),
            previewElement: document.getElementById("taskIconPreview"),
            suggestionsContainer: document.getElementById("taskIconSuggestions"),
            suggestUrl: picker.dataset.iconSuggestUrl,
        });
    }

    document.querySelectorAll(".task-edit-form").forEach((form) => {
        setupTaskIconPicker({
            titleInput: form.querySelector(".edit-task-title"),
            hiddenInput: form.querySelector(".edit-task-icon-input"),
            previewElement: null,
            suggestionsContainer: form.querySelector(".edit-icon-suggestions"),
            suggestUrl: document.querySelector(".task-icon-picker")?.dataset.iconSuggestUrl,
            rowElement: form.closest("tr"),
            loadOnInit: false,
        });
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
                speakCelebration(form.dataset.childName);
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

    document.getElementById("rewardSearch")?.addEventListener("input", (event) => {
        const query = event.target.value.toLowerCase();
        document.querySelectorAll("#rewardTable tr").forEach((row) => {
            row.style.display = row.textContent.toLowerCase().includes(query) ? "" : "none";
        });
    });

    initTaskIconPickers();
});
