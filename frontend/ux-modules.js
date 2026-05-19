// ========== USER PREFERENCES MODULE ==========
class UserPreferences {
    constructor() {
        this.keys = {
            format: 'pullsound_preferred_format',
            quality: 'pullsound_preferred_quality',
            theme: 'pullsound_theme'
        };
    }

    save(format, quality) {
        try {
            localStorage.setItem(this.keys.format, format);
            localStorage.setItem(this.keys.quality, quality);
        } catch (e) {
            console.error('Error saving preferences:', e);
        }
    }

    load() {
        try {
            return {
                format: localStorage.getItem(this.keys.format) || 'mp3',
                quality: localStorage.getItem(this.keys.quality) || '320'
            };
        } catch (e) {
            console.error('Error loading preferences:', e);
            return { format: 'mp3', quality: '320' };
        }
    }

    clear() {
        Object.values(this.keys).forEach(key => localStorage.removeItem(key));
    }
}

// ========== DOWNLOAD HISTORY MODULE ==========
class DownloadHistory {
    constructor(maxItems = 20) {
        this.maxItems = maxItems;
        this.storageKey = 'pullsound_download_history';
    }

    add(title, url, format, quality) {
        try {
            const history = this.getAll();
            const entry = {
                id: Date.now(),
                title,
                url,
                format,
                quality,
                timestamp: new Date().toISOString()
            };
            
            // Add to beginning, keep only maxItems
            history.unshift(entry);
            const trimmed = history.slice(0, this.maxItems);
            
            localStorage.setItem(this.storageKey, JSON.stringify(trimmed));
            return entry;
        } catch (e) {
            console.error('Error adding to history:', e);
            return null;
        }
    }

    getAll() {
        try {
            const data = localStorage.getItem(this.storageKey);
            return data ? JSON.parse(data) : [];
        } catch (e) {
            console.error('Error loading history:', e);
            return [];
        }
    }

    clear() {
        localStorage.removeItem(this.storageKey);
    }

    remove(id) {
        try {
            const history = this.getAll().filter(item => item.id !== id);
            localStorage.setItem(this.storageKey, JSON.stringify(history));
        } catch (e) {
            console.error('Error removing from history:', e);
        }
    }

    renderHTML() {
        const history = this.getAll();
        if (history.length === 0) {
            return '<p class="empty-message">No hay descargas recientes</p>';
        }

        return history.map(item => {
            const date = new Date(item.timestamp);
            const timeAgo = this.getTimeAgo(date);
            const title = this.escapeHtml(item.title);
            
            return `
                <div class="history-item" data-id="${item.id}">
                    <div class="history-info">
                        <h4 class="history-title" title="${title}">${title}</h4>
                        <p class="history-meta">
                            <span class="badge">${item.format.toUpperCase()}</span>
                            <span class="badge">${item.quality}kbps</span>
                            <span class="time-ago">${timeAgo}</span>
                        </p>
                    </div>
                    <div class="history-actions">
                        <button class="history-btn" onClick="globalThis.redownloadFromHistory('${this.escapeAttr(item.url)}', '${item.format}', '${item.quality}')" title="Descargar de nuevo">
                            <i class="fas fa-redo"></i>
                        </button>
                        <button class="history-btn" onclick="globalThis.historyManager.remove(${item.id}); globalThis.updateHistoryPanel();" title="Eliminar">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
            `;
        }).join('');
    }

    getTimeAgo(date) {
        const baseMs = typeof date === 'number' ? date : date.getTime();
        const seconds = Math.floor((Date.now() - baseMs) / 1000);
        
        const intervals = {
            año: 31536000,
            mes: 2592000,
            semana: 604800,
            día: 86400,
            hora: 3600,
            minuto: 60
        };

        for (const [name, secondsCount] of Object.entries(intervals)) {
            const interval = Math.floor(seconds / secondsCount);
            if (interval >= 1) {
                return `Hace ${interval} ${name}${interval > 1 ? 's' : ''}`;
            }
        }
        
        return 'Hace un momento';
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    escapeAttr(text) {
        const s = String(text);
        return s.replaceAll("'", '&#39;').replaceAll('"', '&quot;');
    }
}

// ========== QUEUE MANAGER MODULE ==========
class QueueManager {
    constructor() {
        this.activeDownloads = new Map();
    }

    add(taskId, title, status = 'queued') {
        this.activeDownloads.set(taskId, {
            taskId,
            title,
            status,
            progress: 0,
            addedAt: Date.now()
        });
        this.updateBadge();
    }

    update(taskId, data) {
        if (this.activeDownloads.has(taskId)) {
            this.activeDownloads.set(taskId, {
                ...this.activeDownloads.get(taskId),
                ...data
            });
        }
    }

    remove(taskId) {
        this.activeDownloads.delete(taskId);
        this.updateBadge();
    }

    getAll() {
        return Array.from(this.activeDownloads.values());
    }

    clear() {
        this.activeDownloads.clear();
        this.updateBadge();
    }

    updateBadge() {
        const badge = document.getElementById('queueBadge');
        const count = this.activeDownloads.size;
        
        if (badge) {
            if (count > 0) {
                badge.textContent = count;
                badge.style.display = 'inline-block';
            } else {
                badge.style.display = 'none';
            }
        }
    }

    renderHTML() {
        const downloads = this.getAll();
        
        if (downloads.length === 0) {
            return '<p class="empty-message">No hay descargas activas</p>';
        }

        return downloads.map(item => {
            const statusIcon = this.getStatusIcon(item.status);
            const statusClass = this.getStatusClass(item.status);
            const title = this.escapeHtml(item.title || 'Descarga en proceso');
            
            return `
                <div class="queue-item ${statusClass}" data-task-id="${item.taskId}">
                    <div class="queue-info">
                        <h4 class="queue-title" title="${title}">${title}</h4>
                        <div class="queue-progress-bar">
                            <div class="queue-progress-fill" style="width: ${item.progress}%"></div>
                        </div>
                        <p class="queue-status">
                            <i class="${statusIcon}"></i>
                            ${item.message || this.getStatusText(item.status)} (${Math.round(item.progress)}%)
                        </p>
                    </div>
                </div>
            `;
        }).join('');
    }

    getStatusIcon(status) {
        const icons = {
            queued: 'fas fa-clock',
            downloading: 'fas fa-download',
            converting: 'fas fa-cog fa-spin',
            completed: 'fas fa-check-circle',
            error: 'fas fa-exclamation-circle',
            cancelled: 'fas fa-times-circle'
        };
        return icons[status] || 'fas fa-circle';
    }

    getStatusClass(status) {
        return `status-${status}`;
    }

    getStatusText(status) {
        const texts = {
            queued: 'En cola',
            downloading: 'Descargando',
            converting: 'Convirtiendo',
            completed: 'Completado',
            error: 'Error',
            cancelled: 'Cancelado'
        };
        return texts[status] || status;
    }

    escapeHtml(text) {
        const s = String(text);
        return s
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#39;');
    }
}

// ========== INITIALIZE MODULES ==========
const preferencesManager = new UserPreferences();
const historyManager = new DownloadHistory();
const queueManager = new QueueManager();

// Make globally accessible for inline event handlers
globalThis.historyManager = historyManager;
globalThis.queueManager = queueManager;
globalThis.preferencesManager = preferencesManager;

// ========== HELPER FUNCTIONS ==========
globalThis.updateHistoryPanel = function() {
    const historyContent = document.getElementById('historyContent');
    if (historyContent) {
        historyContent.innerHTML = historyManager.renderHTML();
    }
};

globalThis.updateQueuePanel = function() {
    const queueContent = document.getElementById('queueContent');
    if (queueContent) {
        queueContent.innerHTML = queueManager.renderHTML();
    }
};

globalThis.redownloadFromHistory = function(url, format, quality) {
    // Set preferences
    state.selectedFormat = format;
    state.selectedQuality = quality;
    
    // Update UI
    const formatBtn = document.querySelector(`[data-format="${format}"]`);
    const qualityBtn = document.querySelector(`[data-quality="${quality}"]`);
    
    if (formatBtn) {
        document.querySelectorAll('[data-format]').forEach(b => b.classList.remove('active'));
        formatBtn.classList.add('active');
    }
    
    if (qualityBtn) {
        document.querySelectorAll('[data-quality]').forEach(b => b.classList.remove('active'));
        qualityBtn.classList.add('active');
    }
    
    // Set URL and trigger download
    elements.urlInput.value = url;
    handleDownload();
    
    // Close history panel
    document.getElementById('historyPanel').style.display = 'none';
};

