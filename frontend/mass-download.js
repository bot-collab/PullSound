class MassDownloadManager {
    constructor() {
        this.isActive = false;
        this.isCancelled = false;
        this.urlsToDownload = [];
        this.zipCandidates = [];
        this.completedCount = 0;
        this.errorCount = 0;
        this.totalCount = 0;
        this.maxConcurrency = 3;
        this.activeTasksCount = 0;
        
        this.activeTasks = new Map();

        this.getDOMElements = () => ({
            modal: document.getElementById('massDownloadModal'),
            statusText: document.getElementById('massDownloadStatus'),
            progressFill: document.getElementById('massProgressFill'),
            progressText: document.getElementById('massProgressText'),
            currentTrack: document.getElementById('massCurrentTrack'),
            cancelBtn: document.getElementById('cancelMassDownloadBtn')
        });

        const els = this.getDOMElements();
        if (els.cancelBtn) {
            els.cancelBtn.addEventListener('click', () => this.cancel());
        }
    }

    async start() {
        if (this.isActive) return;
        
        const els = this.getDOMElements();
        if (!els.modal) return showNotification('Error UI: Modal no encontrado', 'error');

        this.isActive = true;
        this.isCancelled = false;
        this.urlsToDownload = [];
        this.zipCandidates = [];
        this.completedCount = 0;
        this.errorCount = 0;
        this.totalCount = 0;
        this.activeTasksCount = 0;
        this.activeTasks.clear();

        els.modal.style.display = 'flex';
        void els.modal.offsetWidth;
        els.modal.classList.add('show');
        
        this._updateUI('Preparando lote...', 0, 'Analizando playlist...');

        try {
            await this._extractAllUrlsSilently();
            if (this.isCancelled) return;

            this.totalCount = this.urlsToDownload.length;
            if (this.totalCount === 0) {
                this._closeModal();
                return showNotification('No se encontraron canciones para descargar', 'warning');
            }

            this._updateUI('Descarga Masiva en Curso', 0, `0 de ${this.totalCount} completados`);
            
            this._processQueue();

        } catch (e) {
            console.error('Error in MassDownload:', e);
            showNotification(e.message || 'Error', 'error');
            this._closeModal();
        }
    }

    cancel() {
        this.isCancelled = true;
        const els = this.getDOMElements();
        if (els.statusText) els.statusText.textContent = 'Cancelando lote...';
        
        for (const taskId of this.activeTasks.keys()) {
            if (globalThis.socket) {
                globalThis.socket.emit('leave', { taskId });
            }
            fetch(`${globalThis.API_BASE_URL}/cancel/${taskId}`, { method: 'POST' }).catch(() => {});
        }
        
        this._closeModal();
        showNotification('Lote de descargas cancelado', 'warning');
    }

    _closeModal() {
        this.isActive = false;
        const els = this.getDOMElements();
        if (els.modal) {
            els.modal.classList.remove('show');
            setTimeout(() => {
                els.modal.style.display = 'none';
            }, 400);
        }
    }

    _updateUI(status, progressPercent, trackText) {
        const els = this.getDOMElements();
        if (status && els.statusText) els.statusText.textContent = status;
        if (progressPercent !== null && els.progressFill) els.progressFill.style.width = `${progressPercent}%`;
        if (els.progressText) els.progressText.textContent = `${this.completedCount + this.errorCount} de ${this.totalCount} procesados`;
        if (trackText && els.currentTrack) els.currentTrack.textContent = trackText;
    }

    async _extractAllUrlsSilently() {
        const playlistUrl = globalThis.state?.playlistPagination?.url || document.getElementById('youtubeUrl')?.value;
        if (!playlistUrl) throw new Error('No hay URL de playlist activa');

        let offset = 0;
        const limit = 50; 
        let hasMore = true;
        const maxItems = 100; 

        while (hasMore && !this.isCancelled && this.urlsToDownload.length < maxItems) {
            const params = new URLSearchParams({ offset, limit });
            try {
                const res = await fetch(`${globalThis.API_BASE_URL}/info?${params.toString()}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: playlistUrl })
                });

                if (!res.ok) throw new Error('Error al extraer canciones');
                
                const info = await res.json();
                
                if (info.entries && info.entries.length > 0) {
                    for (const entry of info.entries) {
                        if (entry.url && this.urlsToDownload.length < maxItems) {
                            this.urlsToDownload.push({ url: entry.url, title: entry.title || 'Desconocido' });
                        }
                    }
                }
                
                hasMore = info.has_more && info.entries && info.entries.length > 0;
                offset = info.next_offset || (offset + limit);
                
                this._updateUI(`Preparando lote... (${this.urlsToDownload.length} extraídos)`, 0, 'Analizando páginas de la playlist...');
                
            } catch (e) {
                console.warn('Error fetching playlist page:', e);
                hasMore = false;
            }
        }
    }

    _processQueue() {
        if (this.isCancelled) return;

        if (this.completedCount + this.errorCount >= this.totalCount) {
            this._handleCompletion();
            return;
        }

        while (this.activeTasksCount < this.maxConcurrency && this.urlsToDownload.length > 0) {
            const track = this.urlsToDownload.shift();
            this._startSingleDownload(track);
        }
    }

    async _startSingleDownload(track) {
        this.activeTasksCount++;
        
        try {
            const response = await fetch(`${globalThis.API_BASE_URL}/download`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url: track.url,
                    format: globalThis.state.selectedFormat,
                    quality: globalThis.state.selectedQuality
                })
            });

            const data = await response.json();

            if (data.success && data.task_id) {
                this.activeTasks.set(data.task_id, track);
                if (globalThis.activeSocketRooms) globalThis.activeSocketRooms.add(data.task_id);
                if (globalThis.socket) globalThis.socket.emit('join', { taskId: data.task_id });
                this._updateUI(null, null, `Iniciando: ${track.title}`);
            } else {
                throw new Error(data.error || 'Fallo al encolar');
            }
        } catch (e) {
            console.error(`Error starting download for ${track.title}:`, e);
            this.errorCount++;
            this.activeTasksCount--;
            this._updateTotalProgress();
            this._processQueue();
        }
    }

    handleTaskStatusChange(taskId, status) {
        if (!this.activeTasks.has(taskId)) return false;

        const track = this.activeTasks.get(taskId);
        
        if (status.status === 'completed') {
            this.completedCount++;
            this.activeTasksCount--;
            this.activeTasks.delete(taskId);
            
            if (status.filename) {
                this.zipCandidates.push(status.filename);
            }
            
            this._updateTotalProgress();
            this._processQueue();
            return true;
        } 
        else if (status.status === 'error' || status.status === 'cancelled') {
            this.errorCount++;
            this.activeTasksCount--;
            this.activeTasks.delete(taskId);
            
            this._updateTotalProgress();
            this._processQueue();
            return true;
        }
        else {
            track.currentProgress = status.progress || 0;
            this._updateTotalProgress();
            this._updateUI(null, null, `Procesando: ${track.title} (${status.progress || 0}%)`);
            return true;
        }
    }

    _updateTotalProgress() {
        let totalProgress = (this.completedCount + this.errorCount) * 100;
        for (const track of this.activeTasks.values()) {
            totalProgress += (track.currentProgress || 0);
        }
        const progressPercent = totalProgress / this.totalCount;
        this._updateUI(null, progressPercent, null);
    }

    async _handleCompletion() {
        if (this.zipCandidates.length === 0) {
            this._closeModal();
            globalThis.showNotification('No se pudo descargar ninguna canción del lote', 'error');
            return;
        }

        this._updateUI('Comprimiendo ZIP...', 100, 'Generando archivo final...');
        
        try {
            const res = await fetch(`${globalThis.API_BASE_URL}/playlist/zip`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filenames: this.zipCandidates })
            });

            if (!res.ok) throw new Error('Error al crear ZIP');

            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'playlist_mass_download.zip';
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(url);

            this.zipCandidates.forEach((fn) => {
                if (globalThis.cleanupFile) globalThis.cleanupFile(fn);
            });
            
            globalThis.showNotification('¡Lote descargado exitosamente!', 'success');

        } catch (e) {
            console.error('ZIP error:', e);
            globalThis.showNotification('Descargas completas, pero falló la compresión ZIP', 'warning');
        } finally {
            this._closeModal();
        }
    }
}

// Add to global window space
globalThis.MassDownloadManager = MassDownloadManager;
