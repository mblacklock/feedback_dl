/**
 * JavaScript logic for the Confirm Mappings page.
 * Manages category row addition, removal, type changes, rubric bands updating,
 * and form validation behaviors.
 */
(function() {
    const config = window.confirmMappingsConfig || {};
    const ALL_RUBRIC_MARKS = config.allRubricMarks || {};
    const RUBRIC_BANDS_URL = config.rubricBandsUrl || "";
    let availableHeaders = config.availableHeaders || [];
    let nextRowIdx = config.nextRowIdx || 0;
    const debounceTimers = {};

    function currentSubdivision(idx) {
        const panel = document.getElementById(`rubric-panel-${idx}`);
        return panel ? (panel.getAttribute('data-subdivision') || 'none') : 'none';
    }

    function currentMaxMarks(idx) {
        const input = document.querySelector(`input[name="max_${idx}"]`);
        return input ? (parseInt(input.value, 10) || 100) : 100;
    }

    function currentDegreeLevel() {
        const input = document.querySelector('select[name="degree_level"]');
        return input ? input.value : 'BEng';
    }

    /** Render a rubric panel from a pre-fetched bands array. */
    function renderBands(container, idx, bands) {
        container.innerHTML = bands.map((band, bandIdx) => `
            <div style="background:white;border:1px solid #e2e8f0;border-radius:6px;padding:4px 7px;display:flex;flex-direction:column;align-items:center;gap:3px;min-width:62px;text-align:center;">
                <div style="font-size:.7rem;font-weight:600;color:#64748b;white-space:nowrap;">${band.grade}</div>
                <input type="number"
                    name="rubric_mark_${idx}_${bandIdx}"
                    value="${band.marks}"
                    class="form-control form-control-sm"
                    style="width:45px;font-weight:700;color:#1e3a8a;text-align:center;padding:1px;height:24px;margin:0;font-size:0.8rem;">
            </div>`).join('');
    }

    /**
     * Fetch fresh bands from the server and render them into the panel.
     * Always uses the current max_marks input value so the result is
     * guaranteed to be consistent with whatever the user has typed.
     * Debounced per-row to avoid hammering the server while typing.
     */
    function fetchAndRenderBands(idx, panel, subdivision, debounceMs = 0) {
        clearTimeout(debounceTimers[idx]);
        debounceTimers[idx] = setTimeout(() => {
            const maxMarks = currentMaxMarks(idx);
            const container = panel.querySelector('.rubric-bands-container');
            if (!container) return;
            fetch(`${RUBRIC_BANDS_URL}?max_marks=${maxMarks}&subdivision=${subdivision}&degree_level=${encodeURIComponent(currentDegreeLevel())}`)
                .then(r => r.json())
                .then(bands => renderBands(container, idx, bands))
                .catch(() => {/* silent — leave existing values in place */ });
        }, debounceMs);
    }


    // ── Generalized Event Binders ────────────────────────────────────────────
    function bindTypeSelectEvent(select) {
        select.addEventListener('change', function () {
            const idx = this.getAttribute('data-idx');
            const type = this.value;
            const maxContainer = document.querySelector(`.max-marks-container-${idx}`);
            const maxInput = document.querySelector(`input[name="max_${idx}"]`);
            const unitContainer = document.querySelector(`.unit-container-${idx}`);
            const unitInput = document.querySelector(`input[name="unit_${idx}"]`);
            const panel = document.getElementById(`rubric-panel-${idx}`);

            if (type === 'information' || type === 'feedback_only') {
                if (maxContainer) {
                    maxContainer.classList.add('d-none');
                }
                if (maxInput) {
                    maxInput.disabled = true;
                    maxInput.required = false;
                }
                if (unitContainer && unitInput) {
                    if (type === 'information') {
                        unitContainer.classList.remove('d-none');
                        unitInput.disabled = false;
                    } else {
                        unitContainer.classList.add('d-none');
                        unitInput.disabled = true;
                    }
                }
                if (panel) {
                    panel.classList.add('d-none');
                }
            } else {
                if (maxContainer) {
                    maxContainer.classList.remove('d-none');
                }
                if (maxInput) {
                    maxInput.disabled = false;
                    maxInput.required = true;
                    if (!maxInput.value) {
                        maxInput.value = 100;
                    }
                }
                if (unitContainer && unitInput) {
                    unitContainer.classList.add('d-none');
                    unitInput.disabled = true;
                }
                if (type === 'grade') {
                    if (panel) {
                        panel.classList.remove('d-none');
                        fetchAndRenderBands(idx, panel, currentSubdivision(idx), 0);
                    }
                } else {
                    if (panel) {
                        panel.classList.add('d-none');
                    }
                }
            }
        });
    }

    function bindMaxInputEvent(input) {
        input.addEventListener('input', function () {
            const idx = this.getAttribute('name').split('_')[1];
            const panel = document.getElementById(`rubric-panel-${idx}`);
            if (!panel || panel.classList.contains('d-none')) return;

            const typeSelect = document.querySelector(`select[name="type_${idx}"]`);
            if (!typeSelect || typeSelect.value !== 'grade') return;

            const maxMarks = parseInt(this.value, 10);
            if (isNaN(maxMarks) || maxMarks <= 0) return;

            fetchAndRenderBands(idx, panel, currentSubdivision(idx), 400);
        });
    }

    // Initialize logic on DOM Content Loaded
    document.addEventListener('DOMContentLoaded', function() {
        // Bind existing rows
        document.querySelectorAll('.type-select').forEach(bindTypeSelectEvent);
        document.querySelectorAll('input[name^="max_"]').forEach(bindMaxInputEvent);

        function updateAvailableHeadersDropdown() {
            const select = document.getElementById('add-column-select');
            if (!select) return;
            
            select.innerHTML = '<option value="">— Select Column —</option>';
            
            // Sort availableHeaders alphabetically by label
            availableHeaders.sort((a, b) => a.label.localeCompare(b.label));
            
            availableHeaders.forEach(h => {
                const opt = document.createElement('option');
                opt.value = h.raw;
                opt.textContent = h.label;
                select.appendChild(opt);
            });
        }

        function removeCategoryRow(idx) {
            const row = document.getElementById(`cat-row-${idx}`);
            const panel = document.getElementById(`rubric-panel-${idx}`);
            const removedInput = document.getElementById(`removed-input-${idx}`);
            
            if (row) row.classList.add('d-none');
            if (panel) panel.classList.add('d-none');
            if (removedInput) removedInput.value = '1';
            
            const colName = row.getAttribute('data-column-name');
            const colLabel = row.querySelector('td:first-child').textContent.trim();
            
            if (colName && !availableHeaders.some(h => h.raw === colName)) {
                // Re-infer if it was numeric. Check current type
                const typeSelect = row.querySelector('.type-select');
                const wasNumeric = typeSelect ? (typeSelect.value === 'numeric' || typeSelect.value === 'grade') : true;
                availableHeaders.push({raw: colName, label: colLabel, is_numeric: wasNumeric});
                updateAvailableHeadersDropdown();
            }
        }

        function addColumnRow(colName, colLabel, isNumeric) {
            const tbody = document.querySelector('.mapping-table tbody');
            
            // Clone row template
            const rowTemplate = document.getElementById('row-template');
            const newRow = rowTemplate.cloneNode(true);
            newRow.id = `cat-row-${nextRowIdx}`;
            newRow.classList.remove('d-none');
            newRow.setAttribute('data-column-name', colName);
            
            newRow.querySelector('.col-name-label').textContent = colLabel;
            
            // Add hidden inputs for backend identification
            const hiddenColName = document.createElement('input');
            hiddenColName.type = 'hidden';
            hiddenColName.name = `col_name_${nextRowIdx}`;
            hiddenColName.value = colName;
            newRow.appendChild(hiddenColName);
            
            const hiddenRemoved = document.createElement('input');
            hiddenRemoved.type = 'hidden';
            hiddenRemoved.name = `removed_${nextRowIdx}`;
            hiddenRemoved.id = `removed-input-${nextRowIdx}`;
            hiddenRemoved.value = '0';
            newRow.appendChild(hiddenRemoved);
            
            // Set type select names and classes
            const typeSelect = newRow.querySelector('.type-select');
            typeSelect.name = `type_${nextRowIdx}`;
            typeSelect.setAttribute('data-idx', nextRowIdx);
            typeSelect.classList.add('type-select'); // to match querySelectorAll
            
            const maxContainer = newRow.querySelector('.max-marks-container');
            maxContainer.className = `max-marks-container-${nextRowIdx}`;
            
            const maxInput = newRow.querySelector('.max-marks-input');
            maxInput.name = `max_${nextRowIdx}`;
            
            const unitContainer = newRow.querySelector('.unit-container');
            unitContainer.className = `unit-container-${nextRowIdx}`;
            
            const unitInput = newRow.querySelector('.unit-input');
            unitInput.name = `unit_${nextRowIdx}`;
            
            const commentsSelect = newRow.querySelector('.comments-select');
            commentsSelect.name = `comments_${nextRowIdx}`;
            
            // Clone rubric panel template
            const panelTemplate = document.getElementById('rubric-panel-template');
            const newPanel = panelTemplate.cloneNode(true);
            newPanel.id = `rubric-panel-${nextRowIdx}`;
            newPanel.setAttribute('data-idx', nextRowIdx);
            newPanel.setAttribute('data-col', colName);
            
            // Bind events
            bindTypeSelectEvent(typeSelect);
            bindMaxInputEvent(maxInput);
            
            const removeBtn = newRow.querySelector('.remove-row-btn');
            removeBtn.addEventListener('click', function() {
                removeCategoryRow(nextRowIdx);
            });
            
            tbody.appendChild(newRow);
            tbody.appendChild(newPanel);
            
            // Default values based on numeric detection
            if (!isNumeric) {
                typeSelect.value = 'feedback_only';
            } else {
                typeSelect.value = 'numeric';
            }
            typeSelect.dispatchEvent(new Event('change'));
            
            // Increment counter
            nextRowIdx++;
            
            // Remove from available headers and update dropdown
            availableHeaders = availableHeaders.filter(h => h.raw !== colName);
            updateAvailableHeadersDropdown();
        }

        // Initialize dropdown on page load
        updateAvailableHeadersDropdown();

        // Bind Add Column button
        const addColumnBtn = document.getElementById('add-column-btn');
        if (addColumnBtn) {
            addColumnBtn.addEventListener('click', function() {
                const select = document.getElementById('add-column-select');
                const selectedVal = select.value;
                if (!selectedVal) return;
                
                const selectedHeader = availableHeaders.find(h => h.raw === selectedVal);
                if (selectedHeader) {
                    addColumnRow(selectedHeader.raw, selectedHeader.label, selectedHeader.is_numeric);
                }
            });
        }

        // Bind existing remove buttons
        document.querySelectorAll('.remove-row-btn').forEach(btn => {
            const idx = btn.getAttribute('data-idx');
            if (idx) {
                btn.addEventListener('click', function() {
                    removeCategoryRow(idx);
                });
            }
        });

        const degreeLevelInput = document.querySelector('select[name="degree_level"]');
        if (degreeLevelInput) {
            degreeLevelInput.addEventListener('change', function () {
                document.querySelectorAll('.rubric-panel').forEach(panel => {
                    if (panel.classList.contains('d-none')) return;
                    const idx = panel.getAttribute('data-idx');
                    fetchAndRenderBands(idx, panel, currentSubdivision(idx), 0);
                });
            });
        }

        // ── Overall mark column dynamic highlighting listener ──────────────────────
        const overallMarkSelect = document.getElementById('col_overall_mark');
        let prevOverallMarkCol = overallMarkSelect ? overallMarkSelect.value : '';

        if (overallMarkSelect) {
            overallMarkSelect.addEventListener('change', function () {
                const selectedVal = this.value;
                
                // 1. Restore the old overall mark column row if it exists in the table
                if (prevOverallMarkCol && prevOverallMarkCol !== selectedVal) {
                    const oldRow = document.querySelector(`tr[id^="cat-row-"][data-column-name="${CSS.escape(prevOverallMarkCol)}"]`);
                    if (oldRow) {
                        oldRow.style.backgroundColor = "";
                        oldRow.style.borderLeft = "";
                        const badge = oldRow.querySelector('.overall-mark-badge');
                        if (badge) badge.remove();
                        const commentsSelect = oldRow.querySelector('select[name^="comments_"]');
                        if (commentsSelect) {
                            commentsSelect.disabled = false;
                            const firstOpt = commentsSelect.options[0];
                            if (firstOpt) firstOpt.textContent = "-- No Comment Column --";
                            
                            // Remove hidden comments input to avoid conflicting with re-enabled select on submit
                            const idx = oldRow.id.slice('cat-row-'.length);
                            const hiddenInput = oldRow.querySelector(`input[type="hidden"][name="comments_${idx}"]`);
                            if (hiddenInput) hiddenInput.remove();
                        }
                        const removeBtn = oldRow.querySelector('.remove-row-btn');
                        if (removeBtn) removeBtn.classList.remove('d-none');
                    } else {
                        // It wasn't in the table, so make it available in the dropdown
                        const option = Array.from(overallMarkSelect.options).find(opt => opt.value === prevOverallMarkCol);
                        const label = option ? option.textContent.trim() : prevOverallMarkCol;
                        if (!availableHeaders.some(h => h.raw === prevOverallMarkCol)) {
                            availableHeaders.push({raw: prevOverallMarkCol, label: label, is_numeric: true});
                            updateAvailableHeadersDropdown();
                        }
                    }
                }
                
                // 2. Handle the new overall mark column row
                if (selectedVal !== "") {
                    let newRow = document.querySelector(`tr[id^="cat-row-"][data-column-name="${CSS.escape(selectedVal)}"]`);
                    if (!newRow) {
                        // It's not in the table yet! Let's find its label and add it automatically.
                        const option = Array.from(overallMarkSelect.options).find(opt => opt.value === selectedVal);
                        const label = option ? option.textContent.trim() : selectedVal;
                        
                        // Add it as a numeric column
                        addColumnRow(selectedVal, label, true);
                        newRow = document.querySelector(`tr[id^="cat-row-"][data-column-name="${CSS.escape(selectedVal)}"]`);
                    }
                    
                    if (newRow) {
                        newRow.style.backgroundColor = "rgba(67, 97, 238, 0.08)";
                        newRow.style.borderLeft = "4px solid #4361ee";
                        
                        const titleCell = newRow.querySelector('td:first-child');
                        if (titleCell && !titleCell.querySelector('.overall-mark-badge')) {
                            const badgeSpan = document.createElement('span');
                            badgeSpan.className = "badge overall-mark-badge ms-2";
                            badgeSpan.textContent = "Overall Mark";
                            
                            const container = titleCell.querySelector('.d-flex');
                            if (container) {
                                container.appendChild(badgeSpan);
                            } else {
                                titleCell.appendChild(badgeSpan);
                            }
                        }
                        
                        const commentsSelect = newRow.querySelector('select[name^="comments_"]');
                        if (commentsSelect) {
                            commentsSelect.disabled = true;
                            commentsSelect.value = "";
                            const firstOpt = commentsSelect.options[0];
                            if (firstOpt) firstOpt.textContent = "-- Mapped as Overall Mark --";
                            
                            // Add hidden input so that form submits empty value for comments when disabled
                            const idx = newRow.id.slice('cat-row-'.length);
                            let hiddenInput = newRow.querySelector(`input[type="hidden"][name="comments_${idx}"]`);
                            if (!hiddenInput) {
                                hiddenInput = document.createElement('input');
                                hiddenInput.type = 'hidden';
                                hiddenInput.name = `comments_${idx}`;
                                hiddenInput.value = '';
                                newRow.appendChild(hiddenInput);
                            }
                        }
                        
                        const removeBtn = newRow.querySelector('.remove-row-btn');
                        if (removeBtn) removeBtn.classList.add('d-none');
                    }
                }
                
                prevOverallMarkCol = selectedVal;
            });
        }

        // ── Student name format toggler listener ───────────────────────────────
        function tryAutoSelectSplitNameCols() {
            const firstSel = document.getElementById('col_first_name');
            const lastSel  = document.getElementById('col_last_name');

            if (firstSel && !firstSel.value) {
                for (const opt of firstSel.options) {
                    const v = opt.value.toLowerCase();
                    if (v.includes('first') || v.includes('forename') || v.includes('given')) {
                        firstSel.value = opt.value;
                        break;
                    }
                }
            }
            if (lastSel && !lastSel.value) {
                for (const opt of lastSel.options) {
                    const v = opt.value.toLowerCase();
                    if (v.includes('last') || v.includes('surname') || v.includes('family')) {
                        lastSel.value = opt.value;
                        break;
                    }
                }
            }
        }

        const nameModeSelect = document.getElementById('name_mode');
        if (nameModeSelect) {
            nameModeSelect.addEventListener('change', function () {
                const isSplit = this.value === 'split';
                
                document.querySelectorAll('.name-field-full').forEach(el => {
                    if (isSplit) el.classList.add('d-none');
                    else el.classList.remove('d-none');
                });
                
                document.querySelectorAll('.name-field-split').forEach(el => {
                    if (isSplit) el.classList.remove('d-none');
                    else el.classList.add('d-none');
                });

                if (isSplit) {
                    tryAutoSelectSplitNameCols();
                }
            });

            if (nameModeSelect.value === 'split') {
                tryAutoSelectSplitNameCols();
            }
        }

        // ── Group column toggle ──────────────────────────────────────────────────
        const groupColSelect = document.getElementById('col_group');
        let _prevGroupCol = groupColSelect ? groupColSelect.value : '';

        function setGroupRowHidden(columnName, hidden) {
            const catRow = document.querySelector(
                `tr[id^="cat-row-"][data-column-name="${CSS.escape(columnName)}"]`
            );
            if (!catRow) return;

            const idx = catRow.id.slice('cat-row-'.length);
            const rubricPanel = document.getElementById(`rubric-panel-${idx}`);
            const typeSelect  = document.querySelector(`select[name="type_${idx}"]`);

            if (hidden) {
                catRow.classList.add('d-none');
                if (rubricPanel) rubricPanel.classList.add('d-none');
            } else {
                catRow.classList.remove('d-none');
                if (rubricPanel && typeSelect && typeSelect.value === 'grade') {
                    rubricPanel.classList.remove('d-none');
                }
            }
        }

        if (groupColSelect) {
            groupColSelect.addEventListener('change', function () {
                const newVal = this.value;
                if (_prevGroupCol) setGroupRowHidden(_prevGroupCol, false);
                if (newVal)        setGroupRowHidden(newVal, true);
                _prevGroupCol = newVal;
            });
        }
    });
})();
