document.addEventListener("DOMContentLoaded", () => {
    const root = document.documentElement;
    const themeButton = document.getElementById("theme-toggle");
    const chartElement = document.getElementById("storageCategoryChart");
    const chartDataElement = document.getElementById("category-chart-data");
    let categoryStats = {};

    let savedTheme = null;
    try {
        savedTheme = localStorage.getItem("sfi-theme");
    } catch (error) {
        // The theme control remains usable if local storage is unavailable.
    }
    const preferredTheme = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light";
    const cssValue = (name) => getComputedStyle(root).getPropertyValue(name).trim();
    const categoryColors = () => [
        cssValue("--chart-1"), cssValue("--chart-2"), cssValue("--chart-3"),
        cssValue("--chart-4"), cssValue("--chart-5"), cssValue("--chart-6")
    ];

    function renderCategoryChart() {
        if (!chartElement) return;
        const categories = Object.keys(categoryStats);
        const values = categories.map((category) => Math.max(0, Number(categoryStats[category].total_size) || 0));
        const total = values.reduce((sum, value) => sum + value, 0);
        const palette = categoryColors();

        let angle = 0;
        const stops = [];
        values.forEach((value, index) => {
            const nextAngle = total > 0 ? angle + (value / total) * 360 : angle;
            if (nextAngle > angle) {
                stops.push(`${palette[index % palette.length]} ${angle}deg ${nextAngle}deg`);
            }
            angle = nextAngle;
        });
        chartElement.style.background = stops.length
            ? `conic-gradient(${stops.join(", ")})`
            : `conic-gradient(${cssValue("--track")} 0deg 360deg)`;
        chartElement.setAttribute(
            "aria-label",
            categories.length
                ? `Storage by category. ${categories.map((category, index) => `${category}: ${formatBytes(values[index])}`).join("; ")}`
                : "No storage category data yet."
        );

        document.querySelectorAll(".category-swatch[data-category-index]").forEach((swatch) => {
            const index = Number.parseInt(swatch.dataset.categoryIndex, 10);
            if (Number.isFinite(index)) swatch.style.backgroundColor = palette[index % palette.length];
        });
    }

    function formatBytes(bytes) {
        const units = ["B", "KB", "MB", "GB", "TB"];
        let value = Number(bytes) || 0;
        let unit = 0;
        while (value >= 1024 && unit < units.length - 1) {
            value /= 1024;
            unit += 1;
        }
        return `${unit === 0 ? Math.round(value) : value.toFixed(2)} ${units[unit]}`;
    }

    function applyTheme(theme) {
        root.dataset.theme = theme;
        const dark = theme === "dark";
        if (themeButton) {
            themeButton.setAttribute("aria-label", dark ? "Switch to light mode" : "Switch to dark mode");
            const icon = themeButton.querySelector(".theme-icon");
            const label = themeButton.querySelector(".theme-label");
            if (icon) icon.textContent = dark ? "☀" : "◐";
            if (label) label.textContent = dark ? "Light mode" : "Dark mode";
        }
        try {
            localStorage.setItem("sfi-theme", theme);
        } catch (error) {
            // Theme still applies to the current page.
        }
        renderCategoryChart();
    }

    if (chartDataElement) {
        try {
            categoryStats = JSON.parse(chartDataElement.textContent || "{}") || {};
        } catch (error) {
            console.error("Could not parse storage category chart data.", error);
            categoryStats = {};
        }
    }

    applyTheme(savedTheme || root.dataset.theme || preferredTheme);
    if (themeButton) {
        themeButton.addEventListener("click", () => {
            applyTheme(root.dataset.theme === "dark" ? "light" : "dark");
        });
    }

    // Keep the right-side section navigator aligned with the section the
    // reader is currently moving through. Intersection ratios were unreliable
    // here because sections have different content heights: a small section
    // could win the ratio comparison even when another section was the target.
    const sections = [...document.querySelectorAll(".dashboard-section[id]")];
    const links = [...document.querySelectorAll(".section-jump-link[href^='#']")];

    if (sections.length && links.length) {
        const sectionById = new Map(sections.map((section) => [section.id, section]));
        let updateQueued = false;

        function setActiveSection(sectionId) {
            if (!sectionById.has(sectionId)) return;
            links.forEach((link) => {
                const active = link.getAttribute("href") === `#${sectionId}`;
                link.classList.toggle("active", active);
                if (active) link.setAttribute("aria-current", "location");
                else link.removeAttribute("aria-current");
            });
        }

        function updateActiveSection() {
            // Pick the section crossing a stable line in the upper-middle of
            // the viewport, rather than comparing intersection ratios.
            const markerY = Math.max(80, window.innerHeight * 0.38);
            let activeSection = sections[0];

            for (const section of sections) {
                const bounds = section.getBoundingClientRect();
                if (bounds.top <= markerY) {
                    activeSection = section;
                } else {
                    break;
                }
            }
            setActiveSection(activeSection.id);
        }

        function scheduleSectionUpdate() {
            if (updateQueued) return;
            updateQueued = true;
            window.requestAnimationFrame(() => {
                updateQueued = false;
                updateActiveSection();
            });
        }

        // Update immediately on a jump, then keep tracking the actual viewport
        // while smooth scrolling completes and when the user scrolls manually.
        links.forEach((link) => {
            link.addEventListener("click", () => {
                const sectionId = link.getAttribute("href").slice(1);
                setActiveSection(sectionId);
            });
        });
        window.addEventListener("scroll", scheduleSectionUpdate, { passive: true });
        window.addEventListener("resize", scheduleSectionUpdate);
        updateActiveSection();
    }
});
