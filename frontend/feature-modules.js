// ========== TIMESTAMP EXTRACTION MODULE ==========

// Note: API_BASE_URL is defined in script.js which loads first

class TimestampExtractor {
    startTime = 0;
    endTime = null;
    enabled = false;

    enable() {
        this.enabled = true;
        this.showUI();
    }

    disable() {
        this.enabled = false;
        this.hideUI();
    }

    showUI() {
        const container = document.getElementById('timestampControls');
        if (container) {
            container.style.display = 'block';
        }
    }

    hideUI() {
        const container = document.getElementById('timestampControls');
        if (container) {
            container.style.display = 'none';
        }
    }

    setTimeRange(start, end) {
        this.startTime = this.parseTime(start);
        this.endTime = this.parseTime(end);
    }

    parseTime(timeStr) {
        // Parse "mm:ss" or "hh:mm:ss" format
        if (!timeStr) return null;
        
        const parts = timeStr.split(':').map(Number);
        if (parts.length === 2) {
            return parts[0] * 60 + parts[1]; // mm:ss
        } else if (parts.length === 3) {
            return parts[0] * 3600 + parts[1] * 60 + parts[2]; // hh:mm:ss
        }
        return null;
    }

    formatTime(seconds) {
        if (!seconds && seconds !== 0) return '';
        
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = Math.floor(seconds % 60);
        
        if (h > 0) {
            return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
        }
        return `${m}:${String(s).padStart(2, '0')}`;
    }

    getFFmpegParams() {
        if (!this.enabled || (!this.startTime && !this.endTime)) {
            return {};
        }

        const params = {};
        if (this.startTime) {
            params.start_time = this.startTime;
        }
        if (this.endTime) {
            params.end_time = this.endTime;
        }
        return params;
    }

    getDuration() {
        if (this.startTime && this.endTime) {
            return this.endTime - this.startTime;
        }
        return null;
    }
}

// ========== AUDIO PREVIEW MODULE ==========
class AudioPreview {
    audio = null;
    isPlaying = false;
    currentObjectUrl = null;
    urlHistory = [];  // FIX: Track all URLs for cleanup

    async generate(url, duration = 30) {
        try {
            StateIndicator.show('Generando preview...', 'loading', 0);
            
            const response = await fetch(`${API_BASE_URL}/preview`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url, duration })
            });

            if (!response.ok) {
                throw new Error('Error generando preview');
            }

            const blob = await response.blob();
            
            // FIX: Validar que el blob no esté vacío (previene Range 416 y NotSupportedError)
            if (!blob || blob.size === 0) {
                throw new Error('Preview vacío o inválido');
            }

            // FIX: Asegurar MIME correcto sin anidar ternarios; usar optional chaining
            let audioBlob;
            const isAudioType = blob.type?.includes('audio');
            if (isAudioType) {
                audioBlob = (blob.type === 'audio/mpeg') ? blob : new Blob([blob], { type: 'audio/mpeg' });
            } else {
                audioBlob = new Blob([blob], { type: 'audio/mpeg' });
            }

            const audioUrl = URL.createObjectURL(audioBlob);
            
            // FIX: Cleanup ALL previous URLs
            this.revokeAllUrls();
            
            // FIX: Track new URL with timestamp
            this.currentObjectUrl = audioUrl;
            this.urlHistory.push({
                url: audioUrl,
                timestamp: Date.now()
            });

            // FIX: Auto-cleanup old URLs (> 1 min)
            this.cleanupOldUrls();

            return audioUrl;
            
        } catch (error) {
            StateIndicator.show(error.message, 'error');
            throw error;
        }
    }

    play(previewUrl) {
        if (this.audio) {
            this.stop();
        }

        this.audio = new Audio(previewUrl);
        this.audio.play();
        this.isPlaying = true;

        this.audio.onended = () => {
            this.isPlaying = false;
        };
    }

    stop() {
        if (this.audio) {
            this.audio.pause();
            this.audio.currentTime = 0;
            this.isPlaying = false;
            
            // FIX: Liberar referencia
            this.audio.src = '';
            this.audio = null;
        }
    }

    toggle(previewUrl) {
        if (this.isPlaying) {
            this.stop();
        } else {
            this.play(previewUrl);
        }
    }

    // FIX: Métodos auxiliares para cleanup
    revokeAllUrls() {
        this.urlHistory.forEach(entry => {
            try {
                URL.revokeObjectURL(entry.url);
            } catch (e) {
                console.warn('Failed to revoke URL:', e);
            }
        });
        this.urlHistory = [];
    }

    cleanupOldUrls() {
        const now = Date.now();
        const maxAge = 60 * 1000;  // 1 min
        
        this.urlHistory = this.urlHistory.filter(entry => {
            if (now - entry.timestamp > maxAge) {
                try {
                    URL.revokeObjectURL(entry.url);
                } catch (e) {
                    console.warn('Failed to revoke old URL:', e);
                }
                return false;  // Remove from history
            }
            return true;  // Keep
        });
    }

    // FIX: Destructor explícito
    destroy() {
        this.stop();
        this.revokeAllUrls();
        this.currentObjectUrl = null;
    }
}

// ========== METADATA EDITOR MODULE ==========
class MetadataEditor {
    constructor() {
        this.metadata = {
            title: '',
            artist: '',
            album: '',
            year: '',
            genre: ''
        };
    }

    open(currentTitle) {
        this.metadata.title = currentTitle;
        this.showModal();
    }

    showModal() {
        const modal = document.getElementById('metadataModal');
        if (modal) {
            // Populate fields
            document.getElementById('metaTitle').value = this.metadata.title;
            document.getElementById('metaArtist').value = this.metadata.artist;
            document.getElementById('metaAlbum').value = this.metadata.album;
            document.getElementById('metaYear').value = this.metadata.year;
            document.getElementById('metaGenre').value = this.metadata.genre;
            
            modal.style.display = 'flex';
        }
    }

    hideModal() {
        const modal = document.getElementById('metadataModal');
        if (modal) {
            modal.style.display = 'none';
        }
    }

    save() {
        this.metadata = {
            title: document.getElementById('metaTitle')?.value || '',
            artist: document.getElementById('metaArtist')?.value || '',
            album: document.getElementById('metaAlbum')?.value || '',
            year: document.getElementById('metaYear')?.value || '',
            genre: document.getElementById('metaGenre')?.value || ''
        };
        this.hideModal();
        return this.metadata;
    }

    getMetadata() {
        return this.metadata;
    }

    hasCustomMetadata() {
        return Object.values(this.metadata).some(v => v && v.trim() !== '');
    }
}

// ========== YOUTUBE SEARCH MODULE ==========
class YouTubeSearch {
    constructor(apiKey) {
        this.apiKey = apiKey;
        this.results = [];
    }

    async search(query, maxResults = 10) {
        if (!this.apiKey) {
            StateIndicator.show('YouTube API key no configurada', 'error');
            return [];
        }

        try {
            StateIndicator.show('Buscando...', 'loading', 0);
            
            // Use backend proxy to avoid CORS and hide API key
            const response = await fetch(`${API_BASE_URL}/search`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query, maxResults })
            });

            if (!response.ok) {
                throw new Error('Error en búsqueda');
            }

            const data = await response.json();
            this.results = data.results;
            
            StateIndicator.show(`${this.results.length} resultados encontrados`, 'success');
            return this.results;
            
        } catch (error) {
            StateIndicator.show(error.message, 'error');
            return [];
        }
    }

    renderResults() {
        if (this.results.length === 0) {
            return '<p class="empty-message">No se encontraron resultados</p>';
        }

        return this.results.map(result => `
            <div class="search-result-item" data-video-id="${result.id}">
                <img src="${result.thumbnail}" alt="${this.escapeHtml(result.title)}" class="search-thumb">
                <div class="search-info">
                    <h4 class="search-title">${this.escapeHtml(result.title)}</h4>
                    <p class="search-channel">${this.escapeHtml(result.channelTitle)}</p>
                    <p class="search-meta">${result.duration || 'N/A'}</p>
                </div>
                <button class="search-btn" onclick="globalThis.loadFromSearch('${result.url}')">
                    <i class="fas fa-download"></i>
                </button>
            </div>
        `).join('');
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize feature modules
const timestampExtractor = new TimestampExtractor();
const audioPreview = new AudioPreview();
const metadataEditor = new MetadataEditor();
const youtubeSearch = new YouTubeSearch(null); // API key loaded from config

// Make globally accessible
globalThis.timestampExtractor = timestampExtractor;
globalThis.audioPreview = audioPreview;
globalThis.metadataEditor = metadataEditor;
globalThis.youtubeSearch = youtubeSearch;

globalThis.loadFromSearch = function(url) {
    elements.urlInput.value = url;
    fetchVideoInfo(url);
    document.getElementById('searchPanel')?.classList.remove('show');
};

// ========== GLOBAL CLEANUP ==========
// FIX: Cleanup all Object URLs on page unload
globalThis.addEventListener('beforeunload', () => {
    if (globalThis.audioPreview) {
        globalThis.audioPreview.destroy();
    }
});

