// CarbonTrack - JavaScript

const categoryConfig = {
    transport: {
        subcategories: ["car_petrol", "bus", "train"],
        label: "Distance (km)",
        placeholder: "Enter km"
    },
    energy: {
        subcategories: ["ac", "fan", "fridge", "tv", "laptop"],
        label: "Usage Time (hours)",
        placeholder: "Enter hours"
    },
    food: {
        subcategories: ["beef", "chicken", "rice"],
        label: "Weight (kg)",
        placeholder: "Enter kg"
    },
    waste: {
        subcategories: ["plastic", "paper", "general_waste"],
        label: "Waste (kg)",
        placeholder: "Enter kg"
    }
};

document.addEventListener("DOMContentLoaded", function() {
    const themeToggle = document.getElementById("theme-toggle");
    const category = document.getElementById("category");
    const subcategory = document.getElementById("subcategory");
    const inputLabel = document.getElementById("inputLabel");
    const valueInput = document.getElementById("valueInput");
    const modeGroup = document.getElementById("modeGroup");
    const modeToggle = document.getElementById("modeToggle");

    if (themeToggle) {
        const themeIcon = themeToggle.querySelector(".theme-icon");
        const savedTheme = localStorage.getItem("theme") || "dark";

        document.documentElement.setAttribute("data-theme", savedTheme);
        updateThemeIcon(savedTheme);

        themeToggle.addEventListener("click", function() {
            const currentTheme = document.documentElement.getAttribute("data-theme");
            const newTheme = currentTheme === "dark" ? "light" : "dark";

            document.documentElement.setAttribute("data-theme", newTheme);
            localStorage.setItem("theme", newTheme);
            updateThemeIcon(newTheme);
        });

        function updateThemeIcon(theme) {
            if (themeIcon) {
                themeIcon.textContent = theme === "dark" ? "Moon" : "Sun";
            }
        }
    }

    function formatOption(value) {
        return value
            .replace(/_/g, " ")
            .replace(/\b\w/g, function(character) {
                return character.toUpperCase();
            });
    }

    function updateSubcategories() {
        if (!category || !subcategory) {
            return;
        }

        const config = categoryConfig[category.value];
        subcategory.innerHTML = "";

        config.subcategories.forEach(function(item) {
            const option = document.createElement("option");
            option.value = item;
            option.textContent = formatOption(item);
            subcategory.appendChild(option);
        });
    }

    function updateInputState() {
        if (!category || !inputLabel || !valueInput || !modeGroup || !modeToggle) {
            return;
        }

        const config = categoryConfig[category.value];
        const servingsMode = category.value === "food" && modeToggle.value === "servings";

        modeGroup.style.display = category.value === "food" ? "block" : "none";
        inputLabel.textContent = servingsMode ? "Servings" : config.label;
        valueInput.placeholder = servingsMode ? "Enter servings" : config.placeholder;
        valueInput.value = "";
    }

    if (category && subcategory && inputLabel && valueInput) {
        category.addEventListener("change", function() {
            updateSubcategories();
            updateInputState();
        });

        if (modeToggle) {
            modeToggle.addEventListener("change", updateInputState);
        }

        updateSubcategories();
        updateInputState();
    }
});

function addActivity(event) {
    event.preventDefault();

    const category = document.getElementById("category").value;
    const type = document.getElementById("subcategory").value;
    const rawAmount = document.getElementById("valueInput").value;
    const modeToggle = document.getElementById("modeToggle");
    const mode = modeToggle ? modeToggle.value : "";

    let amount = Number.parseFloat(rawAmount);

    if (category === "food" && mode === "servings") {
        amount = amount * 0.25;
    }

    if (!type || !Number.isFinite(amount) || amount <= 0) {
        alert("Please fill in all fields correctly.");
        return;
    }

    fetch("/add", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            type: type,
            amount: amount,
            date: new Date().toISOString()
        })
    }).then(function(response) {
        if (response.redirected) {
            window.location.href = response.url;
            return;
        }

        window.location.reload();
    });
}
