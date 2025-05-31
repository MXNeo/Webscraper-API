// Load configuration status on page load
document.addEventListener('DOMContentLoaded', function() {
    loadConfigStatus();
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
        
        // Update status indicators
        updateStatusIndicator('scrapegraph-status', data.scrapegraph_configured);
        updateStatusIndicator('database-status', data.database_configured);
        
        // Pre-fill form if configuration exists
        if (data.scrapegraph_configured && data.scrapegraph_config) {
            const config = data.scrapegraph_config;
            if (config.provider) document.getElementById('provider').value = config.provider;
            if (config.model) document.getElementById('model').value = config.model;
            if (config.base_url) document.getElementById('base-url').value = config.base_url;
            if (config.temperature !== undefined) document.getElementById('temperature').value = config.temperature;
            if (config.max_tokens) document.getElementById('max-tokens').value = config.max_tokens;
            
            // Trigger provider field toggle to show appropriate fields
            toggleProviderFields();
            
            // Fill Azure-specific fields if present
            if (config.additional_params) {
                const params = config.additional_params;
                if (params.api_version) document.getElementById('api-version').value = params.api_version;
                if (params.deployment_name) document.getElementById('deployment-name').value = params.deployment_name;
                if (params.embeddings_deployment) document.getElementById('embeddings-deployment').value = params.embeddings_deployment;
            }
        }
    } catch (error) {
        console.error('Error loading config status:', error);
    }
}

// Update status indicator
function updateStatusIndicator(elementId, isConfigured) {
    const element = document.getElementById(elementId);
    if (element) {
        element.className = isConfigured ? 'badge bg-success' : 'badge bg-warning';
        element.textContent = isConfigured ? 'Configured' : 'Not Configured';
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
    formData.append('database', document.getElementById('db-name').value);
    formData.append('table', document.getElementById('db-table').value);
    formData.append('username', document.getElementById('db-username').value);
    formData.append('password', document.getElementById('db-password').value);
    
    try {
        const response = await fetch('/api/config/database', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showAlert('Database configuration saved successfully!', 'success');
            loadConfigStatus(); // Reload status
        } else {
            showAlert('Error: ' + result.detail, 'danger');
        }
    } catch (error) {
        showAlert('Error saving database configuration: ' + error.message, 'danger');
    }
});

// Scrape with selected method
async function scrapeWithMethod(method) {
    const url = document.getElementById('url').value;
    if (!url) {
        showAlert('Please enter a URL to scrape', 'warning');
        return;
    }
    
    const resultsDiv = document.getElementById('scrape-results');
    const resultsContent = document.getElementById('results-content');
    
    // Show loading
    resultsContent.innerHTML = '<div class="text-center"><div class="spinner-border" role="status"></div><p>Scraping...</p></div>';
    resultsDiv.style.display = 'block';
    
    try {
        const response = await fetch(`/api/scrape/${method}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url: url })
        });
        
        const result = await response.json();
        
        if (result.status === 'success') {
            let contentDisplay = '';
            let imageDisplay = '';
            
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
            resultsContent.innerHTML = `
                <div class="alert alert-danger">
                    <strong>Error!</strong> ${result.error || 'Unknown error occurred'}
                </div>
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