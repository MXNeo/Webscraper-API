// Load configuration status on page load
document.addEventListener('DOMContentLoaded', function() {
    loadSystemStatus();
    setupFormHandlers();
});

// Setup form event handlers
function setupFormHandlers() {
    // ScrapeGraph AI config form
    const scrapegraphForm = document.getElementById('scrapegraph-config-form');
    if (scrapegraphForm) {
        scrapegraphForm.addEventListener('submit', saveScrapeGraphConfig);
    }
    
    // Database config form
    const databaseForm = document.getElementById('database-config-form');
    if (databaseForm) {
        databaseForm.addEventListener('submit', saveDatabaseConfig);
    }
    
    // Initialize DB button
    const initializeBtn = document.getElementById('initialize-db-btn');
    if (initializeBtn) {
        console.log('Initialize button found, adding event listener');
        initializeBtn.addEventListener('click', function(event) {
            console.log('Initialize button clicked');
            event.preventDefault();
            initializeDatabase();
        });
    } else {
        console.log('Initialize button not found during setup');
    }
    
    // Test connection button
    const testBtn = document.getElementById('test-connection-btn');
    if (testBtn) {
        testBtn.addEventListener('click', testDatabaseConnection);
    }
    
    // Proxy toggle
    const proxyToggle = document.getElementById('proxy-toggle');
    if (proxyToggle) {
        proxyToggle.addEventListener('change', toggleProxyUsage);
    }
}

// Load system status and auto-detect configuration
async function loadSystemStatus() {
    try {
        // First check for auto-detection
        const autoDetectResponse = await fetch('/api/config/auto-detect');
        const autoDetectData = await autoDetectResponse.json();
        
        console.log('Auto-detection result:', autoDetectData);
        
        // Auto-fill database fields if in full compose mode
        if (autoDetectData.database_auto_configured) {
            fillDatabaseFields(autoDetectData);
            showDeploymentInfo(autoDetectData.deployment_mode);
        }
        
        // Load regular config status
        const statusResponse = await fetch('/api/config/status');
        const statusData = await statusResponse.json();
        
        console.log('Configuration status:', statusData);
        
        // Load current database configuration into form fields (if exists and not auto-configured)
        if (!autoDetectData.database_auto_configured && statusData.database && statusData.database.configured) {
            await loadCurrentDatabaseConfig();
        }
        
        // Get simple database status (this is the key fix!)
        const dbStatusResponse = await fetch('/api/database/simple-status');
        const dbStatusData = await dbStatusResponse.json();
        
        console.log('Simple database status:', dbStatusData);
        
        // Update all status indicators
        updateApiStatus(statusData.scrapegraph);
        updateSimpleDatabaseStatus(dbStatusData);
        updateProxyStatus(statusData.proxy);
        
    } catch (error) {
        console.error('Error loading system status:', error);
        showAlert('Error loading system status: ' + error.message, 'danger');
    }
}

// Fill database fields with auto-detected values
function fillDatabaseFields(config) {
    console.log('Filling database fields with config:', config);
    
    // Only fill if elements exist
    const hostField = document.getElementById('db-host');
    const portField = document.getElementById('db-port');
    const nameField = document.getElementById('db-name');
    const userField = document.getElementById('db-user');
    const passwordField = document.getElementById('db-password');
    const tableField = document.getElementById('db-table');
    
    if (hostField) hostField.value = config.db_host || '';
    if (portField) portField.value = config.db_port || 5432;
    if (nameField) nameField.value = config.db_name || '';
    if (userField) userField.value = config.db_user || '';
    if (tableField) tableField.value = 'proxies';
    
    // For full compose mode, indicate password is auto-configured
    if (config.deployment_mode === 'full' && passwordField) {
        passwordField.placeholder = 'Auto-configured from environment';
        passwordField.value = 'auto_configured_placeholder'; // Hidden placeholder value
        passwordField.disabled = false; // Keep it editable
    }
}

// Load current database configuration from backend
async function loadCurrentDatabaseConfig() {
    try {
        const response = await fetch('/api/config/database');
        if (response.ok) {
            const config = await response.json();
            console.log('Loading current database config:', config);
            
            if (config.configured) {
                // Fill form fields with current saved configuration
                const hostField = document.getElementById('db-host');
                const portField = document.getElementById('db-port');
                const nameField = document.getElementById('db-name');
                const userField = document.getElementById('db-user');
                const passwordField = document.getElementById('db-password');
                const tableField = document.getElementById('db-table');
                
                if (hostField && config.host) hostField.value = config.host;
                if (portField && config.port) portField.value = config.port;
                if (nameField && config.database) nameField.value = config.database;
                if (userField && config.username) userField.value = config.username;
                if (passwordField) {
                    passwordField.placeholder = 'Current password (hidden)';
                    passwordField.value = ''; // Leave empty but indicate password exists
                }
                if (tableField && config.table) tableField.value = config.table;
                
                console.log('Database form fields populated with saved configuration');
            }
        }
    } catch (error) {
        console.error('Error loading current database config:', error);
    }
}

// Show deployment mode information
function showDeploymentInfo(deploymentMode) {
    const infoDiv = document.getElementById('deployment-info');
    const messageSpan = document.getElementById('deployment-message');
    
    if (infoDiv && messageSpan) {
        if (deploymentMode === 'full') {
            messageSpan.textContent = 'Full compose mode detected - database connection pre-configured but editable';
            infoDiv.style.display = 'block';
            infoDiv.className = 'alert alert-success';
        } else {
            messageSpan.textContent = 'Standalone mode - please configure database connection manually';
            infoDiv.style.display = 'block';
            infoDiv.className = 'alert alert-info';
        }
    }
}

// Update system status display
function updateSystemStatus(config) {
    const statusBadge = document.getElementById('db-connection-status');
    const initializeBtn = document.getElementById('initialize-db-btn');
    const statusDetails = document.getElementById('db-status-details');
    const statusJson = document.getElementById('db-status-json');
    
    if (config.database_connected) {
        statusBadge.textContent = 'Connected';
        statusBadge.className = 'badge bg-success ms-2';
        
        if (config.table_exists) {
            initializeBtn.textContent = 'Reinitialize Database';
            initializeBtn.className = 'btn btn-warning';
            initializeBtn.disabled = false;
        } else {
            initializeBtn.textContent = 'Initialize Database';
            initializeBtn.className = 'btn btn-success';
            initializeBtn.disabled = false;
        }
    } else {
        statusBadge.textContent = config.connection_message || 'Not Connected';
        statusBadge.className = 'badge bg-danger ms-2';
        initializeBtn.disabled = true;
    }
    
    // Show detailed status
    statusDetails.style.display = 'block';
    statusJson.textContent = JSON.stringify(config, null, 2);
}

// Update the database configuration section status
function updateDatabaseConfigSection(config) {
    const statusBadge = document.getElementById('db-connection-status');
    const initializeBtn = document.getElementById('initialize-db-btn');
    const statusDetails = document.getElementById('db-status-details');
    const statusJson = document.getElementById('db-status-json');
    
    if (config.database_connected) {
        statusBadge.textContent = 'Connected (Auto-configured)';
        statusBadge.className = 'badge bg-success ms-2';
        
        // Enable the initialize button for auto-configured setups
        initializeBtn.disabled = false;
        
        if (config.table_exists) {
            initializeBtn.textContent = 'Reinitialize Database';
            initializeBtn.className = 'btn btn-warning';
            initializeBtn.innerHTML = '<i class="fas fa-table me-2"></i>Reinitialize Database';
        } else {
            initializeBtn.textContent = 'Initialize Database';
            initializeBtn.className = 'btn btn-success';
            initializeBtn.innerHTML = '<i class="fas fa-table me-2"></i>Initialize Database';
        }
    } else {
        statusBadge.textContent = config.connection_message || 'Not Connected';
        statusBadge.className = 'badge bg-danger ms-2';
        initializeBtn.disabled = true;
    }
    
    // Show detailed status
    if (statusDetails && statusJson) {
        statusDetails.style.display = 'block';
        statusJson.textContent = JSON.stringify(config, null, 2);
    }
}

// Save database configuration
async function saveDatabaseConfig(event) {
    event.preventDefault();
    
    const config = {
        host: document.getElementById('db-host').value,
        port: parseInt(document.getElementById('db-port').value),
        database: document.getElementById('db-name').value,
        username: document.getElementById('db-user').value,
        password: document.getElementById('db-password').value,
        table: document.getElementById('db-table').value
    };
    
    // Validate required fields
    if (!config.host || !config.database || !config.username) {
        showAlert('Please fill in all required fields (Host, Database, Username)', 'danger');
        return;
    }
    
    // Handle auto-configured password
    if (config.password === 'auto_configured_placeholder') {
        // For auto-configured setups, get the password from environment
        // The backend will handle this
        config.password = ''; // Let backend use environment variable
    }
    
    try {
        // First test the connection
        const testResponse = await fetch('/api/config/database/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: new URLSearchParams({
                host: config.host,
                port: config.port,
                database: config.database,
                username: config.username,
                password: config.password
            })
        });
        
        const testResult = await testResponse.json();
        
        if (!testResponse.ok || !testResult.success) {
            showAlert(`Database connection test failed: ${testResult.message || 'Unknown error'}`, 'danger');
            return;
        }
        
        // If test passed, save the configuration
        const response = await fetch('/api/database/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showAlert('Database configuration saved and tested successfully!', 'success');
            // Refresh status to show updated connection state
            await loadSystemStatus();
        } else {
            showAlert(`Database configuration failed: ${result.error}`, 'danger');
        }
    } catch (error) {
        showAlert(`Error saving database configuration: ${error.message}`, 'danger');
    }
}



// Test database connection
async function testDatabaseConnection() {
    const config = {
        host: document.getElementById('db-host').value,
        port: parseInt(document.getElementById('db-port').value),
        database: document.getElementById('db-name').value,
        username: document.getElementById('db-user').value,
        password: document.getElementById('db-password').value,
        table: document.getElementById('db-table').value
    };
    
    // Handle auto-configured password - use a special indicator
    if (config.password === 'auto_configured_placeholder') {
        // For testing, we'll use the environment values
        showAlert('Using auto-configured database connection for test...', 'info');
        
        // Test with auto-detect endpoint instead
        try {
            const response = await fetch('/api/config/auto-detect');
            const result = await response.json();
            
            if (result.database_connected) {
                showAlert('Database connection successful (auto-configured)!', 'success');
                loadSystemStatus(); // Refresh status
            } else {
                showAlert(`Database connection failed: ${result.connection_message}`, 'danger');
            }
        } catch (error) {
            showAlert(`Error testing auto-configured connection: ${error.message}`, 'danger');
        }
        return;
    }
    
    try {
        const response = await fetch('/api/database/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showAlert('Database connection successful!', 'success');
            
            // Refresh status to show updated connection state
            await loadSystemStatus();
        } else {
            showAlert(`Database connection failed: ${result.error}`, 'danger');
        }
    } catch (error) {
        showAlert(`Error testing database connection: ${error.message}`, 'danger');
    }
}

// Initialize database (create tables)
async function initializeDatabase() {
    console.log('Initialize database function called');
    
    const initializeBtn = document.getElementById('initialize-db-btn');
    if (!initializeBtn) {
        console.error('Initialize button not found');
        showAlert('Initialize button not found', 'danger');
        return;
    }
    
    if (initializeBtn.disabled) {
        console.log('Initialize button is disabled, checking if we can enable it...');
        // Check if we have a database connection
        try {
            const statusResponse = await fetch('/api/config/auto-detect');
            const statusData = await statusResponse.json();
            
            if (statusData.database_connected) {
                console.log('Database is connected, enabling button');
                initializeBtn.disabled = false;
            } else {
                console.log('Database not connected, cannot initialize');
                showAlert('Database connection required before initialization. Please configure and test database connection first.', 'warning');
                return;
            }
        } catch (error) {
            console.error('Error checking database status:', error);
            showAlert('Unable to check database status. Please refresh the page and try again.', 'danger');
            return;
        }
    }
    
    if (!confirm('This will create/recreate the proxies table. Continue?')) {
        return;
    }
    
    const originalText = initializeBtn.innerHTML;
    initializeBtn.disabled = true;
    initializeBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Initializing...';
    
    try {
        console.log('Sending request to /api/database/initialize');
        const response = await fetch('/api/database/initialize', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const result = await response.json();
        console.log('Initialize response:', result);
        
        if (response.ok && result.success) {
            showAlert('Database initialized successfully!', 'success');
            await loadSystemStatus(); // Refresh status
        } else {
            showAlert(`Database initialization failed: ${result.error || 'Unknown error'}`, 'danger');
        }
    } catch (error) {
        console.error('Error initializing database:', error);
        showAlert(`Error initializing database: ${error.message}`, 'danger');
    } finally {
        initializeBtn.disabled = false;
        initializeBtn.innerHTML = originalText;
    }
}

// Refresh system status
async function refreshSystemStatus() {
    const refreshBtn = document.querySelector('button[onclick="refreshSystemStatus()"]');
    if (refreshBtn) {
        const originalHtml = refreshBtn.innerHTML;
        
        // Show loading state
        refreshBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Refreshing...';
        refreshBtn.disabled = true;
        
        try {
            await loadSystemStatus();
            showAlert('System status refreshed successfully', 'success');
        } catch (error) {
            showAlert('Error refreshing system status: ' + error.message, 'danger');
        } finally {
            // Restore button
            setTimeout(() => {
                refreshBtn.innerHTML = originalHtml;
                refreshBtn.disabled = false;
            }, 1000);
        }
    } else {
        await loadSystemStatus();
    }
}

// Update deployment info
function updateDeploymentInfo(autoDetectData) {
    const deploymentInfo = document.getElementById('deployment-info');
    const deploymentMode = document.getElementById('deployment-mode');
    
    if (deploymentInfo && deploymentMode) {
        deploymentMode.textContent = autoDetectData.deployment_mode || 'Unknown';
        deploymentInfo.style.display = 'block';
        
        // Add additional info based on deployment mode
        if (autoDetectData.deployment_mode === 'full') {
            deploymentInfo.className = 'alert alert-success';
            deploymentMode.textContent += ' (with PostgreSQL database)';
        } else {
            deploymentInfo.className = 'alert alert-info';
            deploymentMode.textContent += ' (manual configuration required)';
        }
    }
}

// Update API status
function updateApiStatus(apiConfig) {
    const statusElement = document.getElementById('api-status');
    const detailsElement = document.getElementById('api-details');
    
    if (statusElement) {
        let badgeClass = 'badge bg-warning';
        let text = 'Not Configured';
        
        switch(apiConfig.status) {
            case 'configured':
                badgeClass = 'badge bg-success';
                text = 'Configured';
                break;
            case 'error':
                badgeClass = 'badge bg-danger';
                text = 'Error';
                break;
        }
        
        statusElement.className = badgeClass;
        statusElement.textContent = text;
    }
    
    if (detailsElement) {
        if (apiConfig.message) {
            detailsElement.textContent = apiConfig.message;
            detailsElement.style.display = 'block';
        } else {
            detailsElement.style.display = 'none';
        }
    }
}

// Simple database status update function
function updateSimpleDatabaseStatus(dbStatus) {
    const statusElement = document.getElementById('database-status');
    const statusBadge = document.getElementById('db-connection-status');
    const initializeBtn = document.getElementById('initialize-db-btn');
    const statusDetails = document.getElementById('db-status-details');
    const statusJson = document.getElementById('db-status-json');
    
    let badgeClass = 'badge bg-warning';
    let text = 'Not Configured';
    let details = '';
    
    // Simple status logic based on the endpoint response
    if (dbStatus.working) {
        badgeClass = 'badge bg-success';
        text = 'Ready';
        details = dbStatus.message;
        
        // Enable initialize button when database is working
        if (initializeBtn) {
            initializeBtn.disabled = false;
            initializeBtn.className = 'btn btn-warning';
            initializeBtn.innerHTML = '<i class="fas fa-table me-2"></i>Reinitialize Database';
        }
    } else {
        if (dbStatus.status === 'not_configured') {
            badgeClass = 'badge bg-warning';
            text = 'Not Configured';
            details = 'Please configure database connection';
        } else if (dbStatus.status === 'error') {
            badgeClass = 'badge bg-danger';
            text = 'Connection Error';
            details = dbStatus.message;
        }
        
        // Disable initialize button when database is not working
        if (initializeBtn) {
            initializeBtn.disabled = true;
        }
    }
    
    // Update status elements
    if (statusElement) {
        statusElement.className = badgeClass;
        statusElement.textContent = text;
    }
    
    if (statusBadge) {
        statusBadge.className = badgeClass + ' ms-2';
        statusBadge.textContent = text;
    }
    
    if (statusDetails) {
        statusDetails.textContent = details;
        statusDetails.style.display = details ? 'block' : 'none';
    }
    
    if (statusJson) {
        statusJson.textContent = JSON.stringify(dbStatus, null, 2);
        if (statusJson.parentElement) {
            statusJson.parentElement.style.display = 'block';
        }
    }
}

// Update proxy status
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
        } else if (proxyConfig.enabled) {
            detailsElement.textContent = 'No proxies available in database';
        } else {
            detailsElement.textContent = 'Disabled - requires database configuration';
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

// Initialize full setup (for compose deployments)
async function initializeFullSetup() {
    const button = document.querySelector('button[onclick="initializeFullSetup()"]');
    const originalHtml = button.innerHTML;
    
    // Show loading state
    button.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Initializing...';
    button.disabled = true;
    
    try {
        const response = await fetch('/api/config/initialize-setup', {
            method: 'GET'
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            showAlert('Full setup initialized successfully! Database connected and proxies table created.', 'success');
            
            // Hide the initialize button
            const autoSetupElement = document.getElementById('database-auto-setup');
            if (autoSetupElement) {
                autoSetupElement.style.display = 'none';
            }
            
            // Refresh status
            await loadSystemStatus();
            
        } else {
            throw new Error(data.message || 'Failed to initialize setup');
        }
        
    } catch (error) {
        console.error('Error initializing setup:', error);
        showAlert('Error initializing setup: ' + error.message, 'danger');
    } finally {
        // Restore button
        button.innerHTML = originalHtml;
        button.disabled = false;
    }
}

// Provider field toggle function
function toggleProviderFields() {
    const provider = document.getElementById('provider').value;
    const apiKeyField = document.getElementById('api-key-field');
    const apiKeyInput = document.getElementById('api-key');
    
    // Configure fields based on provider
    switch(provider) {
        case 'openai':
            apiKeyField.style.display = 'block';
            apiKeyInput.required = true;
            break;
            
        case 'anthropic':
            apiKeyField.style.display = 'block';
            apiKeyInput.required = true;
            break;
            
        case 'ollama':
            apiKeyField.style.display = 'none';
            apiKeyInput.required = false;
            break;
            
        case 'azure':
            apiKeyField.style.display = 'block';
            apiKeyInput.required = true;
            break;
            
        case 'custom':
            apiKeyField.style.display = 'block';
            apiKeyInput.required = false;
            break;
            
        default:
            apiKeyField.style.display = 'block';
            apiKeyInput.required = true;
    }
}

// Save ScrapeGraph AI configuration
async function saveScrapeGraphConfig(event) {
    event.preventDefault();
    
    // Get form values
    const provider = document.getElementById('provider').value;
    const model = document.getElementById('model').value;
    const apiKey = document.getElementById('api-key').value;
    const temperature = document.getElementById('temperature').value;
    const maxTokens = document.getElementById('max-tokens').value;
    
    // Basic frontend validation
    if (!provider) {
        showAlert('Please select a provider', 'warning');
        return;
    }
    
    if (!model) {
        showAlert('Please enter a model name', 'warning');
        return;
    }
    
    if (provider !== 'ollama' && (!apiKey || apiKey.trim().length < 10)) {
        showAlert('Please enter a valid API key (at least 10 characters)', 'warning');
        return;
    }
    
    const formData = new FormData();
    formData.append('provider', provider);
    formData.append('model', model);
    formData.append('api_key', apiKey.trim());
    formData.append('temperature', temperature);
    
    // Only add max_tokens if it has a value
    if (maxTokens && maxTokens.trim()) {
        formData.append('max_tokens', maxTokens.trim());
    }
    
    try {
        const response = await fetch('/api/config/scrapegraph', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showAlert('ScrapeGraph AI configuration saved successfully!', 'success');
            await loadSystemStatus();
        } else {
            // Handle different types of errors
            let errorMessage = 'Failed to save configuration';
            
            if (data.detail) {
                errorMessage = data.detail;
            } else if (data.error) {
                errorMessage = data.error;
            } else if (data.message) {
                errorMessage = data.message;
            }
            
            throw new Error(errorMessage);
        }
        
    } catch (error) {
        console.error('Error saving ScrapeGraph AI config:', error);
        showAlert('Error saving configuration: ' + error.message, 'danger');
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
        
        if (response.ok) {
            showAlert('ScrapeGraph AI configuration deleted successfully!', 'success');
            
            // Reset form
            document.getElementById('scrapegraph-config-form').reset();
            
            await loadSystemStatus();
        } else {
            throw new Error('Failed to delete configuration');
        }
        
    } catch (error) {
        console.error('Error deleting ScrapeGraph AI config:', error);
        showAlert('Error deleting configuration: ' + error.message, 'danger');
    }
}

// Delete database configuration
async function deleteDatabaseConfig() {
    if (!confirm('Are you sure you want to delete the database configuration?')) {
        return;
    }
    
    try {
        const response = await fetch('/api/config/database', {
            method: 'DELETE'
        });
        
        if (response.ok) {
            showAlert('Database configuration deleted successfully!', 'success');
            
            // Reset form
            document.getElementById('database-config-form').reset();
            
            // Hide create table button
            const createTableBtn = document.getElementById('create-table-btn');
            if (createTableBtn) {
                createTableBtn.style.display = 'none';
            }
            
            await loadSystemStatus();
        } else {
            throw new Error('Failed to delete database configuration');
        }
        
    } catch (error) {
        console.error('Error deleting database config:', error);
        showAlert('Error deleting database configuration: ' + error.message, 'danger');
    }
}

// Toggle proxy usage
async function toggleProxyUsage() {
    const toggle = document.getElementById('proxy-toggle');
    
    try {
        const formData = new FormData();
        formData.append('enabled', toggle.checked);
        
        const response = await fetch('/api/config/proxy/toggle', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showAlert(`Proxy usage ${toggle.checked ? 'enabled' : 'disabled'} successfully!`, 'success');
            await loadSystemStatus();
        } else {
            // Revert toggle on error
            toggle.checked = !toggle.checked;
            throw new Error(data.detail || 'Failed to toggle proxy usage');
        }
        
    } catch (error) {
        console.error('Error toggling proxy usage:', error);
        showAlert('Error toggling proxy usage: ' + error.message, 'danger');
        // Revert toggle on error
        toggle.checked = !toggle.checked;
    }
}

// Scrape with specific method
async function scrapeWithMethod(method) {
    const url = document.getElementById('url').value;
    const useProxy = document.getElementById('use-proxy-test').checked;
    
    if (!url) {
        showAlert('Please enter a URL to scrape', 'warning');
        return;
    }
    
    const resultsDiv = document.getElementById('scrape-results');
    const resultsContent = document.getElementById('results-content');
    
    // Show loading state
    resultsContent.innerHTML = '<div class="text-center"><i class="fas fa-spinner fa-spin me-2"></i>Scraping content...</div>';
    resultsDiv.style.display = 'block';
    
    try {
        let endpoint;
        if (method === 'scrapegraph') {
            endpoint = '/api/scrape/scrapegraph';
        } else if (method === 'newsplease') {
            endpoint = '/api/scrape/newsplease';
        } else {
            endpoint = '/api/scrape/newspaper';
        }
        
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                url: url,
                use_proxy: useProxy
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // Display enhanced results with proper parsing
            resultsContent.innerHTML = formatScrapingResults(data, method);
        } else {
            throw new Error(data.detail || data.error || 'Scraping failed');
        }
        
    } catch (error) {
        console.error('Error scraping:', error);
        resultsContent.innerHTML = `
            <div class="alert alert-danger">
                <strong>Error:</strong> ${error.message}
            </div>
        `;
    }
}

// Format scraping results with enhanced display and metrics
function formatScrapingResults(data, method) {
    const content = data.content || {};
    
    // Calculate metrics
    const contentText = content.content || '';
    const characterCount = contentText.length;
    const wordCount = contentText.trim() ? contentText.trim().split(/\s+/).length : 0;
    
    // Build the enhanced result HTML
    let resultHtml = `
        <div class="alert alert-success mb-3">
            <strong>Success!</strong> Content scraped using ${method === 'newsplease' ? 'News-Please' : method === 'scrapegraph' ? 'ScrapeGraph AI' : 'Newspaper4k'}
        </div>
        
        <!-- Request Info -->
        <div class="card mb-3">
            <div class="card-header bg-light">
                <h6 class="mb-0"><i class="fas fa-info-circle me-2"></i>Request Information</h6>
            </div>
            <div class="card-body">
                <div class="row">
                    <div class="col-md-6">
                        <strong>URL:</strong> <small class="text-muted">${data.url}</small><br>
                        <strong>Method:</strong> ${method === 'newsplease' ? 'News-Please' : method === 'scrapegraph' ? 'ScrapeGraph AI' : 'Newspaper4k'}<br>
                        <strong>Proxy Used:</strong> ${data.proxy_used || 'None'}
                    </div>
                    <div class="col-md-6">
                        <strong>Content Metrics:</strong><br>
                        <span class="badge bg-primary me-2">${characterCount.toLocaleString()} characters</span>
                        <span class="badge bg-info">${wordCount.toLocaleString()} words</span>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Main content and metadata layout
    resultHtml += `<div class="row">`;
    
    // Left column - Content
    resultHtml += `
        <div class="col-md-8">
            <div class="card">
                <div class="card-header bg-light">
                    <h6 class="mb-0"><i class="fas fa-file-alt me-2"></i>Extracted Content</h6>
                </div>
                <div class="card-body">
    `;
    
    if (contentText) {
        resultHtml += `
            <div class="content-display" style="max-height: 500px; overflow-y: auto; line-height: 1.6;">
                ${contentText.replace(/\n/g, '<br>').replace(/\t/g, '&nbsp;&nbsp;&nbsp;&nbsp;')}
            </div>
        `;
    } else {
        resultHtml += `
            <div class="text-muted text-center py-4">
                <i class="fas fa-exclamation-triangle"></i> No content extracted
            </div>
        `;
    }
    
    resultHtml += `
                </div>
            </div>
        </div>
    `;
    
    // Right column - Metadata and Image
    resultHtml += `
        <div class="col-md-4">
    `;
    
    // Display image if available
    if (content.top_image) {
        resultHtml += `
            <div class="card mb-3">
                <div class="card-header bg-light">
                    <h6 class="mb-0"><i class="fas fa-image me-2"></i>Featured Image</h6>
                </div>
                <div class="card-body p-2">
                    <img src="${content.top_image}" 
                         class="img-fluid rounded" 
                         style="width: 100%; max-height: 200px; object-fit: cover;"
                         alt="Article image"
                         onerror="this.style.display='none'; this.nextElementSibling.style.display='block';">
                    <div class="text-muted text-center py-3" style="display: none;">
                        <i class="fas fa-image-slash"></i><br>Image failed to load
                    </div
                </div>
            </div>
        `;
    }
    
    // Display metadata
    resultHtml += `
        <div class="card">
            <div class="card-header bg-light">
                <h6 class="mb-0"><i class="fas fa-tags me-2"></i>Article Metadata</h6>
            </div>
            <div class="card-body">
    `;
    
    // Title
    if (content.title) {
        resultHtml += `
            <div class="mb-3">
                <strong>Title:</strong><br>
                <span class="text-primary">${content.title}</span>
            </div>
        `;
    }
    
    // Authors
    if (content.authors && content.authors.length > 0) {
        const authorsList = Array.isArray(content.authors) 
            ? content.authors.join(', ') 
            : content.authors;
        resultHtml += `
            <div class="mb-3">
                <strong>Authors:</strong><br>
                <span class="text-secondary">${authorsList}</span>
            </div>
        `;
    }
    
    // Publication date
    if (content.published) {
        const publishedDate = new Date(content.published);
        const formattedDate = publishedDate.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
        resultHtml += `
            <div class="mb-3">
                <strong>Published:</strong><br>
                <span class="text-success">${formattedDate}</span>
            </div>
        `;
    }
    
    // Summary if available
    if (content.summary && content.summary.trim()) {
        resultHtml += `
            <div class="mb-3">
                <strong>Summary:</strong><br>
                <div class="text-muted small" style="line-height: 1.4;">
                    ${content.summary.substring(0, 200)}${content.summary.length > 200 ? '...' : ''}
                </div>
            </div>
        `;
    }
    
    // Performance metrics
    resultHtml += `
        <div class="border-top pt-3 mt-3">
            <strong>Performance:</strong><br>
            <small class="text-muted">
                <div><i class="fas fa-chart-bar me-1"></i> ${characterCount.toLocaleString()} chars</div>
                <div><i class="fas fa-word-spacing me-1"></i> ${wordCount.toLocaleString()} words</div>
                <div><i class="fas fa-clock me-1"></i> ${method.charAt(0).toUpperCase() + method.slice(1)}</div>
            </small>
        </div>
    `;
    
    resultHtml += `
            </div>
        </div>
    </div>
    `;
    
    // Close the row
    resultHtml += `</div>`;
    
    // Raw JSON toggle (collapsed by default)
    resultHtml += `
        <div class="mt-3">
            <button class="btn btn-outline-secondary btn-sm" type="button" data-bs-toggle="collapse" data-bs-target="#rawJson" aria-expanded="false">
                <i class="fas fa-code me-1"></i> View Raw JSON
            </button>
            <div class="collapse mt-2" id="rawJson">
                <div class="card">
                    <div class="card-body">
                        <pre class="small text-muted mb-0" style="max-height: 300px; overflow-y: auto;">${JSON.stringify(data.content, null, 2)}</pre>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    return resultHtml;
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
    
    // Auto-remove after 5 seconds for success/info messages
    if (type === 'success' || type === 'info') {
        setTimeout(() => {
            if (alertDiv && alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 5000);
    }
}

// Debug function to test button functionality - call from browser console: debugInitializeButton()
function debugInitializeButton() {
    console.log('=== Initialize Button Debug ===');
    
    const initializeBtn = document.getElementById('initialize-db-btn');
    if (initializeBtn) {
        console.log('✓ Button found:', initializeBtn);
        console.log('  - Disabled:', initializeBtn.disabled);
        console.log('  - Classes:', initializeBtn.className);
        console.log('  - innerHTML:', initializeBtn.innerHTML);
        console.log('  - Style display:', initializeBtn.style.display);
        console.log('  - Computed display:', window.getComputedStyle(initializeBtn).display);
        
        // Check if the button has event listeners
        console.log('  - Event listeners attached:', initializeBtn.onclick !== null || initializeBtn.getAttribute('onclick') !== null);
        
        // Test if click event works
        console.log('Manual click test...');
        try {
            initializeBtn.click();
            console.log('✓ Click event triggered successfully');
        } catch (error) {
            console.error('✗ Click event failed:', error);
        }
    } else {
        console.error('✗ Button NOT found with ID "initialize-db-btn"');
        
        // Check for similar buttons
        const allButtons = document.querySelectorAll('button');
        console.log('All buttons on page:', allButtons);
        
        const initButtons = document.querySelectorAll('button[id*="init"], button[class*="init"]');
        console.log('Buttons with "init" in ID or class:', initButtons);
    }
    
    console.log('=== End Debug ===');
} 