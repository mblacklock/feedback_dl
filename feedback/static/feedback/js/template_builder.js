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
    row.className = 'category-row row mb-3 align-items-center';
    row.innerHTML = `
        <div class="col-md-6">
            <input type="text" class="form-control cat-label" name="category_label" placeholder="Category Label (e.g., Introduction)">
        </div>
        <div class="col-md-3">
            <input type="number" class="form-control cat-max" name="category_max" placeholder="Max Marks" value="10" min="1" max="1000">
        </div>
        <div class="col-md-3">
            <button type="button" class="btn btn-danger btn-sm w-100" onclick="this.closest('.category-row').remove()">Remove</button>
        </div>
    `;
    container.appendChild(row);
}
