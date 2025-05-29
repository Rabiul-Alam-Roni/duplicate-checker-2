// Enhanced script.js for AI-Powered Protein Gelatin Research Hub

// Utility functions
function showLoading(show = true) {
    const loading = document.getElementById('loading');
    if (loading) {
        loading.style.display = show ? 'block' : 'none';
    }
}

function showProgress(show = true, progress = 0) {
    const progressBar = document.getElementById('progressBar');
    const progressFill = document.getElementById('progressFill');
    
    if (progressBar && progressFill) {
        progressBar.style.display = show ? 'block' : 'none';
        progressFill.style.width = `${progress}%`;
    }
}

function showResponse(elementId, message, type = 'info') {
    const element = document.getElementById(elementId);
    if (element) {
        element.textContent = message;
        element.className = `response ${type}`;
        element.style.display = 'block';
        
        // Auto-hide after 5 seconds for success messages
        if (type === 'success') {
            setTimeout(() => {
                element.style.display = 'none';
            }, 5000);
        }
    }
}

function validateDOI(doi) {
    // Basic DOI validation
    const doiPattern = /^10\.\d{4,}\/[-._;()\/:a-zA-Z0-9]+$/;
    return doiPattern.test(doi);
}

function validateFile(file) {
    const allowedTypes = ['text/csv', 'application/vnd.ms-excel'];
    const maxSize = 10 * 1024 * 1024; // 10MB
    
    if (!allowedTypes.includes(file.type) && !file.name.endsWith('.csv')) {
        throw new Error('Please select a valid CSV file');
    }
    
    if (file.size > maxSize) {
        throw new Error('File size must be less than 10MB');
    }
    
    return true;
}

function clearForm() {
    document.getElementById('doi').value = '';
    document.getElementById('title').value = '';
    document.getElementById('tags').value = '';
    document.getElementById('hardness').checked = false;
    document.getElementById('whc').checked = false;
}

// Enhanced duplicate checking function
async function checkDuplicate() {
    const doi = document.getElementById('doi').value.trim();
    const title = document.getElementById('title').value.trim();
    const tags = document.getElementById('tags').value.trim();
    const hardness = document.getElementById('hardness').checked;
    const whc = document.getElementById('whc').checked;
    
    // Input validation
    if (!doi) {
        showResponse('response', 'Please enter a DOI to check for duplicates.', 'error');
        return;
    }
    
    if (!validateDOI(doi)) {
        showResponse('response', 'Please enter a valid DOI format (e.g., 10.1000/example)', 'error');
        return;
    }
    
    try {
        showLoading(true);
        showResponse('response', 'Analyzing article data...', 'info');
        
        const formData = new FormData();
        formData.append('doi', doi);
        formData.append('title', title);
        formData.append('tags', tags);
        formData.append('hardness', hardness);
        formData.append('whc', whc);
        
        const response = await fetch('/check_article', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error(`Server error: ${response.status}`);
        }
        
        const result = await response.json();
        
        // Show enhanced response based on result
        if (result.status === 'duplicate') {
            showResponse('response', 
                `⚠️ Duplicate Found: ${result.message}`, 
                'error'
            );
        } else if (result.status === 'success') {
            showResponse('response', 
                `✅ Success: ${result.message}`, 
                'success'
            );
            // Clear form on successful addition
            setTimeout(clearForm, 1500);
        } else {
            showResponse('response', 
                `ℹ️ ${result.message}`, 
                'info'
            );
        }
        
        // Update statistics if available
        if (result.stats) {
            updateStats(result.stats);
        }
        
    } catch (error) {
        console.error('Error checking duplicate:', error);
        showResponse('response', 
            `❌ Error: ${error.message || 'Failed to check duplicate. Please try again.'}`, 
            'error'
        );
    } finally {
        showLoading(false);
    }
}

// Enhanced file upload function
async function uploadFile() {
    const fileInput = document.getElementById('fileUpload');
    
    if (!fileInput.files || !fileInput.files[0]) {
        showResponse('fileResponse', 'Please select a CSV file to upload.', 'error');
        return;
    }
    
    const file = fileInput.files[0];
    
    try {
        validateFile(file);
        
        showProgress(true, 0);
        showResponse('fileResponse', 'Processing CSV file...', 'info');
        
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await fetch('/upload_file', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error(`Upload failed: ${response.status}`);
        }
        
        // Simulate progress for better UX
        let progress = 0;
        const progressInterval = setInterval(() => {
            progress += 10;
            showProgress(true, Math.min(progress, 90));
        }, 100);
        
        const result = await response.json();
        
        clearInterval(progressInterval);
        showProgress(true, 100);
        
        // Show detailed results
        const message = `📊 Processing Complete!\n` +
                       `✅ Successfully added: ${result.added} articles\n` +
                       `⚠️ Duplicates found: ${result.duplicates} articles\n` +
                       `📈 Total processed: ${result.added + result.duplicates} entries`;
        
        showResponse('fileResponse', message, 'success');
        
        // Update statistics
        if (result.stats) {
            updateStats(result.stats);
        }
        
        // Clear file input
        fileInput.value = '';
        
        setTimeout(() => {
            showProgress(false);
        }, 2000);
        
    } catch (error) {
        console.error('Error uploading file:', error);
        showResponse('fileResponse', 
            `❌ Upload Error: ${error.message}`, 
            'error'
        );
        showProgress(false);
    }
}

// Statistics functions
async function showStats() {
    try {
        const response = await fetch('/stats');
        if (!response.ok) {
            throw new Error('Failed to fetch statistics');
        }
        
        const stats = await response.json();
        updateStats(stats);
        
        const statsGrid = document.getElementById('statsGrid');
        if (statsGrid) {
            statsGrid.style.display = 'grid';
            statsGrid.scrollIntoView({ behavior: 'smooth' });
        }
        
    } catch (error) {
        console.error('Error fetching stats:', error);
        showResponse('fileResponse', 
            'Failed to load statistics. Please try again.', 
            'error'
        );
    }
}

function updateStats(stats) {
    const totalElement = document.getElementById('totalArticles');
    const duplicatesElement = document.getElementById('duplicatesFound');
    const uniqueElement = document.getElementById('uniqueArticles');
    
    if (totalElement) totalElement.textContent = stats.total || 0;
    if (duplicatesElement) duplicatesElement.textContent = stats.duplicates || 0;
    if (uniqueElement) uniqueElement.textContent = stats.unique || 0;
}

// Enhanced download function
async function downloadDatabase() {
    try {
        showResponse('fileResponse', 'Preparing download...', 'info');
        
        const response = await fetch('/export');
        if (!response.ok) {
            throw new Error('Failed to generate export file');
        }
        
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        
        // Generate filename with timestamp
        const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
        a.href = url;
        a.download = `protein_gelatin_database_${timestamp}.csv`;
        document.body.appendChild(a);
        a.click();
        
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        showResponse('fileResponse', 
            '✅ Database exported successfully!', 
            'success'
        );
        
    } catch (error) {
        console.error('Error downloading database:', error);
        showResponse('fileResponse', 
            `❌ Download Error: ${error.message}`, 
            'error'
        );
    }
}

// Event listeners and initialization
document.addEventListener('DOMContentLoaded', function() {
    // Add keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        if (e.ctrlKey || e.metaKey) {
            switch(e.key) {
                case 'Enter':
                    e.preventDefault();
                    checkDuplicate();
                    break;
                case 's':
                    e.preventDefault();
                    showStats();
                    break;
            }
        }
    });
    
    // Add input validation feedback
    const doiInput = document.getElementById('doi');
    if (doiInput) {
        doiInput.addEventListener('blur', function() {
            const doi = this.value.trim();
            if (doi && !validateDOI(doi)) {
                this.style.borderColor = '#EF4444';
                showResponse('response', 
                    'Invalid DOI format. Please use format: 10.xxxx/xxxxx', 
                    'error'
                );
            } else {
                this.style.borderColor = '';
                const responseElement = document.getElementById('response');
                if (responseElement && responseElement.classList.contains('error')) {
                    responseElement.style.display = 'none';
                }
            }
        });
    }
    
    // Auto-clear responses after user interaction
    const inputs = document.querySelectorAll('input[type="text"]');
    inputs.forEach(input => {
        input.addEventListener('focus', function() {
            const responseElement = document.getElementById('response');
            if (responseElement && responseElement.classList.contains('error')) {
                responseElement.style.display = 'none';
            }
        });
    });
    
    // Load initial statistics
    showStats();
});

// Export functions for global access
window.checkDuplicate = checkDuplicate;
window.uploadFile = uploadFile;
window.showStats = showStats;
window.downloadDatabase = downloadDatabase;
