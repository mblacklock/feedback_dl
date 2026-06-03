/**
 * Shared weight sum validation.
 * Finds weight inputs with class `.weight-input` on the page's form
 * and ensures they sum to exactly 100% on form submission.
 */
document.addEventListener('DOMContentLoaded', () => {
    const form = document.querySelector('form');
    if (!form) return;

    form.addEventListener('submit', (e) => {
        const weights = document.querySelectorAll('.weight-input');
        if (weights.length === 0) return;

        let sum = 0;
        weights.forEach(input => {
            sum += parseInt(input.value || 0, 10);
        });

        if (sum !== 100) {
            e.preventDefault();
            alert(`Component weights must sum to exactly 100%. Currently they sum to ${sum}%.`);
        }
    });
});
