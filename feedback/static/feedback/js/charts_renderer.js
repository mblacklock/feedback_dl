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
        } else if (chart.type === 'histogram' || chart.type === 'bar') {
            renderHistogramChart(ctx, chart);
        }
    });
}

function renderRadarChart(ctx, chart) {
    new Chart(ctx, {
        type: 'radar',
        data: {
            labels: chart.categories,
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
                    position: 'top'
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
                    'rgba(255, 159, 64, 0.5)',
                    'rgba(255, 205, 86, 0.5)',
                    'rgba(75, 192, 192, 0.5)',
                    'rgba(54, 162, 235, 0.5)'
                ],
                borderColor: [
                    'rgb(255, 99, 132)',
                    'rgb(255, 159, 64)',
                    'rgb(255, 205, 86)',
                    'rgb(75, 192, 192)',
                    'rgb(54, 162, 235)'
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
