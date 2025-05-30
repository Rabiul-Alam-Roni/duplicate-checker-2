// Enhanced script.js for AI-Powered Protein Gelatin Research Hub

// Global state management
let uploadedData = [];
let databaseData = [];

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
        element.innerHTML = message.replace(/\n/g, '<br>');
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
    // Enhanced DOI validation
    const doiPattern = /^10\.\d{4,}\/[-._;()\/:a-zA-Z0-9]+$/;
    return doiPattern.test(doi.trim());
}

function validateFile(file) {
    const allowedTypes = [
        'text/csv', 
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/csv',
        'text/plain'
    ];
    const allowedExtensions = ['.csv', '.xlsx', '.xls'];
    const maxSize = 50 * 1024 * 1024; // 50MB for larger Excel files
    
    const hasValidType = allowedTypes.includes(file.type);
    const hasValidExtension = allowedExtensions.some(ext => 
        file.name.toLowerCase().endsWith(ext)
    );
    
    if (!hasValidType && !hasValidExtension) {
        throw new Error('Please select a valid CSV or Excel file (.csv, .xlsx, .xls)');
    }
    
    if (file.size > maxSize) {
        throw new Error('File size must be less than 50MB');
    }
    
    return true;
}

function clearForm() {
    document.getElementById('doi').value = '';
    document.getElementById('title').value = '';
    document.getElementById('protein').value = '';
    document.getElementById('hardness').checked = false;
    document.getElementById('whc').checked = false;
}

function normalizeDOI(doi) {
    return doi.trim().toLowerCase().replace(/https?:\/\/(dx\.)?doi\.org\//, '');
}

function checkIfDOIInUploadedData(doi) {
    const normalizedDOI = normalizeDOI(doi);
    return uploadedData.some(item => 
        normalizeDOI(item.doi || '') === normalizedDOI
    );
}

// Enhanced duplicate checking function
async function checkDuplicate() {
    const doi = document.getElementById('doi').value.trim();
    const title = document.getElementById('title').value.trim();
    const protein = document.getElementById('protein').value.trim();
    const hardness = document.getElementById('hardness').checked;
    const whc = document.getElementById('whc').checked;
    
    // Input validation
    if (!doi) {
        showResponse('response', '❌ Please enter a DOI to check for duplicates.', 'error');
        return;
    }
    
    if (!validateDOI(doi)) {
        showResponse('response', '❌ Please enter a valid DOI format (e.g., 10.1000/example)', 'error');
        return;
    }
    
    // Check if DOI exists in uploaded data first
    if (checkIfDOIInUploadedData(doi)) {
        showResponse('response', 
            '🔴 <strong>ALREADY DOWNLOADED:</strong> This DOI exists in your uploaded CSV/Excel file. No need to save again.', 
            'error'
        );
        return;
    }
    
    try {
        showLoading(true);
        showResponse('response', '🔍 Analyzing article data...', 'info');
        
        const articleData = {
            doi: doi,
            title: title,
            protein: protein,
            hardness: hardness,
            whc: whc,
            timestamp: new Date().toISOString()
        };
        
        const response = await fetch('/check_article', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(articleData)
        });
        
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Server error: ${response.status} - ${errorText}`);
        }
        
        const result = await response.json();
        
        // Show enhanced response based on result
        if (result.status === 'duplicate') {
            showResponse('response', 
                `⚠️ <strong>Duplicate Found:</strong> ${result.message}`, 
                'error'
            );
        } else if (result.status === 'success') {
            // Add to local database data
            databaseData.push(articleData);
            
            showResponse('response', 
                `✅ <strong>Successfully Saved:</strong> ${result.message}<br>📊 Total articles in database: ${databaseData.length}`, 
                'success'
            );
            
            // Clear form on successful addition
            setTimeout(clearForm, 2000);
            
            // Update statistics
            updateLocalStats();
        } else {
            showResponse('response', 
                `ℹ️ ${result.message}`, 
                'info'
            );
        }
        
        // Update statistics if available from server
        if (result.stats) {
            updateStats(result.stats);
        }
        
    } catch (error) {
        console.error('Error checking duplicate:', error);
        showResponse('response', 
            `❌ <strong>Error:</strong> ${error.message || 'Failed to check duplicate. Please try again.'}`, 
            'error'
        );
    } finally {
        showLoading(false);
    }
}

// Enhanced file upload function with Excel support
async function uploadFile() {
    const fileInput = document.getElementById('fileUpload');
    
    if (!fileInput.files || !fileInput.files[0]) {
        showResponse('fileResponse', '❌ Please select a CSV or Excel file to upload.', 'error');
        return;
    }
    
    const file = fileInput.files[0];
    
    try {
        validateFile(file);
        
        showProgress(true, 10);
        showResponse('fileResponse', '📂 Processing file... Please wait.', 'info');
        
        // Process file client-side first
        let fileData = [];
        
        if (file.name.toLowerCase().endsWith('.csv')) {
            fileData = await processCSVFile(file);
        } else if (file.name.toLowerCase().endsWith('.xlsx') || file.name.toLowerCase().endsWith('.xls')) {
            fileData = await processExcelFile(file);
        }
        
        showProgress(true, 30);
        
        // Filter and validate data
        const validData = fileData.filter(row => {
            const doi = row.DOI || row.doi || '';
            return doi && validateDOI(doi);
        }).map(row => ({
            doi: normalizeDOI(row.DOI || row.doi || ''),
            title: row.Title || row.title || '',
            protein: row.Protein_Type || row.protein || row.Protein || '',
            hardness: row.Gel_Hardness || row.hardness || false,
            whc: row.Water_Holding_Capacity || row.whc || row.WHC || false
        }));
        
        showProgress(true, 50);
        
        if (validData.length === 0) {
            throw new Error('No valid DOI entries found in the file. Please check the file format.');
        }
        
        // Store uploaded data globally
        uploadedData = validData;
        
        showProgress(true, 70);
        
        // Send to server
        const formData = new FormData();
        formData.append('file', file);
        formData.append('processed_data', JSON.stringify(validData));
        
        const response = await fetch('/upload_file', {
            method: 'POST',
            body: formData
        });
        
        showProgress(true, 90);
        
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Upload failed: ${response.status} - ${errorText}`);
        }
        
        const result = await response.json();
        showProgress(true, 100);
        
        // Show detailed results
        const message = `📊 <strong>File Processing Complete!</strong><br>` +
                       `✅ Valid entries found: <strong>${validData.length}</strong><br>` +
                       `📥 Successfully processed: <strong>${result.added || validData.length}</strong> articles<br>` +
                       `⚠️ Duplicates detected: <strong>${result.duplicates || 0}</strong> articles<br>` +
                       `🎯 <strong>Ready for duplicate checking!</strong>`;
        
        showResponse('fileResponse', message, 'success');
        
        // Update statistics
        updateLocalStats();
        
        // Clear file input
        fileInput.value = '';
        
        setTimeout(() => {
            showProgress(false);
        }, 3000);
        
    } catch (error) {
        console.error('Error uploading file:', error);
        showResponse('fileResponse', 
            `❌ <strong>Upload Error:</strong> ${error.message}`, 
            'error'
        );
        showProgress(false);
    }
}

// CSV file processing function
async function processCSVFile(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = function(e) {
            try {
                const csv = e.target.result;
                const lines = csv.split('\n');
                const headers = lines[0].split(',').map(h => h.trim().replace(/"/g, ''));
                
                const data = [];
                for (let i = 1; i < lines.length; i++) {
                    if (lines[i].trim()) {
                        const values = lines[i].split(',').map(v => v.trim().replace(/"/g, ''));
                        const row = {};
                        headers.forEach((header, index) => {
                            row[header] = values[index] || '';
                        });
                        data.push(row);
                    }
                }
                resolve(data);
            } catch (error) {
                reject(new Error('Failed to parse CSV file: ' + error.message));
            }
        };
        reader.onerror = () => reject(new Error('Failed to read file'));
        reader.readAsText(file);
    });
}

// Excel file processing function
async function processExcelFile(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = function(e) {
            try {
                // Note: In a real implementation, you'd use a library like SheetJS
                // For now, we'll provide a fallback message
                reject(new Error('Excel file processing requires additional libraries. Please convert to CSV format.'));
            } catch (error) {
                reject(new Error('Failed to parse Excel file: ' + error.message));
            }
        };
        reader.onerror = () => reject(new Error('Failed to read Excel file'));
        reader.readAsArrayBuffer(file);
    });
}

// Statistics functions
async function showStats() {
    try {
        showLoading(true);
        const response = await fetch('/stats');
        
        let stats = {};
        if (response.ok) {
            stats = await response.json();
        } else {
            // Use local statistics if server fails
            stats = getLocalStats();
        }
        
        updateStats(stats);
        
        const statsGrid = document.getElementById('statsGrid');
        if (statsGrid) {
            statsGrid.style.display = 'grid';
            statsGrid.scrollIntoView({ behavior: 'smooth' });
        }
        
    } catch (error) {
        console.error('Error fetching stats:', error);
        // Fallback to local statistics
        const localStats = getLocalStats();
        updateStats(localStats);
        
        showResponse('fileResponse', 
            '⚠️ Using local statistics. Server connection failed.', 
            'info'
        );
    } finally {
        showLoading(false);
    }
}

function getLocalStats() {
    return {
        total: databaseData.length + uploadedData.length,
        uploaded: uploadedData.length,
        saved: databaseData.length,
        unique: new Set([...databaseData, ...uploadedData].map(item => normalizeDOI(item.doi))).size
    };
}

function updateLocalStats() {
    const stats = getLocalStats();
    updateStats(stats);
}

function updateStats(stats) {
    const totalElement = document.getElementById('totalArticles');
    const uploadedElement = document.getElementById('uploadedArticles');
    const savedElement = document.getElementById('savedArticles');
    const uniqueElement = document.getElementById('uniqueArticles');
    
    if (totalElement) totalElement.textContent = stats.total || 0;
    if (uploadedElement) uploadedElement.textContent = stats.uploaded || uploadedData.length;
    if (savedElement) savedElement.textContent = stats.saved || databaseData.length;
    if (uniqueElement) uniqueElement.textContent = stats.unique || 0;
}

// Enhanced download function
async function downloadDatabase() {
    try {
        showResponse('fileResponse', '📥 Preparing database export...', 'info');
        showLoading(true);
        
        const response = await fetch('/export');
        
        if (!response.ok) {
            // Fallback to local data export
            exportLocalData();
            return;
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
            '✅ <strong>Database exported successfully!</strong><br>📁 File saved to your downloads folder.', 
            'success'
        );
        
    } catch (error) {
        console.error('Error downloading database:', error);
        showResponse('fileResponse', 
            `❌ <strong>Download Error:</strong> ${error.message}<br>Trying local export...`, 
            'error'
        );
        
        // Fallback to local export
        setTimeout(() => exportLocalData(), 1000);
    } finally {
        showLoading(false);
    }
}

function exportLocalData() {
    try {
        const allData = [...uploadedData, ...databaseData];
        
        if (allData.length === 0) {
            showResponse('fileResponse', '⚠️ No data available to export.', 'error');
            return;
        }
        
        const headers = ['DOI', 'Title', 'Protein_Type', 'Gel_Hardness', 'Water_Holding_Capacity'];
        const csvContent = [
            headers.join(','),
            ...allData.map(item => [
                item.doi || '',
                `"${(item.title || '').replace(/"/g, '""')}"`,
                item.protein || '',
                item.hardness ? 'Yes' : 'No',
                item.whc ? 'Yes' : 'No'
            ].join(','))
        ].join('\n');
        
        const blob = new Blob([csvContent], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        
        const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
        a.href = url;
        a.download = `protein_gelatin_local_${timestamp}.csv`;
        document.body.appendChild(a);
        a.click();
        
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        showResponse('fileResponse', 
            '✅ <strong>Local data exported successfully!</strong><br>📁 File saved to your downloads folder.', 
            'success'
        );
        
    } catch (error) {
        showResponse('fileResponse', 
            `❌ <strong>Export Error:</strong> ${error.message}`, 
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
                case 'd':
                    e.preventDefault();
                    downloadDatabase();
                    break;
            }
        }
    });
    
    // Enhanced input validation feedback
    const doiInput = document.getElementById('doi');
    if (doiInput) {
        doiInput.addEventListener('blur', function() {
            const doi = this.value.trim();
            if (doi && !validateDOI(doi)) {
                this.style.borderColor = '#EF4444';
                this.style.boxShadow = '0 0 0 3px rgba(239, 68, 68, 0.1)';
                showResponse('response', 
                    '❌ Invalid DOI format. Please use format: 10.xxxx/xxxxx', 
                    'error'
                );
            } else {
                this.style.borderColor = '#10B981';
                this.style.boxShadow = '0 0 0 3px rgba(16, 185, 129, 0.1)';
                const responseElement = document.getElementById('response');
                if (responseElement && responseElement.classList.contains('error')) {
                    responseElement.style.display = 'none';
                }
            }
        });
        
        doiInput.addEventListener('input', function() {
            // Real-time check if DOI exists in uploaded data
            const doi = this.value.trim();
            if (doi && validateDOI(doi) && checkIfDOIInUploadedData(doi)) {
                this.style.borderColor = '#F59E0B';
                this.style.boxShadow = '0 0 0 3px rgba(245, 158, 11, 0.1)';
                showResponse('response', 
                    '🟡 This DOI exists in your uploaded file.', 
                    'info'
                );
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
    setTimeout(() => {
        showStats();
    }, 1000);
    
    // Initialize tooltips for better UX
    initializeTooltips();
});

function initializeTooltips() {
    const tooltipElements = document.querySelectorAll('[data-tooltip]');
    tooltipElements.forEach(element => {
        element.addEventListener('mouseenter', function() {
            const tooltip = document.createElement('div');
            tooltip.className = 'tooltip';
            tooltip.textContent = this.getAttribute('data-tooltip');
            document.body.appendChild(tooltip);
            
            const rect = this.getBoundingClientRect();
            tooltip.style.left = rect.left + (rect.width / 2) - (tooltip.offsetWidth / 2) + 'px';
            tooltip.style.top = rect.top - tooltip.offsetHeight - 10 + 'px';
        });
        
        element.addEventListener('mouseleave', function() {
            const tooltip = document.querySelector('.tooltip');
            if (tooltip) {
                tooltip.remove();
            }
        });
    });
}

// Export functions for global access
window.checkDuplicate = checkDuplicate;
window.uploadFile = uploadFile;
window.showStats = showStats;
window.downloadDatabase = downloadDatabase;

// Additional utility functions for debugging
window.getUploadedData = () => uploadedData;
window.getDatabaseData = () => databaseData;
window.clearAllData = () => {
    uploadedData = [];
    databaseData = [];
    updateLocalStats();
    showResponse('fileResponse', '🗑️ All local data cleared.', 'info');
};
