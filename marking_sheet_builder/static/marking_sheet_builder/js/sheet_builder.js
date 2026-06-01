const columnLabels = {
    numeric: "Numeric mark",
    rubric: "Rubric mark",
    information: "Information",
    feedback: "Feedback comment",
};
const defaultTitles = {
    numeric: "Mark",
    rubric: "Rubric grade",
    information: "Notes",
    feedback: "Feedback",
};

const initialConfig = JSON.parse(document.getElementById("initialConfig").textContent);
const state = {
    columns: initialConfig.columns || [
        { type: "numeric", title: "Numeric mark", max_mark: 50 },
        { type: "rubric", title: "Rubric grade", max_mark: 50, subdivision: "none", marks: {} },
        { type: "feedback", title: "Feedback" },
    ]
};

const previewHeader = document.getElementById("previewHeader");
const previewBody = document.getElementById("previewBody");
const columnCount = document.getElementById("columnCount");
const markTotal = document.getElementById("markTotal");
const markTotalValue = document.getElementById("markTotalValue");

document.getElementById("nameMode").value = initialConfig.name_mode || "full";
document.getElementById("rowCount").value = initialConfig.rows || 100;
document.getElementById("maxMark").value = initialConfig.max_mark || 100;
document.getElementById("degreeLevel").value = initialConfig.degree_level || "BEng";

function sortColumns(columns) {
    return [
        ...columns.filter(c => c.type !== "feedback"),
        ...columns.filter(c => c.type === "feedback")
    ];
}

function renderPreview() {
    state.columns = sortColumns(state.columns);
    
    let needsFetch = false;
    state.columns.forEach((col, index) => {
        if (col.type === "rubric" && (!col.marks || Object.keys(col.marks).length === 0)) {
            needsFetch = true;
            fetchColumnDefaultMarks(col, index).then(() => {
                renderPreview();
            });
        }
    });
    
    if (needsFetch) return;

    const baseHeaders = document.getElementById("nameMode").value === "split"
        ? ["Student ID", "Last Name", "First Name"]
        : ["Student ID", "Student Name"];
    const outputHeaders = [`Mark (${document.getElementById("maxMark").value || 0})`, "%"];

    const nonFeedback = state.columns.filter(c => c.type !== "feedback");
    const feedback = state.columns.filter(c => c.type === "feedback");

    const headers = [
        ...baseHeaders,
        ...nonFeedback.map((column) => displayColumnTitle(column)),
        ...outputHeaders,
        ...feedback.map((column) => displayColumnTitle(column))
    ];

    previewHeader.innerHTML = [
        ...baseHeaders.map((header) => `<th class="sheet-fixed-header">${escapeHtml(header)}</th>`),
        ...nonFeedback.map((column) => renderEditableHeader(column, state.columns.indexOf(column))),
        ...outputHeaders.map((header) => `<th class="sheet-output-header">${escapeHtml(header)}</th>`),
        ...feedback.map((column) => renderEditableHeader(column, state.columns.indexOf(column)))
    ].join("");

    bindHeaderEditors();
    previewBody.innerHTML = "";
    for (let rowIndex = 0; rowIndex < 5; rowIndex += 1) {
        const row = document.createElement("tr");
        row.innerHTML = headers.map((_, index) => {
            let isRubric = false;
            const baseLen = baseHeaders.length;
            const nonFeedbackLen = nonFeedback.length;
            const outputLen = outputHeaders.length;
            
            if (index >= baseLen && index < baseLen + nonFeedbackLen) {
                const col = nonFeedback[index - baseLen];
                isRubric = col.type === "rubric";
            }
            return `<td><span class="cell-pill ${isRubric ? "dropdown" : ""}"></span></td>`;
        }).join("");
        previewBody.appendChild(row);
    }
    columnCount.textContent = `${headers.length} columns`;
    updateMarkTotal();
    renderRubricSettings();
}

function renderEditableHeader(column, index) {
    return `
        <th>
            <div class="sheet-header-editor" data-column-index="${index}" data-column-type="${column.type}">
                
                <div style="display: flex; flex-direction: column; width: 100%;">
                    <span class="sheet-editor-label">Category Title</span>
                    <input class="form-control form-control-sm column-title-input" value="${escapeHtml(column.title)}" aria-label="Column title">
                </div>
                
                <div style="display: flex; flex-direction: column; width: 100%;">
                    <span class="sheet-editor-label">Type</span>
                    <select class="form-select form-select-sm column-type-select" aria-label="Column type">
                        ${Object.entries(columnLabels).map(([value, label]) => `<option value="${value}" ${value === column.type ? "selected" : ""}>${label}</option>`).join("")}
                    </select>
                </div>
                
                <div class="mark-settings" style="display: flex; flex-direction: column; width: 100%;">
                    <span class="sheet-editor-label">Max Mark</span>
                    <input class="form-control form-control-sm column-max-input" type="number" min="1" max="10000" value="${escapeHtml(column.max_mark || 100)}" aria-label="Column max">
                </div>
                
                <div class="rubric-settings" style="display: flex; flex-direction: column; width: 100%;">
                    <span class="sheet-editor-label">Subdivision</span>
                    <select class="form-select form-select-sm column-subdivision-select" aria-label="Rubric boundaries">
                        <option value="none" ${column.subdivision === "none" ? "selected" : ""}>Standard</option>
                        <option value="high_low" ${column.subdivision === "high_low" ? "selected" : ""}>High / low</option>
                        <option value="high_mid_low" ${column.subdivision === "high_mid_low" ? "selected" : ""}>High / mid / low</option>
                    </select>
                </div>
                
                <div class="sheet-header-actions">
                    <div class="drag-column-handle" title="Drag to reorder">⋮⋮</div>
                    <button class="btn btn-light btn-sm remove-column-button" type="button" aria-label="Remove column">Remove</button>
                </div>
            </div>
        </th>
    `;
}

function bindHeaderEditors() {
    document.querySelectorAll(".sheet-header-editor").forEach((editor) => {
        const th = editor.closest("th");
        const index = Number.parseInt(editor.dataset.columnIndex, 10);
        const handle = editor.querySelector(".drag-column-handle");

        handle.addEventListener("mousedown", () => {
            th.setAttribute("draggable", "true");
        });
        handle.addEventListener("mouseup", () => {
            th.setAttribute("draggable", "false");
        });

        th.addEventListener("dragstart", (event) => {
            event.dataTransfer.setData("text/plain", index);
            th.classList.add("dragging");
            event.dataTransfer.effectAllowed = "move";
        });

        th.addEventListener("dragend", () => {
            th.classList.remove("dragging");
            th.setAttribute("draggable", "false");
            document.querySelectorAll(".preview-table th").forEach(el => {
                el.classList.remove("drag-over");
            });
        });

        th.addEventListener("dragover", (event) => {
            event.preventDefault();
            event.dataTransfer.dropEffect = "move";
        });

        th.addEventListener("dragenter", (event) => {
            event.preventDefault();
            th.classList.add("drag-over");
        });

        th.addEventListener("dragleave", () => {
            th.classList.remove("drag-over");
        });

        th.addEventListener("drop", (event) => {
            event.preventDefault();
            th.classList.remove("drag-over");
            const sourceIndex = Number.parseInt(event.dataTransfer.getData("text/plain"), 10);
            const targetIndex = index;

            if (sourceIndex !== targetIndex && !isNaN(sourceIndex)) {
                const draggedCol = state.columns[sourceIndex];
                state.columns.splice(sourceIndex, 1);
                state.columns.splice(targetIndex, 0, draggedCol);
                renderPreview();
            }
        });

        editor.querySelector(".column-title-input").addEventListener("input", (event) => {
            state.columns[index].title = event.target.value;
            updateMarkTotal();
            renderRubricSettings();
        });
        editor.querySelector(".column-max-input").addEventListener("input", (event) => {
            state.columns[index].max_mark = event.target.value;
            updateMarkTotal();
        });
        editor.querySelector(".column-max-input").addEventListener("change", (event) => {
            if (state.columns[index].type === "rubric") {
                fetchColumnDefaultMarks(state.columns[index], index).then(() => {
                    renderPreview();
                });
            } else {
                renderPreview();
            }
        });
        editor.querySelector(".column-subdivision-select").addEventListener("change", (event) => {
            state.columns[index].subdivision = event.target.value;
            fetchColumnDefaultMarks(state.columns[index], index).then(() => {
                renderPreview();
            });
        });
        editor.querySelector(".column-type-select").addEventListener("change", (event) => {
            state.columns[index].type = event.target.value;
            if ((event.target.value === "numeric" || event.target.value === "rubric") && !state.columns[index].max_mark) {
                state.columns[index].max_mark = remainingAssessedMark();
            }
            if (event.target.value === "rubric" && !state.columns[index].subdivision) {
                state.columns[index].subdivision = "none";
            }
            if (!state.columns[index].title.trim()) {
                state.columns[index].title = defaultTitles[event.target.value];
            }
            if (event.target.value === "rubric") {
                fetchColumnDefaultMarks(state.columns[index], index).then(() => {
                    renderPreview();
                });
            } else {
                renderPreview();
            }
        });
        editor.querySelector(".remove-column-button").addEventListener("click", () => {
            state.columns.splice(index, 1);
            renderPreview();
        });
    });
}

function updateMarkTotal() {
    const total = Number.parseInt(document.getElementById("maxMark").value, 10) || 0;
    const numericTotal = state.columns.reduce((sum, column) => {
        if (column.type !== "numeric" && column.type !== "rubric") {
            return sum;
        }
        return sum + (Number.parseInt(column.max_mark, 10) || 0);
    }, 0);
    markTotalValue.textContent = `${numericTotal} / ${total}`;
    markTotal.classList.toggle("invalid", numericTotal !== total);
}

function remainingAssessedMark() {
    const total = Number.parseInt(document.getElementById("maxMark").value, 10) || 100;
    const used = state.columns.reduce((sum, column) => {
        if (column.type !== "numeric" && column.type !== "rubric") {
            return sum;
        }
        return sum + (Number.parseInt(column.max_mark, 10) || 0);
    }, 0);
    return Math.max(1, total - used);
}

function buildPayload() {
    return {
        name_mode: document.getElementById("nameMode").value,
        degree_level: document.getElementById("degreeLevel").value,
        rows: document.getElementById("rowCount").value,
        max_mark: document.getElementById("maxMark").value,
        columns: state.columns,
    };
}

function displayColumnTitle(column) {
    const title = column.title || columnLabels[column.type];
    if (column.type === "numeric" || column.type === "rubric") {
        return `${title} (${column.max_mark || 0})`;
    }
    return title;
}

function escapeHtml(value) {
    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

document.querySelectorAll("[data-add-column]").forEach((button) => {
    button.addEventListener("click", () => {
        const type = button.dataset.addColumn;
        const column = { type, title: defaultTitles[type] };
        if (type === "numeric" || type === "rubric") {
            column.max_mark = remainingAssessedMark();
        }
        if (type === "rubric") {
            column.subdivision = "none";
            column.marks = {};
            state.columns.push(column);
            fetchColumnDefaultMarks(column, state.columns.length - 1).then(() => {
                renderPreview();
            });
        } else {
            state.columns.push(column);
            renderPreview();
        }
    });
});

["nameMode", "rowCount", "maxMark"].forEach((id) => {
    document.getElementById(id).addEventListener("input", renderPreview);
    document.getElementById(id).addEventListener("change", renderPreview);
});
document.getElementById("degreeLevel").addEventListener("change", () => {
    refreshAllRubricColumns();
});

document.getElementById("builderForm").addEventListener("submit", (event) => {
    const payload = buildPayload();
    const total = Number.parseInt(payload.max_mark, 10) || 0;
    const numericTotal = payload.columns.reduce((sum, column) => {
        if (column.type !== "numeric" && column.type !== "rubric") {
            return sum;
        }
        return sum + (Number.parseInt(column.max_mark, 10) || 0);
    }, 0);
    if (numericTotal !== total) {
        event.preventDefault();
        markTotal.classList.add("invalid");
        markTotal.scrollIntoView({ behavior: "smooth", block: "center" });
        return;
    }

    // Check for customizer grade band errors
    const hasErrors = document.querySelectorAll(".customizer-error-msg[style*='display: block']").length > 0;
    if (hasErrors) {
        event.preventDefault();
        alert("Please fix all grade boundary mark validation errors before downloading the template.");
        const firstErr = document.querySelector(".customizer-error-msg[style*='display: block']");
        if (firstErr) {
            firstErr.scrollIntoView({ behavior: "smooth", block: "center" });
        }
        return;
    }

    document.getElementById("builderPayload").value = JSON.stringify(buildPayload());
});

function fetchColumnDefaultMarks(column, index) {
    const degreeLevel = document.getElementById("degreeLevel").value;
    const maxMarks = column.max_mark || 100;
    const subdivision = column.subdivision || "none";
    
    return fetch(`/marking-sheet-builder/api/grade-bands/?max_marks=${maxMarks}&subdivision=${subdivision}&degree_level=${encodeURIComponent(degreeLevel)}`)
        .then(response => response.json())
        .then(data => {
            if (data.bands) {
                const marks = {};
                data.bands.forEach(band => {
                    marks[band.grade] = band.marks;
                });
                column.marks = marks;
                renderRubricSettings();
            }
        })
        .catch(err => console.error("Error fetching default marks:", err));
}

function refreshAllRubricColumns() {
    const promises = [];
    state.columns.forEach((column, index) => {
        if (column.type === "rubric") {
            promises.push(fetchColumnDefaultMarks(column, index));
        }
    });
    return Promise.all(promises).then(() => {
        renderPreview();
    });
}

function validateCardInputs(cardEl, col) {
    const degreeLevel = document.getElementById("degreeLevel").value;
    const isMLevel = degreeLevel && degreeLevel.trim().toLowerCase().startsWith('m');
    const maxMark = col.max_mark || 100;
    
    let firstErrorMsg = "";
    let previousVal = null;
    let previousGrade = null;
    
    cardEl.querySelectorAll(".custom-mark-input").forEach((input) => {
        const grade = input.dataset.grade;
        const val = Number.parseInt(input.value, 10);
        
        input.classList.remove("border-danger", "text-danger");
        
        if (!isNaN(val)) {
            const expectedGrade = getExpectedBaseGrade(grade);
            const pct = (val / maxMark) * 100;
            const actualGrade = getGradeForPercentage(pct, isMLevel);
            
            if (actualGrade !== expectedGrade) {
                let minMark = null;
                let maxMarkLimit = null;
                for (let m = 0; m <= maxMark; m++) {
                    const p = (m / maxMark) * 100;
                    if (getGradeForPercentage(p, isMLevel) === expectedGrade) {
                        if (minMark === null) minMark = m;
                        maxMarkLimit = m;
                    }
                }
                
                input.classList.add("border-danger", "text-danger");
                if (!firstErrorMsg) {
                    let gradeRangeStr = "";
                    if (expectedGrade === "1st") gradeRangeStr = "70-100%";
                    else if (expectedGrade === "2:1") gradeRangeStr = "60-69%";
                    else if (expectedGrade === "2:2") gradeRangeStr = "50-59%";
                    else if (expectedGrade === "3rd") gradeRangeStr = "40-49%";
                    else gradeRangeStr = isMLevel ? "0-49%" : "0-39%";
                    
                    firstErrorMsg = `⚠️ Error: '${grade}' mark must be between ${minMark} and ${maxMarkLimit} to fall within the expected ${expectedGrade} band (${gradeRangeStr}).`;
                }
            } else {
                // Check sequential ordering if individual bounds pass
                if (previousVal !== null) {
                    const currentBase = getExpectedBaseGrade(grade);
                    const previousBase = getExpectedBaseGrade(previousGrade);
                    
                    if (currentBase !== previousBase) {
                        // Cross-band: must be strictly less
                        if (val >= previousVal) {
                            input.classList.add("border-danger", "text-danger");
                            if (!firstErrorMsg) {
                                firstErrorMsg = `⚠️ Error: '${grade}' mark (${val}) must be strictly less than the higher '${previousGrade}' band mark (${previousVal}).`;
                            }
                        }
                    } else {
                        // Within same band: must be less than or equal
                        if (val > previousVal) {
                            input.classList.add("border-danger", "text-danger");
                            if (!firstErrorMsg) {
                                firstErrorMsg = `⚠️ Error: '${grade}' mark (${val}) cannot be higher than the '${previousGrade}' mark (${previousVal}).`;
                            }
                        }
                    }
                }
            }
            
            previousVal = val;
            previousGrade = grade;
        }
    });
    
    const errorEl = cardEl.querySelector(".customizer-error-msg");
    if (errorEl) {
        if (firstErrorMsg) {
            errorEl.textContent = firstErrorMsg;
            errorEl.style.display = "block";
        } else {
            errorEl.style.display = "none";
            errorEl.textContent = "";
        }
    }
}

function renderRubricSettings() {
    const rubricCols = state.columns.filter(c => c.type === "rubric");
    const card = document.getElementById("rubricBoundariesCustomizerCard");
    const container = document.getElementById("rubricCustomizersContainer");
    
    if (!card || !container) return;
    
    if (rubricCols.length === 0) {
        card.style.display = "none";
        return;
    }
    
    card.style.display = "block";
    
    container.innerHTML = rubricCols.map((col) => {
        const originalIndex = state.columns.indexOf(col);
        const marks = col.marks || {};
        
        const inputsHtml = Object.entries(marks).map(([grade, val]) => {
            return `
                <div class="d-flex flex-column align-items-center gap-1 p-2 rounded bg-white text-center" style="border: 1px solid var(--brand-border-light); flex: 1 1 0px; min-width: 75px; max-width: 120px;">
                    <span class="fw-bold text-secondary text-truncate text-center w-100" style="font-size: 0.7rem; line-height: 1.2;" title="${escapeHtml(grade)}">${escapeHtml(grade)}</span>
                    <input type="number" class="form-control form-control-sm text-center custom-mark-input p-1" 
                           style="font-size: 0.85rem; font-weight: 600; max-width: 55px; border-radius: 4px;"
                           data-column-index="${originalIndex}" 
                           data-grade="${escapeHtml(grade)}" 
                           value="${val}" min="0" max="${col.max_mark || 100}" aria-label="${escapeHtml(grade)} marks">
                </div>
            `;
        }).join("");
        
        return `
            <div class="p-3 rounded-3 rubric-card" style="background: #f8fafc; border: 1px solid var(--brand-border-light);">
                <div class="d-flex justify-content-between align-items-center mb-3 border-bottom pb-2">
                    <h6 class="fw-bold text-dark mb-0 brand-font">
                        📍 ${escapeHtml(col.title || "Rubric grade")} <span class="badge bg-secondary-subtle text-black ms-2">${col.max_mark || 0} marks</span>
                    </h6>
                    <span class="text-muted small">${col.subdivision === "none" ? "Standard" : col.subdivision === "high_low" ? "High / Low" : "High / Mid / Low"}</span>
                </div>
                <div class="d-flex flex-wrap gap-2">
                    ${inputsHtml}
                </div>
                <div class="customizer-error-msg text-danger mt-2 small" style="display: none; font-weight: 500;"></div>
            </div>
        `;
    }).join("");
    
    container.querySelectorAll(".custom-mark-input").forEach((input) => {
        input.addEventListener("input", (event) => {
            const colIndex = Number.parseInt(event.target.dataset.columnIndex, 10);
            const grade = event.target.dataset.grade;
            const val = Number.parseInt(event.target.value, 10);
            if (!isNaN(val) && colIndex >= 0 && colIndex < state.columns.length) {
                const col = state.columns[colIndex];
                col.marks[grade] = val;
            }
            const cardEl = event.target.closest(".rubric-card");
            const colIndexForCard = Number.parseInt(event.target.dataset.columnIndex, 10);
            if (cardEl && colIndexForCard >= 0 && colIndexForCard < state.columns.length) {
                validateCardInputs(cardEl, state.columns[colIndexForCard]);
            }
        });
    });

    // Run validation initially for each rendered card
    container.querySelectorAll(".rubric-card").forEach((cardEl, idx) => {
        const col = rubricCols[idx];
        validateCardInputs(cardEl, col);
    });
}

renderPreview();
