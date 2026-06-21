let scatterChart = null;
let currentScatterData = null;
let currentMod1 = "";
let currentMod2 = "";

function calculatePearsonCorrelation(xs, ys) {
    const n = xs.length;
    if (n < 3) return null;
    const mean_x = xs.reduce((a, b) => a + b, 0) / n;
    const mean_y = ys.reduce((a, b) => a + b, 0) / n;
    let num = 0;
    let den_x = 0;
    let den_y = 0;
    for (let i = 0; i < n; i++) {
        const diff_x = xs[i] - mean_x;
        const diff_y = ys[i] - mean_y;
        num += diff_x * diff_y;
        den_x += diff_x * diff_x;
        den_y += diff_y * diff_y;
    }
    if (den_x === 0 || den_y === 0) return null;
    return num / Math.sqrt(den_x * den_y);
}

function calculateRegressionLine(points) {
    const n = points.length;
    if (n < 3) return null;
    const xs = points.map(p => p.x);
    const ys = points.map(p => p.y);
    const mean_x = xs.reduce((a, b) => a + b, 0) / n;
    const mean_y = ys.reduce((a, b) => a + b, 0) / n;
    let num = 0;
    let den = 0;
    for (let i = 0; i < n; i++) {
        num += (xs[i] - mean_x) * (ys[i] - mean_y);
        den += (xs[i] - mean_x) * (xs[i] - mean_x);
    }
    if (den === 0) return null;
    const slope = num / den;
    const intercept = mean_y - slope * mean_x;
    const min_x = Math.min(...xs);
    const max_x = Math.max(...xs);
    return [
        { x: min_x, y: parseFloat((slope * min_x + intercept).toFixed(1)) },
        { x: max_x, y: parseFloat((slope * max_x + intercept).toFixed(1)) }
    ];
}

function updateScatterChart() {
    if (!currentScatterData) return;
    const thresholdInput = document.getElementById('nonSubThreshold');
    const threshold = thresholdInput ? parseFloat(thresholdInput.value) || 0 : 20;

    const points = currentScatterData.points;
    const abovePoints = points.filter(p => p.x >= threshold && p.y >= threshold);
    const belowPoints = points.filter(p => p.x < threshold || p.y < threshold);

    // Calculate r and regression from above-threshold points only
    const xsAbove = abovePoints.map(p => p.x);
    const ysAbove = abovePoints.map(p => p.y);
    const r = calculatePearsonCorrelation(xsAbove, ysAbove);
    const regressionLine = calculateRegressionLine(abovePoints);

    // Update labels
    document.getElementById('overlapCount').innerText = points.length;
    document.getElementById('analysisCount').innerText = abovePoints.length;
    document.getElementById('correlationVal').innerText = r !== null ? r.toFixed(2) : 'N/A';
    
    document.getElementById('correlationLabel').innerHTML = `Pearson Correlation (${r !== null ? 'r' : 'N/A'}) <span class="d-block small text-muted font-monospace">marks >= ${threshold}%</span>`;
    document.getElementById('analysisCountLabel').innerHTML = `Above-Threshold (N) <span class="d-block small text-muted font-monospace">marks >= ${threshold}%</span>`;

    const ctx = document.getElementById('scatterChartCanvas').getContext('2d');
    if (scatterChart) {
        scatterChart.destroy();
    }

    const datasets = [
        {
            label: `Valid Submissions (>= ${threshold}%)`,
            data: abovePoints,
            backgroundColor: 'rgba(67, 97, 238, 0.65)',
            borderColor: 'rgba(67, 97, 238, 1)',
            borderWidth: 1,
            pointRadius: 6,
            pointHoverRadius: 8,
            type: 'scatter'
        },
        {
            label: `Suspected Non-Submissions (< ${threshold}%)`,
            data: belowPoints,
            backgroundColor: 'rgba(239, 68, 68, 0.65)',
            borderColor: 'rgba(239, 68, 68, 1)',
            borderWidth: 1,
            pointRadius: 6,
            pointHoverRadius: 8,
            type: 'scatter'
        }
    ];

    if (regressionLine && regressionLine.length > 0) {
        datasets.push({
            label: `Regression Line (marks >= ${threshold}%)`,
            data: regressionLine,
            type: 'line',
            borderColor: 'rgba(255, 0, 110, 0.85)',
            borderWidth: 2.5,
            fill: false,
            pointRadius: 0,
            tension: 0
        });
    }

    scatterChart = new Chart(ctx, {
        data: {
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    type: 'linear',
                    min: 0,
                    max: 100,
                    title: {
                        display: true,
                        text: `${currentMod1} Mark (%)`,
                        font: { weight: 'bold', size: 12 }
                    }
                },
                y: {
                    type: 'linear',
                    min: 0,
                    max: 100,
                    title: {
                        display: true,
                        text: `${currentMod2} Mark (%)`,
                        font: { weight: 'bold', size: 12 }
                    }
                }
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'bottom'
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            if (context.dataset.label.indexOf('Regression') === -1) {
                                return `Student: ${currentMod1}: ${context.raw.x}%, ${currentMod2}: ${context.raw.y}%`;
                            }
                            return context.dataset.label;
                        }
                    }
                }
            }
        }
    });
}

function loadScatter(mod1, mod2) {
    const modalEl = document.getElementById('scatterModal');
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();

    document.getElementById('scatterModalLabel').innerText = `${mod1} vs ${mod2} Correlation Scatter Plot`;
    document.getElementById('scatterSpinner').style.display = 'block';
    document.getElementById('scatterContent').style.display = 'none';

    // Reset modal threshold to match global value
    const globalThresholdInput = document.getElementById('globalThreshold');
    const modalThresholdInput = document.getElementById('nonSubThreshold');
    if (globalThresholdInput && modalThresholdInput) {
        modalThresholdInput.value = globalThresholdInput.value;
    }

    currentMod1 = mod1;
    currentMod2 = mod2;

    const queryParams = new URLSearchParams(window.location.search);
    queryParams.set('mod1', mod1);
    queryParams.set('mod2', mod2);
    fetch(`/longitudinal-analytics/scatter-data/?${queryParams.toString()}`)
        .then(res => res.json())
        .then(data => {
            document.getElementById('scatterSpinner').style.display = 'none';
            document.getElementById('scatterContent').style.display = 'block';

            currentScatterData = data;
            updateScatterChart();
        })
        .catch(err => {
            console.error(err);
            document.getElementById('scatterSpinner').innerHTML = '<div class="text-danger fw-bold py-3">Error fetching scatter coordinates.</div>';
        });
}

document.addEventListener("DOMContentLoaded", function() {
    // Enable tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    const thresholdInput = document.getElementById('nonSubThreshold');
    if (thresholdInput) {
        thresholdInput.addEventListener('input', updateScatterChart);
    }

    // 1. Cohort Lines
    const cohortLinesData = JSON.parse(document.getElementById('cohort-lines-data').textContent);
    const ctxCohort = document.getElementById('cohortLinesCanvas').getContext('2d');
    new Chart(ctxCohort, {
        type: 'line',
        data: {
            labels: ['Level 3', 'Level 4', 'Level 5', 'Level 6', 'Level 7'],
            datasets: cohortLinesData
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    min: 0,
                    max: 100,
                    title: { display: true, text: 'Mean Mark (%)', font: { weight: 'bold' } }
                },
                x: {
                    title: { display: true, text: 'Academic Level', font: { weight: 'bold' } }
                }
            },
            plugins: {
                legend: { position: 'bottom' }
            }
        }
    });

    // 2. Transitions Stacked Bar
    const transitionsData = JSON.parse(document.getElementById('transitions-data').textContent);
    const ctxTrans = document.getElementById('transitionsCanvas').getContext('2d');
    new Chart(ctxTrans, {
        type: 'bar',
        data: {
            labels: transitionsData.labels,
            datasets: [
                {
                    label: 'Declining (<= -3)',
                    data: transitionsData.declining,
                    backgroundColor: '#ef4444' // Red
                },
                {
                    label: 'Stable (-3 to +3)',
                    data: transitionsData.stable,
                    backgroundColor: '#3b82f6' // Blue
                },
                {
                    label: 'Improving (>= +3)',
                    data: transitionsData.improving,
                    backgroundColor: '#10b981' // Green
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    stacked: true,
                    title: { display: true, text: 'Level Transition', font: { weight: 'bold' } }
                },
                y: {
                    stacked: true,
                    title: { display: true, text: 'Number of Students', font: { weight: 'bold' } },
                    ticks: { stepSize: 1 }
                }
            },
            plugins: {
                legend: { position: 'bottom' }
            }
        }
    });

    // 3. Entry Route Side-by-Side Bar
    const entryRouteData = JSON.parse(document.getElementById('entry-route-data').textContent);
    const ctxRoute = document.getElementById('entryRouteCanvas').getContext('2d');
    new Chart(ctxRoute, {
        type: 'bar',
        data: {
            labels: entryRouteData.levels.map(l => `Level ${l}`),
            datasets: [
                {
                    label: 'Level 3 Entrants',
                    data: entryRouteData.l3_entrants,
                    backgroundColor: '#4361ee'
                },
                {
                    label: 'Direct Entrants',
                    data: entryRouteData.direct_entrants,
                    backgroundColor: '#ff006e'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    min: 0,
                    max: 100,
                    title: { display: true, text: 'Mean Mark (%)', font: { weight: 'bold' } }
                }
            },
            plugins: {
                legend: { position: 'bottom' }
            }
        }
    });
});
