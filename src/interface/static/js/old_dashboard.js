
document.addEventListener("DOMContentLoaded", () => {
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
