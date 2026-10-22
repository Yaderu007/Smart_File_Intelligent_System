
document.addEventListener("DOMContentLoaded", () => {
    // Theme preference: use the saved choice, otherwise follow the OS setting.
    const themeButton = document.getElementById("theme-toggle");
    const root = document.documentElement;
    const savedTheme = localStorage.getItem("sfi-theme");
    const preferredTheme = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";

    function applyTheme(theme) {
        root.dataset.theme = theme;
        if (themeButton) {
            const dark = theme === "dark";
            themeButton.setAttribute("aria-label", dark ? "Switch to light mode" : "Switch to dark mode");
            themeButton.querySelector(".theme-icon").textContent = dark ? "☀" : "☾";
            themeButton.querySelector(".theme-label").textContent = dark ? "Light mode" : "Dark mode";
        }
        localStorage.setItem("sfi-theme", theme);
    }
    applyTheme(savedTheme || preferredTheme);
    if (themeButton) {
        themeButton.addEventListener("click", () => {
            applyTheme(root.dataset.theme === "dark" ? "light" : "dark");
        });
    }

    // Search filters visible file, category and duplicate rows without a server request.
    const searchInput = document.getElementById("dashboard-search");
    if (searchInput) {
        searchInput.addEventListener("input", () => {
            const query = searchInput.value.trim().toLowerCase();
            document.querySelectorAll(".file-row, .category-row, .duplicate-row").forEach((row) => {
                row.hidden = query !== "" && !row.textContent.toLowerCase().includes(query);
            });
        });
    }

    const canvas = document.getElementById("storageCategoryChart");

    if (!canvas || typeof Chart === "undefined") {
        return;
    }

    const categoryDataElement = document.getElementById("category-chart-data");

    if (!categoryDataElement) {
        return;
    }

    const categoryStats = JSON.parse(categoryDataElement.textContent);
    const categories = Object.keys(categoryStats);
    const storageValues = categories.map(
        (category) => categoryStats[category].total_size
    );

    new Chart(canvas, {
        type: "doughnut",
        data: {
            labels: categories,
            datasets: [{
                label: "Storage (bytes)",
                data: storageValues,
                borderWidth: 2,
                hoverOffset: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: "bottom"
                },
                tooltip: {
                    callbacks: {
                        label(context) {
                            const bytes = context.raw;
                            const formatted = bytes >= 1024
                                ? `${(bytes / 1024).toFixed(2)} KB`
                                : `${bytes} B`;

                            return `${context.label}: ${formatted}`;
                        }
                    }
                }
            }
        }
    });
});
