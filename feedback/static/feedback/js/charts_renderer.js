// Chart.js rendering for feedback sheet visualizations
// Expects: charts array and categories array to be passed in

function renderFeedbackCharts(charts, categories) {
    if (!charts || charts.length === 0) {
        return;
    }

    charts.forEach((chart, index) => {
        const ctx = document.getElementById(`chart-${index + 1}`);
        if (!ctx) return;
        
        if (chart.type === 'radar') {
            renderRadarChart(ctx, chart);
        } else if (chart.type === 'histogram') {
            renderHistogramChart(ctx, chart);
        }
    });
}

function renderRadarChart(ctx, chart) {
    // Use short names if available, otherwise use full category labels
    const labels = chart.categories.map(cat => {
        return chart.category_short_names && chart.category_short_names[cat] 
            ? chart.category_short_names[cat] 
            : cat;
    });
    
    new Chart(ctx, {
        type: 'radar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Example Student Performance',
                data: chart.categories.map(() => Math.floor(Math.random() * 30) + 60), // Random 60-90%
                borderColor: 'rgb(75, 192, 192)',
                backgroundColor: 'rgba(75, 192, 192, 0.2)'
            }]
        },
        options: {
            scales: {
                r: {
                    beginAtZero: true,
                    max: 100,
                    ticks: {
                        stepSize: 20
                    }
                }
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'bottom',
                    labels: {
                        boxHeight: 6
                    }
                }
            }
        }
    });
}

function renderHistogramChart(ctx, chart) {
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['0-39%', '40-49%', '50-59%', '60-69%', '70-100%'],
            datasets: [{
                label: 'Number of Students',
                data: [2, 5, 12, 18, 8], // Example distribution
                backgroundColor: [
                    'rgba(255, 99, 132, 0.5)',
                    'rgba(54, 162, 235, 0.5)',
                    'rgba(54, 162, 235, 0.5)',
                    'rgba(54, 162, 235, 0.5)',
                    'rgba(8, 163, 34, 0.5)'
                ],
                borderColor: [
                    'rgba(255, 99, 132, 0.5)',
                    'rgba(54, 162, 235, 0.5)',
                    'rgba(54, 162, 235, 0.5)',
                    'rgba(54, 162, 235, 0.5)',
                    'rgba(8, 163, 34, 0.5)'
                ],
                borderWidth: 1
            }]
        },
        options: {
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Number of Students'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: chart.data_source === 'overall' ? 'Overall Mark Range' : `${chart.data_source} Mark Range`
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                },
                title: {
                    display: false
                }
            }
        }
    });
}
