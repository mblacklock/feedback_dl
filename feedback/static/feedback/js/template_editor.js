// Template Editor - Auto-save functionality

let saveTimeout = null;
let isSaving = false;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Load existing categories if any
    if (window.templateData && window.templateData.categories && window.templateData.categories.length > 0) {
        window.templateData.categories.forEach(cat => {
            addCategoryRow(cat);
        });
    } else {
        // Add one empty row
        addCategoryRow();
    }
    
    // Set up auto-save for summary fields
    document.querySelectorAll('.auto-save').forEach(field => {
        field.addEventListener('input', debouncedSave);
        field.addEventListener('blur', saveNow);
    });
});

// Add category button
document.getElementById('add-category').addEventListener('click', function() {
    addCategoryRow();
    debouncedSave();
});

function addCategoryRow(categoryData = null) {
    const container = document.getElementById('categories');
    const row = document.createElement('div');
    const uniqueId = Date.now();
    row.className = 'category-row mb-4 p-3 border rounded';
    
    const label = categoryData ? categoryData.label : '';
    const max = categoryData ? categoryData.max : 10;
    // If categoryData exists, use its type; if no type field, infer from presence of subdivision
    // For new empty rows (no categoryData), default to 'grade'
    let type = 'grade';  // Default for new empty rows
    if (categoryData) {
        if (categoryData.type) {
            type = categoryData.type;
        } else {
            // Backward compatibility: if no type field, infer from subdivision field
            type = categoryData.subdivision ? 'grade' : 'numeric';
        }
    }
    const subdivision = categoryData && categoryData.subdivision ? categoryData.subdivision : 'none';
    
    // Store original category data on the row element for preservation when switching types
    row.dataset.originalCategoryData = JSON.stringify(categoryData || {});
    
    row.innerHTML = `
        <div class="row mb-2">
            <div class="col-md-10">
                <label class="form-label">Category Label</label>
                <input type="text" class="form-control cat-label" placeholder="e.g., Introduction" value="${label}">
            </div>
            <div class="col-md-2">
                <label class="form-label">&nbsp;</label>
                <button type="button" class="btn btn-danger btn-sm w-100 remove-category">Remove</button>
            </div>
        </div>
        <div class="row mb-2">
            <div class="col-md-2">
                <label class="form-label">Max Marks</label>
                <input type="number" class="form-control cat-max" placeholder="Max" value="${max}" min="1" max="1000">
            </div>
            <div class="col-md-3">
                <label class="form-label">Type</label>
                <div class="btn-group w-100" role="group">
                    <input type="radio" class="btn-check cat-type-grade" name="category_type_${uniqueId}" id="grade_${uniqueId}" value="grade" ${type === 'grade' ? 'checked' : ''}>
                    <label class="btn btn-outline-primary" for="grade_${uniqueId}">Grade</label>
                    
                    <input type="radio" class="btn-check cat-type-numeric" name="category_type_${uniqueId}" id="numeric_${uniqueId}" value="numeric" ${type === 'numeric' ? 'checked' : ''}>
                    <label class="btn btn-outline-primary" for="numeric_${uniqueId}">Numeric</label>
                </div>
            </div>
            <div class="col-md-7 subdivision-controls" style="display: ${type === 'grade' ? 'block' : 'none'};">
                <label class="form-label">Subdivision</label>
                <div class="btn-group w-100" role="group">
                    <button type="button" class="btn btn-outline-secondary subdivision-btn ${subdivision === 'none' ? 'active' : ''}" data-subdivision="none">None</button>
                    <button type="button" class="btn btn-outline-secondary subdivision-btn ${subdivision === 'high_low' ? 'active' : ''}" data-subdivision="high_low">High/Low</button>
                    <button type="button" class="btn btn-outline-secondary subdivision-btn ${subdivision === 'high_mid_low' ? 'active' : ''}" data-subdivision="high_mid_low">High/Mid/Low</button>
                </div>
                <input type="hidden" class="subdivision-value" value="${subdivision}">
            </div>
        </div>
        <div class="row subdivision-controls" style="display: ${type === 'grade' ? 'block' : 'none'};">
            <div class="col-md-12">
                <div class="grade-bands-preview mt-2 small text-muted"></div>
            </div>
        </div>
    `;
    container.appendChild(row);
    
    // Explicitly set the checked property on the radio button (HTML attribute doesn't always work)
    const gradeRadio = row.querySelector('.cat-type-grade');
    const numericRadio = row.querySelector('.cat-type-numeric');
    if (type === 'grade') {
        gradeRadio.checked = true;
    } else {
        numericRadio.checked = true;
    }
    
    // Update grade bands preview if grade type is selected
    if (type === 'grade' && subdivision) {
        updateGradeBandsPreview(row);
    }
    
    // Set up event handlers for this row
    setupRowEventHandlers(row);
}

function setupRowEventHandlers(row) {
    const typeRadios = row.querySelectorAll('input[type="radio"]');
    const subdivisionControls = row.querySelectorAll('.subdivision-controls');
    const subdivisionButtons = row.querySelectorAll('.subdivision-btn');
    const subdivisionInput = row.querySelector('.subdivision-value');
    const maxMarksInput = row.querySelector('.cat-max');
    const labelInput = row.querySelector('.cat-label');
    const removeButton = row.querySelector('.remove-category');
    
    // Auto-save on input changes
    labelInput.addEventListener('input', debouncedSave);
    labelInput.addEventListener('blur', saveNow);
    maxMarksInput.addEventListener('input', debouncedSave);
    maxMarksInput.addEventListener('blur', saveNow);
    
    // Handle type radio button changes
    typeRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            if (this.value === 'grade') {
                subdivisionControls.forEach(el => el.style.display = 'block');
                if (!subdivisionInput.value) {
                    subdivisionInput.value = 'none';
                    subdivisionButtons[0].classList.add('active');
                }
                validateRow(row);
                updateGradeBandsPreview(row);
            } else {
                subdivisionControls.forEach(el => el.style.display = 'none');
                subdivisionInput.value = '';
                subdivisionButtons.forEach(btn => btn.classList.remove('active'));
                removeRowValidationError(row);
            }
            debouncedSave();
        });
    });
    
    // Validate when max marks changes
    maxMarksInput.addEventListener('input', function() {
        const typeRadio = row.querySelector('input[type="radio"]:checked');
        if (typeRadio && typeRadio.value === 'grade') {
            validateRow(row);
            updateGradeBandsPreview(row);
        }
    });
    
    // Handle subdivision button clicks
    subdivisionButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            subdivisionButtons.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            subdivisionInput.value = this.dataset.subdivision;
            validateRow(row);
            updateGradeBandsPreview(row);
            debouncedSave();
        });
    });
    
    // Handle remove button
    removeButton.addEventListener('click', function() {
        row.remove();
        debouncedSave();
    });
}

function validateRow(row) {
    removeRowValidationError(row);
    
    const typeRadio = row.querySelector('input[type="radio"]:checked');
    
    if (typeRadio && typeRadio.value === 'grade') {
        const maxMarks = parseInt(row.querySelector('.cat-max').value);
        const label = row.querySelector('.cat-label').value || 'This category';
        
        if (maxMarks < 9) {
            showValidationError(row, `${label}: ${maxMarks} marks is too low for grade bands. Use 9+ marks or switch to numeric scoring.`);
        }
    }
}

function removeRowValidationError(row) {
    const existingError = row.querySelector('.grade-validation-error');
    if (existingError) {
        existingError.remove();
    }
}

function showValidationError(row, message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'alert alert-danger alert-dismissible fade show mt-2 grade-validation-error';
    errorDiv.innerHTML = `
        <strong>Validation Error:</strong> ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    row.appendChild(errorDiv);
    errorDiv.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function debouncedSave() {
    updateSaveStatus('pending');
    
    if (saveTimeout) {
        clearTimeout(saveTimeout);
    }
    
    saveTimeout = setTimeout(() => {
        saveNow();
    }, 1000); // Wait 1 second after user stops typing
}

function updateStoredCategoryData(row) {
    // Update the stored original category data with current values
    // This ensures descriptions are preserved when switching between types
    try {
        const originalData = JSON.parse(row.dataset.originalCategoryData || '{}');
        
        // Collect current descriptions from DOM
        const descriptions = {};
        row.querySelectorAll('.grade-description').forEach(textarea => {
            const grade = textarea.getAttribute('data-grade');
            const desc = textarea.value.trim();
            if (desc) {
                descriptions[grade] = desc;
            }
        });
        
        // Update stored data
        if (Object.keys(descriptions).length > 0) {
            originalData.grade_band_descriptions = descriptions;
        }
        
        const subdivision = row.querySelector('.subdivision-value')?.value;
        if (subdivision) {
            originalData.subdivision = subdivision;
        }
        
        const typeRadio = row.querySelector('input[type="radio"]:checked');
        if (typeRadio) {
            originalData.type = typeRadio.value;
        }
        
        row.dataset.originalCategoryData = JSON.stringify(originalData);
    } catch (e) {
        console.error('Error updating stored category data:', e);
    }
}

function saveNow() {
    if (isSaving) return;
    
    // Clear any pending timeout
    if (saveTimeout) {
        clearTimeout(saveTimeout);
        saveTimeout = null;
    }
    
    // Update stored data for all rows before saving
    document.querySelectorAll('.category-row').forEach(row => {
        updateStoredCategoryData(row);
    });
    
    updateSaveStatus('saving');
    isSaving = true;
    
    // Collect data
    const data = {
        title: document.getElementById('title').value,
        module_code: document.getElementById('module_code').value,
        module_title: document.getElementById('module_title').value,
        assessment_title: document.getElementById('assessment_title').value,
        weighting: document.getElementById('weighting').value ? parseInt(document.getElementById('weighting').value) : null,
        component: parseInt(document.getElementById('component').value),
        categories: []
    };
    
    // Collect categories
    document.querySelectorAll('.category-row').forEach(row => {
        const label = row.querySelector('.cat-label').value.trim();
        const max = parseInt(row.querySelector('.cat-max').value);
        
        if (!label || !max) return; // Skip empty rows
        
        const typeRadio = row.querySelector('input[type="radio"]:checked');
        const type = typeRadio ? typeRadio.value : 'numeric';
        
        const category = {
            label: label,
            max: max,
            type: type
        };
        
        // Preserve subdivision and descriptions even when switching to numeric
        // (so they can be restored if user switches back to grade)
        const subdivision = row.querySelector('.subdivision-value').value;
        if (subdivision) {
            category.subdivision = subdivision;
        }
        
        // Collect grade band descriptions from visible textareas (if grade type)
        const descriptions = {};
        row.querySelectorAll('.grade-description').forEach(textarea => {
            const grade = textarea.getAttribute('data-grade');
            const desc = textarea.value.trim();
            if (desc) {
                descriptions[grade] = desc;
            }
        });
        
        // If numeric type and no visible descriptions, preserve original descriptions from data
        if (type === 'numeric' && Object.keys(descriptions).length === 0) {
            try {
                const originalData = JSON.parse(row.dataset.originalCategoryData || '{}');
                if (originalData.grade_band_descriptions) {
                    Object.assign(descriptions, originalData.grade_band_descriptions);
                }
            } catch (e) {
                // Ignore JSON parse errors
            }
        }
        
        if (Object.keys(descriptions).length > 0) {
            category.grade_band_descriptions = descriptions;
        }
        
        data.categories.push(category);
    });
    
    // Get CSRF token
    const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || 
                     getCookie('csrftoken');
        
    // Send to server
    fetch(`/feedback/template/${window.templateData.id}/update/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrftoken
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(result => {
        if (result.status === 'saved') {
            updateSaveStatus('saved');
        } else {
            updateSaveStatus('error');
            console.error('Save error:', result.error);
        }
        isSaving = false;
    })
    .catch(error => {
        updateSaveStatus('error');
        console.error('Save failed:', error);
        isSaving = false;
    });
}

function updateSaveStatus(status) {
    const statusEl = document.getElementById('save-status');
    
    switch(status) {
        case 'pending':
            // Don't show anything while waiting for debounce
            break;
        case 'saving':
            statusEl.innerHTML = '<span class="text-primary"><i class="bi bi-arrow-repeat spin"></i> Saving...</span>';
            break;
        case 'saved':
            statusEl.innerHTML = '<span class="text-success"><i class="bi bi-check-circle"></i> Saved</span>';
            setTimeout(() => {
                statusEl.innerHTML = '';
            }, 2000);
            break;
        case 'error':
            statusEl.innerHTML = '<span class="text-danger"><i class="bi bi-exclamation-circle"></i> Save failed</span>';
            break;
    }
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function updateGradeBandsPreview(row) {
    const previewEl = row.querySelector('.grade-bands-preview');
    if (!previewEl) return;
    
    const maxMarks = parseInt(row.querySelector('.cat-max').value);
    const subdivision = row.querySelector('.subdivision-value').value;
    
    if (!maxMarks || maxMarks < 1 || !subdivision) {
        previewEl.innerHTML = '';
        return;
    }
    
    // Save current descriptions from DOM before re-rendering
    const currentDescriptions = {};
    previewEl.querySelectorAll('.grade-description').forEach(textarea => {
        const grade = textarea.getAttribute('data-grade');
        const value = textarea.value.trim();
        if (value) {
            currentDescriptions[grade] = value;
        }
    });
    
    // Fetch grade bands HTML from server
    fetch(`/feedback/grade-bands-preview/?max_marks=${maxMarks}&subdivision=${subdivision}`)
        .then(response => response.json())
        .then(data => {
            if (data.html) {
                previewEl.innerHTML = data.html;
                
                // Get existing descriptions from saved category data
                const categoryData = getCategoryDataForRow(row);
                const savedDescriptions = categoryData && categoryData.grade_band_descriptions ? categoryData.grade_band_descriptions : {};
                
                // Merge: current DOM values take priority over saved values
                const descriptions = { ...savedDescriptions, ...currentDescriptions };
                
                // Fill in existing descriptions and attach event listeners
                // Use setTimeout to ensure DOM is ready
                setTimeout(() => {
                    previewEl.querySelectorAll('.grade-description').forEach(textarea => {
                        const grade = textarea.getAttribute('data-grade');
                        if (descriptions[grade]) {
                            textarea.value = descriptions[grade];
                        }
                        
                        // Attach event listeners
                        textarea.addEventListener('input', debouncedSave);
                        textarea.addEventListener('blur', saveNow);
                    });
                }, 0);
            } else {
                previewEl.innerHTML = '';
            }
        })
        .catch(error => {
            console.error('Error fetching grade bands:', error);
            previewEl.innerHTML = '';
        });
}

function getCategoryDataForRow(row) {
    // Find the index of this row
    const allRows = document.querySelectorAll('.category-row');
    const rowIndex = Array.from(allRows).indexOf(row);
    
    // Get category data from window.templateData if available
    if (window.templateData && window.templateData.categories && window.templateData.categories[rowIndex]) {
        return window.templateData.categories[rowIndex];
    }
    return null;
}

// Add spinning animation for save icon
const style = document.createElement('style');
style.textContent = `
    .spin {
        animation: spin 1s linear infinite;
    }
    @keyframes spin {
        100% { transform: rotate(360deg); }
    }
`;
document.head.appendChild(style);
