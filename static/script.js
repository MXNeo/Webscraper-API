// Load configuration status on page load
document.addEventListener('DOMContentLoaded', function() {
    loadConfigStatus();
    
    // Add proxy toggle event listener
    const proxyToggle = document.getElementById('proxy-toggle');
    if (proxyToggle) {
        proxyToggle.addEventListener('change', toggleProxyUsage);
    }
});

// Provider field toggle function
function toggleProviderFields() {
    const provider = document.getElementById('provider').value;
    const apiKeyField = document.getElementById('api-key-field');
    const baseUrlField = document.getElementById('base-url-field');
    const azureFields = document.getElementById('azure-fields');
    const modelSuggestions = document.getElementById('model-suggestions');
    const suggestionList = document.getElementById('suggestion-list');
    const modelHelp = document.getElementById('model-help');
    const apiKeyInput = document.getElementById('api-key');
    
    // Reset visibility
    azureFields.style.display = 'none';
    modelSuggestions.style.display = 'none';
    
    // Configure fields based on provider
    switch(provider) {
        case 'openai':
            apiKeyField.style.display = 'block';
            baseUrlField.style.display = 'block';
            apiKeyInput.required = true;
            modelHelp.textContent = 'Enter OpenAI model name (e.g., gpt-4o, gpt-3.5-turbo, gpt-4-turbo)';
            suggestionList.innerHTML = `
                <span class="badge bg-secondary me-1" onclick="setModel('gpt-4o')">gpt-4o</span>
                <span class="badge bg-secondary me-1" onclick="setModel('gpt-4-turbo')">gpt-4-turbo</span>
                <span class="badge bg-secondary me-1" onclick="setModel('gpt-3.5-turbo')">gpt-3.5-turbo</span>
                <span class="badge bg-secondary me-1" onclick="setModel('gpt-4o-mini')">gpt-4o-mini</span>
            `;
            modelSuggestions.style.display = 'block';
            break;
            
        case 'anthropic':
            apiKeyField.style.display = 'block';
            baseUrlField.style.display = 'block';
            apiKeyInput.required = true;
            modelHelp.textContent = 'Enter Anthropic model name (e.g., claude-3-opus-20240229, claude-3-sonnet-20240229)';
            suggestionList.innerHTML = `
                <span class="badge bg-secondary me-1" onclick="setModel('claude-3-opus-20240229')">claude-3-opus-20240229</span>
                <span class="badge bg-secondary me-1" onclick="setModel('claude-3-sonnet-20240229')">claude-3-sonnet-20240229</span>
                <span class="badge bg-secondary me-1" onclick="setModel('claude-3-haiku-20240307')">claude-3-haiku-20240307</span>
            `;
            modelSuggestions.style.display = 'block';
            break;
            
        case 'ollama':
            apiKeyField.style.display = 'none';
            baseUrlField.style.display = 'block';
            apiKeyInput.required = false;
            document.getElementById('base-url').value = 'http://localhost:11434';
            modelHelp.textContent = 'Enter Ollama model name (e.g., llama3, mistral, codellama)';
            suggestionList.innerHTML = `
                <span class="badge bg-secondary me-1" onclick="setModel('ollama/llama3')">ollama/llama3</span>
                <span class="badge bg-secondary me-1" onclick="setModel('ollama/mistral')">ollama/mistral</span>
                <span class="badge bg-secondary me-1" onclick="setModel('ollama/codellama')">ollama/codellama</span>
                <span class="badge bg-secondary me-1" onclick="setModel('ollama/phi3')">ollama/phi3</span>
            `;
            modelSuggestions.style.display = 'block';
            break;
            
        case 'azure':
            apiKeyField.style.display = 'block';
            baseUrlField.style.display = 'block';
            azureFields.style.display = 'block';
            apiKeyInput.required = true;
            modelHelp.textContent = 'Enter Azure deployment model name';
            break;
            
        case 'custom':
            apiKeyField.style.display = 'block';
            baseUrlField.style.display = 'block';
            apiKeyInput.required = false;
            modelHelp.textContent = 'Enter custom model name or identifier';
            break;
            
        default:
            apiKeyField.style.display = 'block';
            baseUrlField.style.display = 'block';
            apiKeyInput.required = true;
            modelHelp.textContent = 'Enter the exact model name';
    }
}

// Set model name from suggestion
function setModel(modelName) {
    document.getElementById('model').value = modelName;
}

// Load configuration status
async function loadConfigStatus() {
    try {
        const response = await fetch('/api/config/status');
        const data = await response.json();
        
        console.log('Configuration status:', data);
        
        // Update ScrapeGraph AI status
        updateStatusIndicator('scrapegraph-status', data.scrapegraph.status === 'configured', data.scrapegraph.status);
        
        // Update Database status
        updateStatusIndicator('database-status', data.database.status === 'connected', data.database.status);
        updateDatabaseDetails(data.database);
        
        // Update Proxy status
        updateProxyStatus(data.proxy);
        
    } catch (error) {
        console.error('Error loading config status:', error);
        showAlert('Error loading configuration status: ' + error.message, 'danger');
    }
}

// Update status indicator with more detailed status
function updateStatusIndicator(elementId, isConfigured, status) {
    const element = document.getElementById(elementId);
    if (element) {
        let badgeClass = 'badge bg-warning';
        let text = 'Not Configured';
        
        switch(status) {
            case 'configured':
            case 'connected':
                badgeClass = 'badge bg-success';
                text = status === 'configured' ? 'Configured' : 'Connected';
                break;
            case 'error':
                badgeClass = 'badge bg-danger';
                text = 'Error';
                break;
            case 'not_configured':
            default:
                badgeClass = 'badge bg-warning';
                text = 'Not Configured';
        }
        
        element.className = badgeClass;
        element.textContent = text;
    }
}

// Update database details
function updateDatabaseDetails(databaseConfig) {
    const detailsElement = document.getElementById('database-details');
    if (detailsElement && databaseConfig.message) {
        detailsElement.textContent = databaseConfig.message;
        detailsElement.style.display = 'block';
    }
}

// Update proxy status and controls
function updateProxyStatus(proxyConfig) {
    const statusElement = document.getElementById('proxy-status');
    const detailsElement = document.getElementById('proxy-details');
    const controlsElement = document.getElementById('proxy-controls');
    const toggleElement = document.getElementById('proxy-toggle');
    
    if (statusElement) {
        let badgeClass = 'badge bg-secondary';
        let text = 'Disabled';
        
        if (proxyConfig.status === 'ready') {
            badgeClass = 'badge bg-success';
            text = 'Ready';
        } else if (proxyConfig.enabled) {
            badgeClass = 'badge bg-warning';
            text = 'Enabled (No Proxies)';
        }
        
        statusElement.className = badgeClass;
        statusElement.textContent = text;
    }
    
    if (detailsElement) {
        if (proxyConfig.available_proxies > 0) {
            detailsElement.textContent = `${proxyConfig.available_proxies} proxies available`;
            detailsElement.style.display = 'block';
        } else {
            detailsElement.style.display = 'none';
        }
    }
    
    if (controlsElement && toggleElement) {
        // Show controls if database is configured
        if (proxyConfig.available_proxies >= 0) {
            controlsElement.style.display = 'block';
            toggleElement.checked = proxyConfig.enabled;
        } else {
            controlsElement.style.display = 'none';
        }
    }
}

// Toggle proxy usage
async function toggleProxyUsage() {
    const enabled = document.getElementById('proxy-toggle').checked;
    
    try {
        const formData = new FormData();
        formData.append('enabled', enabled);
        
        const response = await fetch('/api/config/proxy/toggle', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showAlert(result.message, 'success');
            loadConfigStatus(); // Reload status
        } else {
            showAlert('Error: ' + result.detail, 'danger');
            // Revert toggle state
            document.getElementById('proxy-toggle').checked = !enabled;
        }
    } catch (error) {
        showAlert('Error toggling proxy usage: ' + error.message, 'danger');
        // Revert toggle state
        document.getElementById('proxy-toggle').checked = !enabled;
    }
}

// Handle ScrapeGraph AI configuration form submission
document.getElementById('scrapegraph-config-form').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const formData = new FormData();
    formData.append('provider', document.getElementById('provider').value);
    formData.append('model', document.getElementById('model').value);
    
    const apiKey = document.getElementById('api-key').value;
    if (apiKey) formData.append('api_key', apiKey);
    
    const baseUrl = document.getElementById('base-url').value;
    if (baseUrl) formData.append('base_url', baseUrl);
    
    formData.append('temperature', document.getElementById('temperature').value);
    
    const maxTokens = document.getElementById('max-tokens').value;
    if (maxTokens) formData.append('max_tokens', maxTokens);
    
    // Add Azure-specific parameters if provider is Azure
    const provider = document.getElementById('provider').value;
    if (provider === 'azure') {
        const apiVersion = document.getElementById('api-version').value;
        if (apiVersion) formData.append('api_version', apiVersion);
        
        const deploymentName = document.getElementById('deployment-name').value;
        if (deploymentName) formData.append('deployment_name', deploymentName);
        
        const embeddingsDeployment = document.getElementById('embeddings-deployment').value;
        if (embeddingsDeployment) formData.append('embeddings_deployment', embeddingsDeployment);
    }
    
    try {
        const response = await fetch('/api/config/scrapegraph', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showAlert('Configuration saved successfully!', 'success');
            loadConfigStatus(); // Reload status
        } else {
            showAlert('Error: ' + result.detail, 'danger');
        }
    } catch (error) {
        showAlert('Error saving configuration: ' + error.message, 'danger');
    }
});

// Handle database configuration form submission
document.getElementById('database-config-form').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const formData = new FormData();
    formData.append('host', document.getElementById('db-host').value);
    formData.append('port', document.getElementById('db-port').value);
    formData.append('database', document.getElementById('db-name').value);
    formData.append('username', document.getElementById('db-username').value);
    formData.append('password', document.getElementById('db-password').value);
    
    try {
        const response = await fetch('/api/config/database', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showAlert(`Database configuration saved! ${result.proxy_table_status}`, 'success');
            loadConfigStatus(); // Reload status
        } else {
            showAlert('Error: ' + result.detail, 'danger');
        }
    } catch (error) {
        showAlert('Error saving database configuration: ' + error.message, 'danger');
    }
});

// Test database connection
async function testDatabaseConnection() {
    try {
        const response = await fetch('/api/proxy/test');
        const result = await response.json();
        
        if (result.success) {
            showAlert(`Database test successful! ${result.message}`, 'success');
        } else {
            showAlert(`Database test failed: ${result.message}`, 'danger');
        }
    } catch (error) {
        showAlert('Error testing database: ' + error.message, 'danger');
    }
}

// Delete database configuration
async function deleteDatabaseConfig() {
    if (!confirm('Are you sure you want to delete the database configuration? This will also disable proxy usage.')) {
        return;
    }
    
    try {
        const response = await fetch('/api/config/database', {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showAlert('Database configuration deleted successfully!', 'success');
            loadConfigStatus(); // Reload status
            // Clear form
            document.getElementById('database-config-form').reset();
        } else {
            showAlert('Error: ' + result.detail, 'danger');
        }
    } catch (error) {
        showAlert('Error deleting database configuration: ' + error.message, 'danger');
    }
}

// Test proxy connection
async function testProxyConnection() {
    const testResults = document.getElementById('proxy-test-results');
    const testContent = document.getElementById('proxy-test-content');
    
    testContent.innerHTML = '<div class="text-center"><div class="spinner-border spinner-border-sm" role="status"></div> Testing...</div>';
    testResults.style.display = 'block';
    
    try {
        const response = await fetch('/api/proxy/test');
        const result = await response.json();
        
        if (result.success) {
            let proxyList = '';
            if (result.sample_proxies && result.sample_proxies.length > 0) {
                proxyList = '<h6>Sample Proxies:</h6><ul>';
                result.sample_proxies.forEach(proxy => {
                    proxyList += `<li>${proxy.address}:${proxy.port} (${proxy.type}) - Errors: ${proxy.error_count} ${proxy.has_auth ? '🔐' : ''}</li>`;
                });
                proxyList += '</ul>';
            }
            
            testContent.innerHTML = `
                <div class="alert alert-success">
                    <strong>Success!</strong> ${result.message}
                </div>
                ${proxyList}
            `;
        } else {
            testContent.innerHTML = `
                <div class="alert alert-danger">
                    <strong>Failed!</strong> ${result.message}
                </div>
            `;
        }
    } catch (error) {
        testContent.innerHTML = `
            <div class="alert alert-danger">
                <strong>Error!</strong> ${error.message}
            </div>
        `;
    }
}

// Get proxy statistics
async function getProxyStats() {
    const statsResults = document.getElementById('proxy-stats-results');
    const statsContent = document.getElementById('proxy-stats-content');
    
    statsContent.innerHTML = '<div class="text-center"><div class="spinner-border spinner-border-sm" role="status"></div> Loading...</div>';
    statsResults.style.display = 'block';
    
    try {
        const response = await fetch('/api/proxy/stats');
        const result = await response.json();
        
        if (result.error) {
            statsContent.innerHTML = `
                <div class="alert alert-danger">
                    <strong>Error!</strong> ${result.error}
                </div>
            `;
        } else {
            statsContent.innerHTML = `
                <div class="row">
                    <div class="col-md-3">
                        <div class="card text-center">
                            <div class="card-body">
                                <h5 class="card-title">${result.total_proxies || 0}</h5>
                                <p class="card-text">Total Proxies</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card text-center">
                            <div class="card-body">
                                <h5 class="card-title">${result.active_proxies || 0}</h5>
                                <p class="card-text">Active Proxies</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card text-center">
                            <div class="card-body">
                                <h5 class="card-title">${result.usable_proxies || 0}</h5>
                                <p class="card-text">Usable Proxies<br><small>(error_count < 5)</small></p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card text-center">
                            <div class="card-body">
                                <h5 class="card-title">${result.high_error_proxies || 0}</h5>
                                <p class="card-text">High Error Proxies<br><small>(error_count ≥ 5)</small></p>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="mt-3">
                    <p><strong>Average Error Count:</strong> ${result.avg_error_count ? parseFloat(result.avg_error_count).toFixed(2) : 'N/A'}</p>
                </div>
            `;
        }
    } catch (error) {
        statsContent.innerHTML = `
            <div class="alert alert-danger">
                <strong>Error!</strong> ${error.message}
            </div>
        `;
    }
}

// Scrape with selected method
async function scrapeWithMethod(method) {
    const url = document.getElementById('url').value;
    if (!url) {
        showAlert('Please enter a URL to scrape', 'warning');
        return;
    }
    
    const useProxy = document.getElementById('use-proxy-test').checked;
    const resultsDiv = document.getElementById('scrape-results');
    const resultsContent = document.getElementById('results-content');
    
    // Show loading
    resultsContent.innerHTML = '<div class="text-center"><div class="spinner-border" role="status"></div><p>Scraping...</p></div>';
    resultsDiv.style.display = 'block';
    
    try {
        const requestBody = { url: url };
        if (useProxy) {
            requestBody.use_proxy = true;
        }
        
        const response = await fetch(`/api/scrape/${method}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestBody)
        });
        
        const result = await response.json();
        
        if (result.status === 'success') {
            let contentDisplay = '';
            let imageDisplay = '';
            let proxyInfo = '';
            
            // Show proxy usage info
            if (result.proxy_used) {
                proxyInfo = `<div class="alert alert-info"><small>🌐 Used proxy: ${result.proxy_used}</small></div>`;
            } else if (useProxy) {
                proxyInfo = `<div class="alert alert-warning"><small>⚠️ Proxy requested but not used (no proxies available)</small></div>`;
            }
            
            // Debug: Log the actual response structure
            console.log('API Response:', result);
            
            // Both methods now return the same standardized format: content, top_image, published
            const content = result.content;
            
            if (content && typeof content === 'object' && content.content !== undefined) {
                // Standardized response format for both methods
                const actualContent = typeof content.content === 'string' ? content.content : 
                                    (typeof content.content === 'object' ? JSON.stringify(content.content, null, 2) : 
                                     String(content.content));
                
                contentDisplay = `
                    ${content.published ? `<h6>Published:</h6><p>${content.published}</p>` : ''}
                    <h6>Content:</h6>
                    <div class="border p-3" style="max-height: 400px; overflow-y: auto; white-space: pre-wrap;">
                        ${actualContent || 'No content found'}
                    </div>
                `;
                imageDisplay = content.top_image ? `<img src="${content.top_image}" class="img-fluid" alt="Article image">` : '<p class="text-muted">No image found</p>';
            } else if (typeof content === 'string') {
                // String response (fallback)
                contentDisplay = `
                    <h6>Extracted Content:</h6>
                    <div class="border p-3" style="max-height: 400px; overflow-y: auto; white-space: pre-wrap;">
                        ${content}
                    </div>
                `;
                imageDisplay = '<p class="text-muted">Content extraction</p>';
            } else {
                // JSON object response (fallback) - better handling
                console.warn('Unexpected content structure:', content);
                contentDisplay = `
                    <h6>Debug - Raw Response:</h6>
                    <div class="border p-3" style="max-height: 400px; overflow-y: auto;">
                        <pre>${JSON.stringify(content, null, 2)}</pre>
                    </div>
                    <div class="alert alert-warning mt-2">
                        <small>Unexpected response format. Please check the console for details.</small>
                    </div>
                `;
                imageDisplay = '<p class="text-muted">Content extraction</p>';
            }
            
            resultsContent.innerHTML = `
                <div class="alert alert-success">
                    <strong>Success!</strong> Scraped using ${method === 'newspaper' ? 'Newspaper4k' : 'ScrapGraph AI'}
                </div>
                ${proxyInfo}
                <div class="row">
                    <div class="col-md-8">
                        ${contentDisplay}
                    </div>
                    <div class="col-md-4">
                        <h6>Image:</h6>
                        ${imageDisplay}
                    </div>
                </div>
            `;
        } else {
            let proxyInfo = '';
            if (result.proxy_used) {
                proxyInfo = `<div class="alert alert-warning"><small>🌐 Failed with proxy: ${result.proxy_used}</small></div>`;
            }
            
            resultsContent.innerHTML = `
                <div class="alert alert-danger">
                    <strong>Error!</strong> ${result.error || 'Unknown error occurred'}
                </div>
                ${proxyInfo}
            `;
        }
    } catch (error) {
        resultsContent.innerHTML = `
            <div class="alert alert-danger">
                <strong>Error!</strong> ${error.message}
            </div>
        `;
    }
}

// Delete ScrapeGraph AI configuration
async function deleteScrapegraphConfig() {
    if (!confirm('Are you sure you want to delete the ScrapeGraph AI configuration?')) {
        return;
    }
    
    try {
        const response = await fetch('/api/config/scrapegraph', {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showAlert('Configuration deleted successfully!', 'success');
            loadConfigStatus(); // Reload status
            // Clear form
            document.getElementById('scrapegraph-config-form').reset();
        } else {
            showAlert('Error: ' + result.detail, 'danger');
        }
    } catch (error) {
        showAlert('Error deleting configuration: ' + error.message, 'danger');
    }
}

// Show alert message
function showAlert(message, type) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    // Insert at the top of the container
    const container = document.querySelector('.container');
    container.insertBefore(alertDiv, container.firstChild);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
} 