// Template Builder - Dynamic Category Management

// Add initial category row on page load
document.addEventListener('DOMContentLoaded', function() {
    addCategoryRow();
});

document.getElementById('add-category').addEventListener('click', function() {
    addCategoryRow();
});

function addCategoryRow() {
    const container = document.getElementById('categories');
    const row = document.createElement('div');
    const uniqueId = Date.now();
    row.className = 'category-row mb-4 p-3 border rounded';
    row.innerHTML = `
        <div class="row mb-2">
            <div class="col-md-6">
                <label class="form-label">Category Label</label>
                <input type="text" class="form-control cat-label" name="category_label" placeholder="e.g., Introduction">
            </div>
            <div class="col-md-4">
                <label class="form-label">Maximum Marks</label>
                <input type="number" class="form-control cat-max" name="category_max" placeholder="Max Marks" value="10" min="1" max="1000">
            </div>
            <div class="col-md-2">
                <label class="form-label">&nbsp;</label>
                <button type="button" class="btn btn-danger btn-sm w-100" onclick="this.closest('.category-row').remove()">Remove</button>
            </div>
        </div>
        <div class="row mb-2">
            <div class="col-md-12">
                <label class="form-label">Type</label>
                <div class="btn-group w-100" role="group">
                    <input type="radio" class="btn-check cat-type-numeric" name="category_type_${uniqueId}" id="numeric_${uniqueId}" value="numeric" checked>
                    <label class="btn btn-outline-primary" for="numeric_${uniqueId}">Numeric</label>
                    
                    <input type="radio" class="btn-check cat-type-grade" name="category_type_${uniqueId}" id="grade_${uniqueId}" value="grade">
                    <label class="btn btn-outline-primary" for="grade_${uniqueId}">Grade</label>
                </div>
            </div>
        </div>
        <div class="row subdivision-controls" style="display: none;">
            <div class="col-md-12">
                <label class="form-label">Subdivision</label>
                <div class="btn-group w-100" role="group">
                    <button type="button" class="btn btn-outline-secondary subdivision-btn" data-subdivision="none">None</button>
                    <button type="button" class="btn btn-outline-secondary subdivision-btn" data-subdivision="high_low">High/Low</button>
                    <button type="button" class="btn btn-outline-secondary subdivision-btn" data-subdivision="high_mid_low">High/Mid/Low</button>
                </div>
                <input type="hidden" class="subdivision-value" name="category_subdivision" value="">
            </div>
        </div>
    `;
    container.appendChild(row);
    
    // Set up event handlers for this row
    setupRowEventHandlers(row);
}

function setupRowEventHandlers(row) {
    // Handle type radio button changes
    const typeRadios = row.querySelectorAll('input[type="radio"]');
    const subdivisionControls = row.querySelector('.subdivision-controls');
    const subdivisionButtons = row.querySelectorAll('.subdivision-btn');
    const subdivisionInput = row.querySelector('.subdivision-value');
    
    typeRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            if (this.value === 'grade') {
                subdivisionControls.style.display = 'block';
                // Default to 'none' if nothing selected
                if (!subdivisionInput.value) {
                    subdivisionInput.value = 'none';
                    subdivisionButtons[0].classList.add('active');
                }
            } else {
                subdivisionControls.style.display = 'none';
                subdivisionInput.value = '';
                subdivisionButtons.forEach(btn => btn.classList.remove('active'));
            }
        });
    });
    
    // Handle subdivision button clicks
    subdivisionButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            // Remove active from all buttons in this row
            subdivisionButtons.forEach(b => b.classList.remove('active'));
            // Add active to clicked button
            this.classList.add('active');
            // Set hidden input value
            subdivisionInput.value = this.dataset.subdivision;
        });
    });
    
    // Add hidden input for category_type that submits with the form
    const form = document.getElementById('template-form');
    form.addEventListener('submit', function() {
        // For each row, add a hidden input with the selected type
        document.querySelectorAll('.category-row').forEach((r, idx) => {
            const checkedRadio = r.querySelector('input[type="radio"]:checked');
            if (checkedRadio) {
                const hiddenInput = document.createElement('input');
                hiddenInput.type = 'hidden';
                hiddenInput.name = 'category_type';
                hiddenInput.value = checkedRadio.value;
                form.appendChild(hiddenInput);
            }
        });
    });
}
