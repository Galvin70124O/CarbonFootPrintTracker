// CarbonTrack: shared behaviour on every page.

(function () {
    // Light/dark toggle. Without a saved choice the OS setting is used (CSS).
    const toggle = document.getElementById("theme-toggle");
    if (toggle) {
        toggle.addEventListener("click", function () {
            const root = document.documentElement;
            const current = root.getAttribute("data-theme") ||
                (window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
            const next = current === "dark" ? "light" : "dark";
            root.setAttribute("data-theme", next);
            try { localStorage.setItem("theme", next); } catch (e) {}
            document.dispatchEvent(new CustomEvent("themechange"));
        });
    }

    // Confirm before destructive form posts (delete).
    document.querySelectorAll("form[data-confirm]").forEach(function (form) {
        form.addEventListener("submit", function (event) {
            if (!window.confirm(form.dataset.confirm)) event.preventDefault();
        });
    });

    // Fade flash messages after a few seconds.
    document.querySelectorAll(".flash").forEach(function (el) {
        setTimeout(function () { el.classList.add("hide"); }, 5000);
    });
})();
