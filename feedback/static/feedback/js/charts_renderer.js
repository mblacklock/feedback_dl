// Chart.js rendering for feedback sheet visualizations
// Expects: charts array and categories array to be passed in

function renderFeedbackCharts(charts, categories) {
    if (!charts || charts.length === 0) {
        return;
    }

    charts.forEach((chart, index) => {
        const ctx = document.getElementById(`chart-${index + 1}`);
        if (!ctx) return;

        // With Bootstrap ratio container in the template, we don't set the
        // canvas internal pixel dimensions in JS; the container controls sizing
        // and Chart.js will respect the container when maintainAspectRatio is true.

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
            datasets: [
                {
                    label: 'Your marks',
                    data: chart.categories.map(() => Math.floor(Math.random() * 30) + 60), // Random 60-90%
                    borderColor: 'rgba(8, 163, 34, 0.5)',
                    backgroundColor: 'rgba(8, 163, 34, 0.4)'
                },
                {
                    label: 'Class Average',
                    data: chart.categories.map(() => Math.floor(Math.random() * 30) + 60), // Random 60-90%
                    borderColor: 'rgba(54, 162, 235, 0.5)',
                    backgroundColor: 'rgba(54, 162, 235, 0.2)',
                }
            ]
        },
        options: {
            // Fill the container's pixel dimensions (we use a fixed-height container)
            maintainAspectRatio: false,
            scales: {
                r: {
                    beginAtZero: true,
                    max: 100,
                    // Make category (point) labels larger for readability
                    pointLabels: {
                        font: {
                            size: 14
                        }
                    },
                    ticks: {
                        stepSize: 20
                    }
                    
                }
            },
            layout: {
                padding: 0
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'bottom',
                    labels: {
                        font: {
                            size: 14
                        },
                        boxHeight: 1
                    }
                }
            },
        }
    });
}

function renderHistogramChart(ctx, chart) {
    // Example student mark (percent). Use provided value if available.
    const studentMark = (chart.student_mark !== undefined) ? chart.student_mark : 75;

    // Plugin draws a vertical line at the student's mark across the chart area.
    const studentLinePlugin = {
        id: 'studentLine',
        afterDatasetsDraw: function(chartInstance) {
            const opts = chartInstance.options.plugins && chartInstance.options.plugins.studentLine ? chartInstance.options.plugins.studentLine : {};
            const mark = (typeof opts.mark === 'number') ? opts.mark : studentMark;
            const color = opts.color || 'rgba(255, 99, 132, 0.9)';
            const lineWidth = opts.lineWidth || 2;
            const ctx2 = chartInstance.ctx;
            const area = chartInstance.chartArea;
            if (!area) return;

            // Try to map the mark into the pixel space using the bar elements so
            // gaps and variable bin widths are accounted for visually.
            try {
                const meta = chartInstance.getDatasetMeta(0);
                const bars = meta && meta.data ? meta.data : null;
                const labels = chartInstance.data && chartInstance.data.labels ? chartInstance.data.labels : [];

                if (bars && bars.length === labels.length && labels.length > 0) {
                    // Parse label ranges like '0-39%' into numeric ranges.
                    const ranges = labels.map(lbl => {
                        const s = String(lbl).replace(/%/g, '').trim();
                        const parts = s.split('-');
                        if (parts.length === 2) {
                            const a = parseFloat(parts[0]);
                            const b = parseFloat(parts[1]);
                            if (!isNaN(a) && !isNaN(b)) return {start: a, end: b};
                        }
                        // Fallback: treat single number as a tiny bin
                        const v = parseFloat(s);
                        return {start: isNaN(v) ? 0 : v, end: isNaN(v) ? 100 : v};
                    });

                    // Find the bin that contains the mark
                    let binIndex = ranges.findIndex(r => mark >= r.start && mark <= r.end);
                    if (binIndex === -1) {
                        // if out of range, clamp to nearest bin
                        if (mark < ranges[0].start) binIndex = 0;
                        else binIndex = ranges.length - 1;
                    }

                    const bar = bars[binIndex];
                    if (bar) {
                        const barLeft = bar.x - (bar.width || 0) / 2;
                        const barWidth = (bar.width || 0);
                        const r = ranges[binIndex];
                        const denom = (r.end - r.start) || 1;
                        const frac = (mark - r.start) / denom;
                        const x = barLeft + Math.max(0, Math.min(1, frac)) * barWidth;
                        ctx2.save();
                        // dashed line if requested
                        const dash = (opts.dash && Array.isArray(opts.dash)) ? opts.dash : [6,4];
                        ctx2.setLineDash(dash);
                        ctx2.beginPath();
                        // draw full vertical line from top of chart area to bottom
                        // (label will be positioned above the bars to avoid overlap)
                        ctx2.moveTo(x, area.top);
                        ctx2.lineTo(x, area.bottom);
                        ctx2.lineWidth = lineWidth;
                        ctx2.strokeStyle = color;
                        ctx2.stroke();
                        ctx2.setLineDash([]);

                        // draw label above the line inside the top padding
                        const labelText = (typeof opts.labelText === 'string') ? opts.labelText : `Your mark`;
                        const fontSize = opts.labelFontSize || 12;
                        // bold the label so 'You' stands out
                        ctx2.font = `bold ${fontSize}px sans-serif`;
                        ctx2.fillStyle = opts.labelColor || color;
                        const textWidth = ctx2.measureText(labelText).width;
                        // clamp text within chart area
                        let textX = x - textWidth / 2;
                        textX = Math.max(area.left + 4, Math.min(area.right - textWidth - 4, textX));
                        // position the label above the bars (above chartArea.top) if possible
                        const labelOffsetAbove = (opts.labelOffsetAbove !== undefined) ? opts.labelOffsetAbove : 8;
                        let textY = area.top - labelOffsetAbove;
                        // if that would draw outside the canvas, fall back to top padding inside chart
                        if (textY < 10) {
                            textY = area.top + (opts.labelOffsetY || 14);
                        }
                        ctx2.fillText(labelText, textX, textY);

                        ctx2.restore();
                        return;
                    }
                }
            } catch (e) {
                // fallback to linear mapping below
            }

            // Fallback: linear mapping across 0-100
            const xFallback = area.left + (mark / 100) * (area.right - area.left);
            ctx2.save();
            const dashFallback = (opts.dash && Array.isArray(opts.dash)) ? opts.dash : [6,4];
            ctx2.setLineDash(dashFallback);
            ctx2.beginPath();
            // draw full vertical line from top to bottom; label placed above bars
            ctx2.moveTo(xFallback, area.top);
            ctx2.lineTo(xFallback, area.bottom);
            ctx2.lineWidth = lineWidth;
            ctx2.strokeStyle = color;
            ctx2.stroke();
            ctx2.setLineDash([]);

            // label
            const labelTextFb = (typeof opts.labelText === 'string') ? opts.labelText : `Your mark`;
            const fontSizeFb = opts.labelFontSize || 12;
            // bold the fallback label as well
            ctx2.font = `bold ${fontSizeFb}px sans-serif`;
            ctx2.fillStyle = opts.labelColor || color;
            const textWidthFb = ctx2.measureText(labelTextFb).width;
            let textXfb = xFallback - textWidthFb / 2;
            textXfb = Math.max(area.left + 4, Math.min(area.right - textWidthFb - 4, textXfb));
            const labelOffsetAboveFb = (opts.labelOffsetAbove !== undefined) ? opts.labelOffsetAbove : 8;
            let textYfb = area.top - labelOffsetAboveFb;
            if (textYfb < 10) {
                textYfb = area.top + (opts.labelOffsetY || 14);
            }
            ctx2.fillText(labelTextFb, textXfb, textYfb);
            ctx2.restore();
        }
    };

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
            // Fill the container's pixel dimensions (we use a fixed-height container)
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Number of Students',
                        font: {
                            size: 16
                        }
                    },
                    ticks: {
                        font: {
                            size: 16
                        }
                    },
                    grid: {
                        display: false
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: chart.data_source === 'overall' ? 'Overall Mark Range' : `${chart.data_source} Mark Range`,
                        font: {
                            size: 16
                        }
                    },
                    ticks: {
                        font: {
                            size: 16
                        }
                    },
                    grid: {
                        display: false
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                },
                title: {
                    display: false
                },
                // options for the student line plugin
                studentLine: {
                    mark: studentMark,
                    color: 'rgba(255, 99, 132, 0.9)',
                    lineWidth: 2
                }
            },
            layout: {
                padding: 40
            }
        }
        ,
        plugins: [studentLinePlugin]
    });
}
