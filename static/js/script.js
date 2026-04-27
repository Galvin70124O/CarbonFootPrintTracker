function readJsonScript(id) {
    const script = document.getElementById(id);
    if (!script) {
        return null;
    }

    try {
        return JSON.parse(script.textContent);
    } catch {
        return null;
    }
}

function createEmissionChart(canvas, weeklyEmissions) {
    const context = canvas.getContext("2d");
    const gradient = context.createLinearGradient(0, 0, 0, 280);

    gradient.addColorStop(0, "rgba(125, 211, 168, 0.28)");
    gradient.addColorStop(1, "rgba(125, 211, 168, 0.02)");

    return new Chart(canvas, {
        type: "line",
        data: {
            labels: weeklyEmissions.labels,
            datasets: [{
                label: "Emissions",
                data: weeklyEmissions.values,
                borderColor: "#7dd3a8",
                backgroundColor: gradient,
                borderWidth: 2,
                fill: true,
                tension: 0.38,
                pointRadius: 4,
                pointHoverRadius: 6,
                pointBackgroundColor: "#0f172a",
                pointBorderColor: "#7dd3a8",
                pointBorderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: "rgba(15, 23, 42, 0.96)",
                    borderColor: "rgba(148, 163, 184, 0.18)",
                    borderWidth: 1,
                    titleColor: "#eef2f7",
                    bodyColor: "#cbd5e1",
                    displayColors: false,
                    callbacks: {
                        label: (context) => `${context.parsed.y.toFixed(4)}t CO2e`
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        color: "#8b9bb0"
                    },
                    border: {
                        color: "rgba(148, 163, 184, 0.14)"
                    }
                },
                y: {
                    beginAtZero: true,
                    grid: {
                        color: "rgba(148, 163, 184, 0.1)"
                    },
                    ticks: {
                        color: "#8b9bb0",
                        callback: (value) => `${value}t`
                    },
                    border: {
                        color: "rgba(148, 163, 184, 0.14)"
                    }
                }
            }
        }
    });
}

function initializeDashboardChart() {
    const canvas = document.getElementById("weeklyEmissionChart");
    const weeklyEmissions = readJsonScript("weekly-emissions-data");

    if (!canvas || !weeklyEmissions || typeof Chart === "undefined") {
        return;
    }

    createEmissionChart(canvas, weeklyEmissions);
}

function formatOptionLabel(option) {
    return option.label;
}

function getFirstOptionKey(options) {
    return Object.keys(options)[0];
}

function updateActivityOptions(categories) {
    const categorySelect = document.getElementById("category");
    const activitySelect = document.getElementById("activity_type");

    if (!categorySelect || !activitySelect || !categories) {
        return;
    }

    const category = categories[categorySelect.value];
    if (!category) {
        return;
    }

    activitySelect.innerHTML = "";

    Object.entries(category.options).forEach(([key, option]) => {
        const optionElement = document.createElement("option");
        optionElement.value = key;
        optionElement.textContent = formatOptionLabel(option);
        activitySelect.appendChild(optionElement);
    });

    activitySelect.value = getFirstOptionKey(category.options);
    updateActivityAmountHints(categories);
    updateInputMode(categories);
}

function updateInputMode(categories) {
    const categorySelect = document.getElementById("category");
    const foodInputToggle = document.getElementById("food-input-toggle");
    const hiddenInputType = document.getElementById("input_type");
    const amountInput = document.getElementById("amount");
    const amountLabel = document.getElementById("amount-label");
    const amountUnit = document.getElementById("amount-unit");
    const activityHelp = document.getElementById("activity-help");

    if (!categorySelect || !foodInputToggle || !categories) {
        return;
    }

    const category = categories[categorySelect.value];
    if (!category) {
        return;
    }

    // Show/hide food input toggle
    if (category.input_mode === "food") {
        foodInputToggle.style.display = "block";
        // Get current selected input type from radio buttons
        const selectedInputType = document.querySelector('input[name="input_type"]:checked')?.value || "servings";
        hiddenInputType.value = selectedInputType;
        updateFoodInputFields(selectedInputType, category);
    } else {
        foodInputToggle.style.display = "none";
        hiddenInputType.value = "simple";
        
        // Update for electricity or other categories
        if (category.input_mode === "electricity") {
            amountLabel.textContent = "Hours used";
            amountUnit.textContent = "hours";
            activityHelp.textContent = `Enter hours used for the selected appliance.`;
            amountInput.max = "24";
            amountInput.placeholder = "Example: 8";
        } else {
            amountLabel.textContent = category.amount_label;
            const option = category.options?.[document.getElementById("activity_type")?.value];
            if (option) {
                amountUnit.textContent = option.unit;
                activityHelp.textContent = `Enter ${category.amount_label.toLowerCase()} in ${option.unit} for ${option.label.toLowerCase()}.`;
            }
            amountInput.max = "100000";
            amountInput.placeholder = "Example: 12.5";
        }
    }
}

function updateFoodInputFields(inputType, category) {
    const amountLabel = document.getElementById("amount-label");
    const amountUnit = document.getElementById("amount-unit");
    const activityHelp = document.getElementById("activity-help");
    const amountInput = document.getElementById("amount");

    if (inputType === "weight") {
        amountLabel.textContent = "Weight";
        amountUnit.textContent = "grams";
        activityHelp.textContent = "Enter the weight in grams (1kg = 1000g).";
        amountInput.max = "10000";
        amountInput.placeholder = "Example: 250";
    } else {
        amountLabel.textContent = "Servings";
        amountUnit.textContent = "portions";
        activityHelp.textContent = "Enter the number of servings.";
        amountInput.max = "100";
        amountInput.placeholder = "Example: 2";
    }
}

function updateActivityAmountHints(categories) {
    const categorySelect = document.getElementById("category");
    const activitySelect = document.getElementById("activity_type");
    const amountLabel = document.getElementById("amount-label");
    const amountUnit = document.getElementById("amount-unit");
    const activityHelp = document.getElementById("activity-help");

    if (!categorySelect || !activitySelect || !amountLabel || !amountUnit || !activityHelp || !categories) {
        return;
    }

    const category = categories[categorySelect.value];
    const option = category?.options?.[activitySelect.value];

    if (!category || !option) {
        return;
    }

    // Don't update if food toggle is shown (it handles its own labels)
    if (category.input_mode === "food") {
        const inputType = document.querySelector('input[name="input_type"]:checked')?.value || "servings";
        updateFoodInputFields(inputType, category);
        return;
    }

    amountLabel.textContent = category.amount_label;
    amountUnit.textContent = option.unit;
    activityHelp.textContent = `Enter ${category.amount_label.toLowerCase()} in ${option.unit} for ${option.label.toLowerCase()}.`;
}

function initializeActivityForm() {
    const categories = readJsonScript("activity-categories-data");
    const categorySelect = document.getElementById("category");
    const activitySelect = document.getElementById("activity_type");
    const inputTypeRadios = document.querySelectorAll('input[name="input_type"]');

    if (!categories || !categorySelect || !activitySelect) {
        return;
    }

    categorySelect.addEventListener("change", () => updateActivityOptions(categories));
    activitySelect.addEventListener("change", () => updateActivityAmountHints(categories));
    
    // Handle food input type radio buttons
    inputTypeRadios.forEach((radio) => {
        radio.addEventListener("change", () => {
            const hiddenInputType = document.getElementById("input_type");
            if (radio.checked) {
                hiddenInputType.value = radio.value;
                updateActivityAmountHints(categories);
            }
        });
    });
    
    updateActivityOptions(categories);
}

function initializeFormSubmitState() {
    const forms = document.querySelectorAll("form");

    forms.forEach((form) => {
        form.addEventListener("submit", () => {
            const submitButton = form.querySelector("button[type='submit']");

            if (!submitButton) {
                return;
            }

            const loadingLabel = submitButton.dataset.loadingLabel || "Working...";
            submitButton.dataset.originalLabel = submitButton.textContent;
            submitButton.textContent = loadingLabel;
            submitButton.disabled = true;
            form.classList.add("is-submitting");
        });
    });
}

document.addEventListener("DOMContentLoaded", () => {
    initializeDashboardChart();
    initializeActivityForm();
    initializeFormSubmitState();
});
