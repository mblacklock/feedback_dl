/**
 * Shared utility to initialize drag-and-drop file upload zones.
 *
 * @param {Object} options Configuration options:
 * @param {string} options.dropzoneId - ID of the dropzone container element.
 * @param {string} options.fileInputId - ID of the file input element.
 * @param {string} [options.fileListCardId] - ID of the optional staged files card container.
 * @param {string} [options.stagedFilesListId] - ID of the <ul> where staged files are listed.
 * @param {string} [options.clearAllBtnId] - ID of the "Clear All" button.
 * @param {string} [options.headingSelector] - CSS Selector for the primary text header.
 * @param {string} [options.subtextSelector] - CSS Selector for the secondary text subtext.
 * @param {string} [options.defaultHeading] - Default text header when empty.
 * @param {string} [options.defaultSubtext] - Default subtext when empty.
 * @param {string} [options.successTextSingle] - Subtext when 1 file is selected.
 * @param {string} [options.successTextMultiple] - Subtext when multiple files are selected.
 * @param {string} [options.pluralNoun="files"] - Noun used in plural headers (e.g. "snapshots").
 * @param {string} [options.activeBorderColor="#4361ee"] - Border color applied when file is ready or dragover.
 * @param {string} [options.activeBgColor="#eff6ff"] - Background color applied when file is ready or dragover.
 */
function initDropzone(options) {
    const dropzone = document.getElementById(options.dropzoneId);
    const fileInput = document.getElementById(options.fileInputId);
    if (!dropzone || !fileInput) return;

    const fileListCard = options.fileListCardId ? document.getElementById(options.fileListCardId) : null;
    const stagedFilesList = options.stagedFilesListId ? document.getElementById(options.stagedFilesListId) : null;
    const clearAllBtn = options.clearAllBtnId ? document.getElementById(options.clearAllBtnId) : null;

    const headingEl = dropzone.querySelector(options.headingSelector || 'h5, .file-heading');
    const subEl = dropzone.querySelector(options.subtextSelector || 'p, .file-sub');

    const multiple = fileInput.multiple || options.multiple || false;
    let accumulatedFiles = new DataTransfer();

    const activeBorderColor = options.activeBorderColor || "#4361ee";
    const activeBgColor = options.activeBgColor || "#eff6ff";

    // Remember initial default text from DOM if not explicitly provided in options
    const defaultHeadingText = options.defaultHeading || (headingEl ? headingEl.innerText : "");
    const defaultSubtextVal = options.defaultSubtext || (subEl ? subEl.innerText : "");

    function updateUI() {
        const filesCount = fileInput.files.length;
        if (filesCount > 0) {
            // Render staged file lists if matching elements exist
            if (fileListCard && stagedFilesList) {
                fileListCard.classList.remove('d-none');
                stagedFilesList.innerHTML = '';
                for (let i = 0; i < filesCount; i++) {
                    const file = fileInput.files[i];
                    const li = document.createElement('li');
                    li.className = 'list-group-item d-flex justify-content-between align-items-center bg-transparent py-1 px-0 border-0 text-slate-700 small';
                    li.innerHTML = `
                        <span>📄 ${file.name}</span>
                        <span class="text-muted text-xs">(${Math.round(file.size / 1024)} KB)</span>
                    `;
                    stagedFilesList.appendChild(li);
                }
            }

            // Update primary text header and subtext
            if (filesCount === 1) {
                if (headingEl) headingEl.innerText = fileInput.files[0].name;
                if (subEl) subEl.innerText = options.successTextSingle || "1 file ready to upload";
            } else {
                if (headingEl) headingEl.innerText = `${filesCount} ${options.pluralNoun || 'files'} selected`;
                if (subEl) subEl.innerText = options.successTextMultiple || "Files ready to upload";
            }
            
            // Set inline styles to indicate success
            dropzone.style.borderColor = activeBorderColor;
            dropzone.style.backgroundColor = activeBgColor;
        } else {
            // Reset to empty state
            if (fileListCard) fileListCard.classList.add('d-none');
            if (stagedFilesList) stagedFilesList.innerHTML = '';
            
            if (headingEl) headingEl.innerText = defaultHeadingText;
            if (subEl) subEl.innerText = defaultSubtextVal;
            
            // Clear inline styles so standard CSS hover classes can take over
            dropzone.style.borderColor = "";
            dropzone.style.backgroundColor = "";
        }
    }

    fileInput.addEventListener('change', (e) => {
        if (multiple && e.detail !== 'manual_update') {
            for (let i = 0; i < fileInput.files.length; i++) {
                accumulatedFiles.items.add(fileInput.files[i]);
            }
            fileInput.files = accumulatedFiles.files;
        }
        updateUI();
    });

    if (clearAllBtn) {
        clearAllBtn.addEventListener('click', () => {
            accumulatedFiles = new DataTransfer();
            fileInput.value = '';
            updateUI();
        });
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropzone.classList.add('dragover');
            dropzone.style.borderColor = activeBorderColor;
            dropzone.style.backgroundColor = activeBgColor;
        }, false);
    });

    dropzone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        const filesCount = fileInput.files.length;
        if (filesCount === 0) {
            dropzone.style.borderColor = "";
            dropzone.style.backgroundColor = "";
        }
    }, false);

    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            if (multiple) {
                for (let i = 0; i < e.dataTransfer.files.length; i++) {
                    accumulatedFiles.items.add(e.dataTransfer.files[i]);
                }
                fileInput.files = accumulatedFiles.files;
                fileInput.dispatchEvent(new CustomEvent('change', { detail: 'manual_update' }));
            } else {
                fileInput.files = e.dataTransfer.files;
                fileInput.dispatchEvent(new Event('change'));
            }
        }
    }, false);

    // Run once at start to bind state if pre-populated
    updateUI();
}
