// CarbonTrack dashboard: activity form helpers and Chart.js charts.

(function () {
    const dataEl = document.getElementById("dashboard-data");
    if (!dataEl) return;
    const data = JSON.parse(dataEl.textContent);
    const categories = data.categories;

    // ---------- Add activity form ----------
    const category = document.getElementById("category");
    const item = document.getElementById("activity_type");
    const amount = document.getElementById("amount");
    const amountLabel = document.getElementById("amount-label");
    const modeField = document.getElementById("mode-field");
    const preview = document.getElementById("preview");

    function mode() {
        const checked = document.querySelector("input[name=mode]:checked");
        return checked ? checked.value : "weight";
    }

    function fillItems() {
        const cat = categories[category.value];
        item.innerHTML = "";
        Object.entries(cat.items).forEach(function ([key, spec]) {
            const opt = document.createElement("option");
            opt.value = key;
            opt.textContent = spec.label;
            item.appendChild(opt);
        });
        modeField.hidden = !cat.servings;
        updateLabel();
    }

    function updateLabel() {
        const cat = categories[category.value];
        const spec = cat.items[item.value] || {};
        if (cat.servings && mode() === "servings") {
            amountLabel.textContent = "Servings";
        } else {
            amountLabel.textContent = spec.input_label || cat.input_label;
        }
        updatePreview();
    }

    // Mirrors calculate_emission() in app.py so the user sees the result before saving.
    function estimate() {
        const value = parseFloat(amount.value);
        if (!Number.isFinite(value) || value <= 0) return null;
        const spec = categories[category.value].items[item.value];
        if (!spec) return null;
        if (category.value === "energy") return value * spec.power_kw * data.grid;
        if (category.value === "food" && mode() === "servings") return value * spec.serving_kg * spec.factor;
        return value * spec.factor;
    }

    function updatePreview() {
        const kg = estimate();
        preview.textContent = kg === null ? "" : "≈ " + kg.toFixed(kg < 1 ? 3 : 2) + " kg CO₂e";
    }

    category.addEventListener("change", fillItems);
    item.addEventListener("change", updateLabel);
    amount.addEventListener("input", updatePreview);
    document.querySelectorAll("input[name=mode]").forEach(function (r) {
        r.addEventListener("change", updateLabel);
    });
    fillItems();

    // ---------- Charts ----------
    if (typeof Chart === "undefined") {
        document.querySelectorAll(".chart-box").forEach(function (box) {
            box.innerHTML = '<p class="empty">Charts could not load (offline?).</p>';
        });
        return;
    }

    const css = function (name) {
        return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    };
    const charts = [];

    function draw() {
        charts.splice(0).forEach(function (c) { c.destroy(); });
        const text = css("--text-muted");
        const grid = css("--border");
        Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
        Chart.defaults.color = text;

        const daily = document.getElementById("daily-chart");
        if (daily) {
            charts.push(new Chart(daily, {
                type: "bar",
                data: {
                    labels: data.chart.labels,
                    datasets: [{
                        label: "kg CO₂e",
                        data: data.chart.values,
                        backgroundColor: css("--accent"),
                        borderRadius: 4,
                        maxBarThickness: 18
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: { callbacks: { label: function (c) { return c.parsed.y.toFixed(2) + " kg CO₂e"; } } }
                    },
                    scales: {
                        x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8 } },
                        y: { beginAtZero: true, grid: { color: grid }, ticks: { callback: function (v) { return v + " kg"; } } }
                    }
                }
            }));
        }

        const byCat = document.getElementById("category-chart");
        if (byCat) {
            const keys = Object.keys(categories);
            charts.push(new Chart(byCat, {
                type: "doughnut",
                data: {
                    labels: data.chart.categories,
                    datasets: [{
                        data: data.chart.categoryValues,
                        backgroundColor: keys.map(function (k) { return css("--cat-" + k) || css("--accent"); }),
                        borderColor: css("--bg-card"),
                        borderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: "62%",
                    plugins: {
                        legend: { position: "bottom", labels: { usePointStyle: true, boxWidth: 8, padding: 14 } },
                        tooltip: {
                            callbacks: {
                                label: function (c) {
                                    const total = c.dataset.data.reduce(function (a, b) { return a + b; }, 0);
                                    const pct = total ? Math.round(c.parsed / total * 100) : 0;
                                    return " " + c.label + ": " + c.parsed.toFixed(2) + " kg (" + pct + "%)";
                                }
                            }
                        }
                    }
                }
            }));
        }
    }

    draw();
    document.addEventListener("themechange", draw);
    window.matchMedia("(prefers-color-scheme: light)").addEventListener("change", draw);
})();
