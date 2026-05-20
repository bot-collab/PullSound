// FIX #13: Configuration constants
const CONFIG = {
    API_BASE_URL: '/api',
    CLEANUP_DELAY: 3000,
    NOTIFICATION_DURATION: 3000,
    DOWNLOAD_ALL_DELAY: 1000
};

const API_BASE_URL = CONFIG.API_BASE_URL;
const socket = io(); // Conectar a WebSocket

// ===== THEME TOGGLE FUNCTIONALITY =====
// Load theme from localStorage or default to dark
const currentTheme = localStorage.getItem('theme') || 'dark';
document.documentElement.dataset.theme = currentTheme;
document.body.dataset.theme = currentTheme;

// Update initialization to remove preload test file
document.addEventListener('DOMContentLoaded', () => {
    // Cleanup initialization
    const testAudio = document.getElementById('test-audio');
    if (testAudio) {
        testAudio.remove();
    }
});



// Theme toggle button
document.addEventListener('DOMContentLoaded', () => {
    const themeToggle = document.getElementById('themeToggle');

    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            const currentTheme = document.body.dataset.theme;
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';

            // Update theme
            document.documentElement.dataset.theme = newTheme;
            document.body.dataset.theme = newTheme;
            localStorage.setItem('theme', newTheme);

            // Optional: Add transition animation
            document.body.style.transition = 'background-color 0.3s ease, color 0.3s ease';
            setTimeout(() => {
                document.body.style.transition = '';
            }, 300);
        });
    }
});
// ========================================

// FIX #1: HTML sanitization helper (XSS prevention)
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// FIX #4: Track active socket rooms for cleanup
const activeSocketRooms = new Set();

const state = {
    selectedFormat: 'mp3',
    selectedQuality: '128',
    videoInfo: null,
    lastInfoUrl: null,
    isProcessing: false,
    currentTaskId: null,
    playlistEntries: [], // New: Store playlist entries
    activeTasks: {}, // New: Map taskId -> entryIndex/elementId
    massDownloadInProgress: false,
    massCancelRequested: false,
    massZipMode: false,
    zipCandidates: [],
    zipRequestSent: false,
    playlistStatus: {},
    playlistPagination: {
        url: null,
        offset: 0,
        limit: 10,
        total: null,
        hasMore: false,
        loading: false
    }
};

let playlistObserver = null;

const elements = {
    urlInput: document.getElementById('youtubeUrl'),
    clearBtn: document.getElementById('clearBtn'),
    downloadBtn: document.getElementById('convertBtn'), // FIX: Changed from 'downloadBtn' to 'convertBtn'

    videoPreview: document.getElementById('videoPreview'),
    thumbnail: document.getElementById('thumbnail'),
    videoTitle: document.getElementById('videoTitle'),
    videoMeta: document.getElementById('videoMeta'),
    progressContainer: document.getElementById('progressContainer'),
    progressFill: document.getElementById('progressFill'),
    progressText: document.getElementById('progressText'),
    qualitySection: document.getElementById('qualitySection'),
    formatBtns: document.querySelectorAll('[data-format]'),
    qualityBtns: document.querySelectorAll('[data-quality]'),
    playlistSection: document.getElementById('playlistSection'), // New
    playlistContainer: document.getElementById('playlistContainer'), // New
    downloadAllBtn: document.getElementById('downloadAllBtn') // New
};

socket.on('connect', () => {
    // Connected to WebSocket
});

// FIX #14: Handle socket disconnection
socket.on('disconnect', () => {
    showNotification('Conexión perdida. Reconectando...', 'warning');
});

socket.on('reconnect', () => {
    showNotification('Conexión restaurada', 'success');
});

socket.on('status_update', (data) => {
    if (data.task_id) {
        handleStatusUpdate(data);
    }
});

function handleStatusUpdate(status) {
    const taskId = status.task_id;

    // Check if it's the main single download
    if (taskId === state.currentTaskId) {
        updateMainProgress(status);
        return;
    }

    // Check if it's a mass download task
    if (globalThis.massDownloadManager && globalThis.massDownloadManager.isActive) {
        if (globalThis.massDownloadManager.handleTaskStatusChange(taskId, status)) {
            return;
        }
    }

    // Check if it's a playlist item
    const entryElement = document.querySelector(`.playlist-item[data-task-id="${taskId}"]`);
    if (entryElement) {
        updatePlaylistProgress(entryElement, status);
    }
}

function updateMainProgress(status) {
    const progress = status.progress || 0;
    const message = status.message || 'Procesando...';

    elements.progressFill.style.width = progress + '%';
    elements.progressText.textContent = message;

    if (status.status === 'completed') {
        downloadFile(status.filename);
        showNotification('Audio descargado exitosamente', 'success');
        setTimeout(() => {
            cleanupFile(status.filename);
            resetDownloadUI();
        }, 3000);
    } else if (status.status === 'error') {
        showNotification(status.error || status.message || 'Error', 'error');
        resetDownloadUI();
    } else if (status.status === 'cancelled') {
        showNotification('Cancelado', 'info');
        resetDownloadUI();
    }
}

// ========== PLAYLIST PROGRESS HELPERS (extracted to reduce complexity) ==========
function _updateProgressUI(progressBar, progressFill, statusText, clampedProgress, message) {
    progressBar.style.display = 'block';
    progressFill.style.width = clampedProgress + '%';

    if (statusText) {
        statusText.style.display = 'block';
        let msg = message || '';
        if (msg.includes('Descargando:')) msg = msg.replace('Descargando:', '').trim();
        statusText.textContent = `${Math.round(clampedProgress)}% - ${msg}`;
    }
}

function _getOrCreateButton(actionsDiv, fromClass, toClass) {
    let btn = actionsDiv.querySelector(`.${fromClass}`);
    if (!btn) {
        btn = actionsDiv.querySelector(`.${toClass}`);
    }
    return btn;
}

function _updateButtonToCancelState(btn, taskId) {
    if (btn?.classList.contains('btn-download-item')) {
        btn.className = 'option-btn btn-sm btn-cancel-item';
        btn.innerHTML = '<i class="fas fa-times"></i>';
        btn.title = "Cancelar";
        btn.onclick = () => cancelTask(taskId);
        btn.disabled = false;
        btn.style.display = 'block';
        btn.style.background = 'rgba(255, 50, 50, 0.2)';
    }
}

function _handleCompletedState(element, progressFill, statusText, actionsDiv, filename, dataIndex) {
    progressFill.style.width = '100%';
    progressFill.style.background = '#48bb78';
    element.classList.add('completed');

    if (statusText) {
        statusText.textContent = 'Completado';
        statusText.style.color = '#48bb78';
        statusText.style.display = 'block';
    }

    if (filename) {
        if (state.massZipMode) {
            if (!state.zipCandidates.includes(filename)) {
                state.zipCandidates.push(filename);
            }
            if (statusText) {
                statusText.textContent = 'Listo para ZIP';
                statusText.style.color = '#63b3ed';
            }
        } else {
            downloadFile(filename);
            setTimeout(() => cleanupFile(filename), 10000);
        }
    }

    const btn = _getOrCreateButton(actionsDiv, 'btn-cancel-item', 'btn-download-item');
    if (btn) {
        btn.className = 'option-btn btn-sm btn-download-item';
        btn.style.display = 'block';
        btn.style.background = 'rgba(72, 187, 120, 0.2)';
        btn.innerHTML = '<i class="fas fa-check"></i>';
        btn.title = "Descargado";
        btn.onclick = () => downloadSingleItem(dataIndex);
        btn.disabled = false;
    }
}

function _handleErrorOrCancelledState(statusText, actionsDiv, status, dataIndex) {
    if (statusText) {
        statusText.textContent = status.status === 'error' ? 'Error' : 'Cancelado';
        statusText.style.color = '#fc8181';
    }

    const btn = _getOrCreateButton(actionsDiv, 'btn-cancel-item', 'btn-download-item');
    if (btn) {
        btn.className = 'option-btn btn-sm btn-download-item';
        btn.style.display = 'block';
        btn.style.background = '';
        btn.disabled = false;
        btn.onclick = () => downloadSingleItem(dataIndex);

        if (status.status === 'error') {
            btn.innerHTML = '<i class="fas fa-exclamation-triangle"></i>';
            btn.title = "Error: " + (status.message || 'Desconocido');
        } else {
            btn.innerHTML = '<i class="fas fa-redo"></i>';
            btn.title = "Cancelado. Reintentar?";
        }
    }
}

function updatePlaylistProgress(element, status) {
    const actionsDiv = element.querySelector('.playlist-actions');
    const progressBar = element.querySelector('.item-progress');
    const progressFill = element.querySelector('.item-progress-fill');
    const statusText = element.querySelector('.item-status-text');
    const clampedProgress = Math.min(100, Math.max(0, status.progress || 0));
    const idx = element.dataset.index;
    if (idx !== undefined) {
        if (status.status === 'completed') {
            setPlaylistStatus(idx, 'completed');
        } else if (status.status === 'error') {
            setPlaylistStatus(idx, 'error');
        } else if (status.status === 'cancelled') {
            setPlaylistStatus(idx, 'cancelled');
        } else if (status.status) {
            setPlaylistStatus(idx, 'downloading');
        }
    }

    if (status.status === 'downloading' || status.status === 'converting' || status.status === 'starting') {
        _updateProgressUI(progressBar, progressFill, statusText, clampedProgress, status.message);
        const btn = _getOrCreateButton(actionsDiv, 'btn-download-item', 'btn-cancel-item');
        _updateButtonToCancelState(btn, status.task_id);
    } else if (status.status === 'completed') {
        _handleCompletedState(element, progressFill, statusText, actionsDiv, status.filename, element.dataset.index);
    } else if (status.status === 'error' || status.status === 'cancelled') {
        progressBar.style.display = 'none';
        _handleErrorOrCancelledState(statusText, actionsDiv, status, element.dataset.index);
    }
}

function setPlaylistStatus(index, status) {
    state.playlistStatus[index] = status;
    // Delegate to MassDownloadManager if active
    if (globalThis.massDownloadManager && globalThis.massDownloadManager.isActive) {
        globalThis.massDownloadManager.handleTaskStatusChange(index, status);
    }
}

function renderPlaylist(entries, options = {}) {
    const { append = false, startIndex = state.playlistEntries.length } = options;

    elements.playlistSection.style.display = 'block';

    if (!append) {
        // Reset container and state when starting a new playlist
        elements.playlistContainer.innerHTML = '';
        state.playlistEntries = [];
        state.playlistStatus = {};
        state.zipCandidates = [];
    }

    entries.forEach((entry, localIdx) => {
        if (!entry?.url) return;

        const globalIndex = startIndex + localIdx;
        state.playlistStatus[globalIndex] = 'pending';
        state.playlistEntries[globalIndex] = entry;

        const item = document.createElement('div');
        item.className = 'playlist-item';
        item.dataset.url = entry.url;
        item.dataset.title = entry.title || 'Sin título';
        item.dataset.index = globalIndex;

        const thumbSrc = entry.thumbnail || 'https://cdn-icons-png.flaticon.com/512/565/565267.png';

        const progressDiv = document.createElement('div');
        progressDiv.className = 'item-progress';
        const progressFill = document.createElement('div');
        progressFill.className = 'item-progress-fill';
        progressDiv.appendChild(progressFill);

        const thumbContainer = document.createElement('div');
        thumbContainer.className = 'playlist-thumb-container';
        thumbContainer.onclick = function (e) {
            e.stopPropagation();
            togglePlaylistPreview(entry.url, globalIndex);
        };

        const thumb = document.createElement('img');
        thumb.loading = 'lazy';
        thumb.src = thumbSrc;
        thumb.className = 'playlist-thumb';
        thumb.alt = 'Thumbnail';
        thumb.onerror = function () {
            this.src = 'https://cdn-icons-png.flaticon.com/512/565/565267.png';
        };

        const overlay = document.createElement('div');
        overlay.className = 'preview-overlay';
        overlay.innerHTML = '<i class="fas fa-play"></i>';

        thumbContainer.appendChild(thumb);
        thumbContainer.appendChild(overlay);

        const info = document.createElement('div');
        info.className = 'playlist-info';

        const h4 = document.createElement('h4');
        h4.textContent = entry.title || 'Sin título';
        h4.title = entry.title || '';

        const meta = document.createElement('div');
        meta.className = 'playlist-meta';
        meta.textContent = entry.duration ? formatDuration(entry.duration) : '';

        const statusText = document.createElement('div');
        statusText.className = 'item-status-text';

        info.appendChild(h4);
        info.appendChild(meta);
        info.appendChild(statusText);

        const actions = document.createElement('div');
        actions.className = 'playlist-actions';

        const btn = document.createElement('button');
        btn.className = 'option-btn btn-sm btn-download-item';
        const icon = document.createElement('i');
        icon.className = 'fas fa-download';
        btn.appendChild(icon);
        actions.appendChild(btn);

        item.appendChild(progressDiv);
        item.appendChild(thumbContainer);
        item.appendChild(info);
        item.appendChild(actions);

        elements.playlistContainer.appendChild(item);
    });

    ensurePlaylistSentinel();
}

function ensurePlaylistSentinel() {
    if (!elements.playlistContainer) return;

    let sentinel = document.getElementById('playlist-load-more');
    if (sentinel) {
        // Move sentinel to the end to keep observer accurate after re-renders
        sentinel.remove();
    } else {
        sentinel = document.createElement('div');
        sentinel.id = 'playlist-load-more';
        sentinel.style.height = '1px';
        sentinel.style.width = '100%';
        sentinel.style.marginTop = '1px';
    }

    elements.playlistContainer.appendChild(sentinel);

    if (playlistObserver) {
        playlistObserver.observe(sentinel);
        return;
    }

    playlistObserver = new IntersectionObserver((entries) => {
        if (entries?.[0]?.isIntersecting) {
            loadMorePlaylistEntries();
        }
    }, {
        root: null,
        rootMargin: '400px 0px',
        threshold: 0
    });

    playlistObserver.observe(sentinel);
}

globalThis.downloadSingleItem = async function (index) {
    const itemElement = elements.playlistContainer.querySelector(`.playlist-item[data-index="${index}"]`);
    if (!itemElement) return;

    // FIX #6: Prevent double download
    if (itemElement.classList.contains('completed') || itemElement.classList.contains('downloading')) {
        return;
    }

    // FIX #3: Use data attributes instead of array index (more robust)
    const url = itemElement.dataset.url;

    if (!url) return;

    const btn = itemElement.querySelector('.btn-download-item');

    try {
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        itemElement.classList.add('downloading');

        const response = await fetch(`${API_BASE_URL}/download`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url: url,
                format: state.selectedFormat,
                quality: state.selectedQuality
            })
        });

        const data = await response.json();

        if (data.success) {
            // FIX #4: Leave old room if exists
            const oldTaskId = itemElement.dataset.taskId;
            if (oldTaskId && activeSocketRooms.has(oldTaskId)) {
                socket.emit('leave', { taskId: oldTaskId });
                activeSocketRooms.delete(oldTaskId);
            }

            // Set new task ID
            itemElement.dataset.taskId = data.task_id;
            activeSocketRooms.add(data.task_id);

            showNotification('Descarga iniciada', 'info');

            // Join the socket room for this task
            socket.emit('join', { taskId: data.task_id });

            // Initial UI update
            updatePlaylistProgress(itemElement, {
                status: 'starting',
                progress: 0,
                task_id: data.task_id
            });

        } else {
            throw new Error(data.error || 'Error al iniciar descarga');
        }
    } catch (e) {
        console.error(e);
        btn.innerHTML = '<i class="fas fa-times"></i>';
        btn.disabled = false;
        itemElement.classList.remove('downloading');
    }
}

async function handleDownloadAll() {
    if (!state.playlistPagination.url && !document.getElementById('youtubeUrl')?.value) return;

    if (!globalThis.massDownloadManager) {
        globalThis.massDownloadManager = new MassDownloadManager();
    }
    await globalThis.massDownloadManager.start();
}





// ========== PLAYLIST PREVIEW HANDLER ==========
async function togglePlaylistPreview(url, index) {
    if (typeof AudioPreview === 'undefined') {
        return showNotification('Módulo de preview no cargado', 'error');
    }

    if (!globalThis.audioPreview) {
        globalThis.audioPreview = new AudioPreview();
    }

    const items = document.querySelectorAll('.playlist-item');
    const targetItem = items[index];
    if (!targetItem) return;

    const thumbContainer = targetItem.querySelector('.playlist-thumb-container');
    const icon = thumbContainer.querySelector('i');
    const progressBar = targetItem.querySelector('.item-progress');
    const progressFill = targetItem.querySelector('.item-progress-fill');

    // Check if clicking the same currently playing song
    if (state.playingPreviewIndex === index && globalThis.audioPreview.isPlaying) {
        globalThis.audioPreview.stop();
        state.playingPreviewIndex = null;

        // Reset UI
        thumbContainer.classList.remove('playing');
        icon.className = 'fas fa-play';
        progressBar.classList.remove('playing-preview');
        return;
    }

    // Stop accumulated playing song (if any different one)
    if (state.playingPreviewIndex !== null && state.playingPreviewIndex !== index) {
        // Find previous item and reset
        const prevItem = items[state.playingPreviewIndex];
        if (prevItem) {
            const prevContainer = prevItem.querySelector('.playlist-thumb-container');
            const prevIcon = prevContainer.querySelector('i');
            const prevBar = prevItem.querySelector('.item-progress');

            prevContainer.classList.remove('playing');
            prevIcon.className = 'fas fa-play';
            prevBar.classList.remove('playing-preview');
            const prevFill = prevBar.querySelector('.item-progress-fill');
            if (prevFill) prevFill.style.width = '0%';
        }
        globalThis.audioPreview.stop();
    }

    // Start new preview
    try {
        thumbContainer.classList.add('playing');
        icon.className = 'fas fa-spinner fa-spin'; // Loading state

        // Setup progress bar reuse
        progressBar.classList.add('playing-preview');
        progressFill.style.width = '0%';

        // Generate and Play
        const previewUrl = await globalThis.audioPreview.generate(url);
        globalThis.audioPreview.play(previewUrl);
        state.playingPreviewIndex = index;

        icon.className = 'fas fa-pause';

        // Bind time update
        globalThis.audioPreview.audio.ontimeupdate = () => {
            const audio = globalThis.audioPreview.audio;
            // FIX: Check if audio object still exists before accessing properties
            if (audio && !Number.isNaN(audio.duration) && audio.duration > 0) {
                const percent = (audio.currentTime / audio.duration) * 100;
                progressFill.style.width = percent + '%';
            }
        };

        // Handle finish
        globalThis.audioPreview.audio.onended = () => {
            globalThis.audioPreview.isPlaying = false;
            state.playingPreviewIndex = null;

            thumbContainer.classList.remove('playing');
            icon.className = 'fas fa-play';
            progressBar.classList.remove('playing-preview');
            progressFill.style.width = '0%';
        };

    } catch (e) {
        console.error('Playlist preview error:', e);
        showNotification('Error reproduciendo preview', 'error');
        thumbContainer.classList.remove('playing');
        icon.className = 'fas fa-exclamation-triangle';
        setTimeout(() => icon.className = 'fas fa-play', 2000);
    }
}

async function loadMorePlaylistEntries() {
    const { url, offset, limit, hasMore, loading } = state.playlistPagination;
    if (!url || loading || !hasMore) return;

    state.playlistPagination.loading = true;

    try {
        const params = new URLSearchParams({ offset, limit });
        const res = await fetch(`${API_BASE_URL}/info?${params.toString()}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });

        if (!res.ok) throw new Error('Error obteniendo info');

        const data = await res.json();
        displayVideoInfo(data, { append: true });

    } catch (e) {
        console.error('Load more error:', e);
        showNotification('No se pudo cargar más elementos', 'error');
        state.playlistPagination.hasMore = false;
    } finally {
        state.playlistPagination.loading = false;
    }
}

async function handleDownload() {
    const url = elements.urlInput.value.trim();
    if (!url) return showNotification('URL requerida', 'error');

    // FIX: Prevenir descarga corrupta de playlists enteras en el botón individual
    if (state.playlistEntries.length > 0 && state.lastInfoUrl === url) {
        showNotification('Para playlists, utiliza el botón "Descargar Todo"', 'warning');
        return;
    }

    if (state.isProcessing) return;

    // FIX #4: Leave old room if exists
    if (state.currentTaskId && activeSocketRooms.has(state.currentTaskId)) {
        socket.emit('leave', { taskId: state.currentTaskId });
        activeSocketRooms.delete(state.currentTaskId);
    }

    state.isProcessing = true;
    elements.downloadBtn.disabled = true;
    elements.progressContainer.style.display = 'block';

    try {
        updateMainProgress({ progress: 0, message: 'Iniciando...' });

        const response = await fetch(`${API_BASE_URL}/download`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url: url,
                format: state.selectedFormat,
                quality: state.selectedQuality
            })
        });

        if (!response.ok) throw new Error(await response.text());

        const data = await response.json();
        state.currentTaskId = data.task_id;
        activeSocketRooms.add(data.task_id);

        socket.emit('join', { taskId: state.currentTaskId });

    } catch (error) {
        showNotification(error.message, 'error');
        resetDownloadUI();
    }
}

async function handleCancel() {
    if (state.currentTaskId) {
        await cancelTask(state.currentTaskId);
    }
}

async function cancelTask(taskId) {
    if (!taskId) return;
    try {
        await fetch(`${API_BASE_URL}/cancel/${taskId}`, { method: 'POST' });
    } catch (e) {
        console.error("Error cancelling task:", e);
    }
}

function resetDownloadUI() {
    state.isProcessing = false;
    state.currentTaskId = null;
    elements.downloadBtn.disabled = false;
    elements.progressContainer.style.display = 'none';
}

function displayVideoInfo(info, options = {}) {
    const { append = false } = options;

    if (info.is_playlist) {
        elements.videoPreview.style.display = 'none';

        const entries = info.entries || [];
        const startIndex = append ? state.playlistEntries.length : (info.offset || 0);

        renderPlaylist(entries, { append, startIndex });

        const nextOffset = (info.offset || 0) + entries.length;
        const total = info.count ?? state.playlistPagination.total ?? entries.length;
        const hasMore = Boolean(info.has_more ?? (total ? nextOffset < total : false));

        state.playlistPagination = {
            ...state.playlistPagination,
            offset: nextOffset,
            limit: info.limit || state.playlistPagination.limit || 10,
            total,
            hasMore,
            loading: false
        };

        showNotification(append ? 'Más elementos cargados' : 'Playlist cargada exitosamente', 'success');

    } else {
        elements.playlistSection.style.display = 'none';

        elements.thumbnail.src = info.thumbnail;
        elements.videoTitle.textContent = info.title;

        const duration = formatDuration(info.duration);
        const views = info.view_count ? ` - ${formatViews(info.view_count)} vistas` : '';
        elements.videoMeta.textContent = `${info.uploader} - ${duration}${views}`;
        elements.videoPreview.style.display = 'flex';

        state.playlistPagination = {
            ...state.playlistPagination,
            url: null,
            offset: 0,
            total: null,
            hasMore: false,
            loading: false
        };

        // Stop any playing preview when loading new video info
        if (globalThis.audioPreview?.isPlaying) {
            globalThis.audioPreview.stop();
        }
    }

    state.lastInfoUrl = state.playlistPagination.url;
}

// Event Listeners
function init() {
    if (elements.urlInput) {
        elements.urlInput.addEventListener('input', (e) => {
            if (elements.clearBtn) {
                elements.clearBtn.style.display = e.target.value ? 'flex' : 'none';
            }
        });

        elements.urlInput.addEventListener('keydown', (e) => {
            if (e.key !== 'Enter') return;
            const url = elements.urlInput.value.trim();
            if (!url) {
                showNotification('URL requerida', 'error');
                return;
            }
            if (!isValidMediaUrl(url)) {
                showNotification('URL no soportada', 'error');
                return;
            }
            e.preventDefault();
            fetchVideoInfo(url);
        });
    }

    if (elements.clearBtn) {
        elements.clearBtn.addEventListener('click', () => {
            if (elements.urlInput) elements.urlInput.value = '';
            elements.clearBtn.style.display = 'none';
            if (elements.videoPreview) elements.videoPreview.style.display = 'none';
            if (elements.playlistSection) elements.playlistSection.style.display = 'none';
            state.playlistEntries = [];
            state.playlistStatus = {};
            state.playlistPagination = {
                ...state.playlistPagination,
                url: null,
                offset: 0,
                total: null,
                hasMore: false,
                loading: false
            };
        });
    }

    if (elements.urlInput) {
        elements.urlInput.addEventListener('paste', (e) => {
            setTimeout(() => {
                const url = e.target.value.trim();
                if (isValidMediaUrl(url)) fetchVideoInfo(url);
            }, 100);
        });
    }

    if (elements.downloadBtn) {
        elements.downloadBtn.addEventListener('click', async () => {
            const url = elements.urlInput.value.trim();
            if (!url) return showNotification('URL requerida', 'error');
            if (!isValidMediaUrl(url)) return showNotification('URL no soportada', 'error');

            // Intenta traer info antes de descargar para asegurar preview/playlist
            try {
                if (state.lastInfoUrl !== url) {
                    await fetchVideoInfo(url);
                }
            } catch (e) {
                // Si falla info, notifícalo y no continúes a descargar
                console.warn('No se pudo obtener info antes de descargar:', e);
                showNotification('No se pudo obtener información del video', 'error');
                return;
            }

            handleDownload();
        });
    }


    const cancelBtn = document.getElementById('cancelDownloadBtn');
    if (cancelBtn) cancelBtn.addEventListener('click', handleCancel);

    if (elements.downloadAllBtn) {
        elements.downloadAllBtn.addEventListener('click', handleDownloadAll);
    }

    // FIX #2: Event delegation for playlist items (prevents memory leaks on re-render)
    if (elements.playlistContainer) {
        elements.playlistContainer.addEventListener('click', (e) => {
            const btn = e.target.closest('.btn-download-item, .btn-cancel-item');
            if (!btn) return;

            const item = btn.closest('.playlist-item');
            if (!item) return;

            if (btn.classList.contains('btn-cancel-item')) {
                // Cancel button clicked
                const taskId = item.dataset.taskId;
                if (taskId) cancelTask(taskId);
            } else {
                // Download button clicked
                const index = Number.parseInt(item.dataset.index, 10);
                if (!Number.isNaN(index)) downloadSingleItem(index);
            }
        });
    }

    if (elements.formatBtns) {
        elements.formatBtns.forEach(btn => btn.addEventListener('click', () => {
            elements.formatBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.selectedFormat = btn.dataset.format;

            const losslessFormats = ['flac', 'wav'];
            if (elements.qualitySection) {
                if (losslessFormats.includes(state.selectedFormat)) {
                    elements.qualitySection.style.opacity = '0.5';
                    elements.qualitySection.style.pointerEvents = 'none';
                } else {
                    elements.qualitySection.style.opacity = '1';
                    elements.qualitySection.style.pointerEvents = 'auto';
                }
            }
        }));
    }

    if (elements.qualityBtns) {
        elements.qualityBtns.forEach(btn => btn.addEventListener('click', () => {
            elements.qualityBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.selectedQuality = btn.dataset.quality;
        }));
    }
}

function isValidMediaUrl(url) {
    return /^(https?:\/\/)?((www|music|m|open)\.)?(youtube\.com|youtu\.be|soundcloud\.com|spotify\.com)\/.+$/i.test(url);
}

async function fetchVideoInfo(url, options = {}) {
    const { offset = 0, limit = state.playlistPagination.limit || 10, append = false } = options;

    if (!url) return showNotification('URL requerida', 'error');

    // Evitar re-fetch innecesario del mismo URL cuando ya tenemos datos
    if (!append && state.lastInfoUrl === url) {
        return;
    }

    state.playlistPagination.url = url;
    state.playlistPagination.offset = offset;
    state.playlistPagination.limit = limit;

    const params = new URLSearchParams({ offset, limit });

    try {
        if (!append) showNotification('Cargando información...', 'info');

        const res = await fetch(`${API_BASE_URL}/info?${params.toString()}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });
        if (!res.ok) throw new Error('Error obteniendo info');
        const info = await res.json();
        displayVideoInfo(info, { append });
        state.lastInfoUrl = url;
    } catch (e) {
        showNotification(e.message, 'error');
    }
}

async function downloadFile(filename) {
    const a = document.createElement('a');
    a.href = `${API_BASE_URL.replace('/api', '')}/api/file/${encodeURIComponent(filename)}`;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
}

async function cleanupFile(filename) {
    try {
        const response = await fetch(`${API_BASE_URL}/cleanup/${encodeURIComponent(filename)}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            await response.json();
        } else {
            // Don't show errors to user - file cleanup is non-critical
            if (response.status !== 409) {
                const error = await response.json();
                console.warn('⚠ Cleanup failed (non-critical):', error.error || 'Unknown error', filename);
            }
        }
    } catch (e) {
        // Silent fail - cleanup errors shouldn't disrupt user experience
        console.error('✗ Cleanup error (non-critical):', e.message, filename);
    }
}

// Improved Helpers (Merged from legacy)

function formatDuration(seconds) {
    // FIX #13: Validate input to prevent NaN display
    if (!seconds || Number.isNaN(seconds) || seconds < 0) {
        return 'N/A';
    }

    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);

    if (hours > 0) {
        return `${hours}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    }
    return `${minutes}:${String(secs).padStart(2, '0')}`;
}

function formatViews(views) {
    if (views >= 1000000) {
        return (views / 1000000).toFixed(1) + 'M';
    } else if (views >= 1000) {
        return (views / 1000).toFixed(1) + 'K';
    }
    return views;
}

// Modern Glassmorphic Confirmation Dialog
function showConfirmDialog(message, options = {}) {
    return new Promise((resolve) => {
        const {
            confirmText = 'Aceptar',
            cancelText = 'Cancelar',
            type = 'warning'
        } = options;

        // Create overlay with stronger blur
        const overlay = document.createElement('div');
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.75);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            z-index: 9999;
            display: flex;
            align-items: center;
            justify-content: center;
            animation: fadeIn 0.3s ease;
        `;

        // Create glassmorphic dialog
        const dialog = document.createElement('div');
        dialog.style.cssText = `
            background: linear-gradient(135deg, rgba(80, 80, 120, 0.4), rgba(60, 60, 90, 0.3));
            backdrop-filter: blur(40px);
            -webkit-backdrop-filter: blur(40px);
            border: 1px solid rgba(255, 255, 255, 0.18);
            border-radius: 28px;
            padding: 45px 40px;
            max-width: 480px;
            width: 90%;
            box-shadow: 
                0 8px 32px rgba(0, 0, 0, 0.4),
                0 0 0 1px rgba(255, 255, 255, 0.1) inset,
                0 40px 80px rgba(0, 0, 0, 0.3);
            animation: slideInDialog 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
            text-align: center;
        `;

        // Warning icon with glow effect
        const iconContainer = document.createElement('div');
        iconContainer.style.cssText = `
            position: relative;
            display: inline-block;
            margin-bottom: 25px;
        `;

        const iconDiv = document.createElement('div');
        iconDiv.style.cssText = `
            font-size: 64px;
            filter: drop-shadow(0 0 30px rgba(255, 200, 0, 0.6)) drop-shadow(0 0 60px rgba(255, 200, 0, 0.4));
            animation: glowPulse 2s ease-in-out infinite;
        `;

        const icons = {
            warning: 'https://giffiles.alphacoders.com/738/7385.gif',
            info: 'ℹ️',
            question: '❓',
            success: '✅'
        };
        if (type === 'warning') {
            const img = document.createElement('img');
            img.src = icons[type];
            img.style.cssText = `
        width: 80px;
        height: 80px;
        object-fit: contain;
    `;
            iconDiv.appendChild(img);
        } else {
            iconDiv.textContent = icons[type];
        }
        iconContainer.appendChild(iconDiv);

        // Message with better typography
        const messageDiv = document.createElement('div');
        messageDiv.style.cssText = `
            color: rgba(255, 255, 255, 0.95);
            font-size: 17px;
            line-height: 1.6;
            margin-bottom: 35px;
            font-weight: 400;
            letter-spacing: 0.2px;
        `;
        messageDiv.textContent = message;

        // Buttons container
        const buttonsDiv = document.createElement('div');
        buttonsDiv.style.cssText = `
            display: flex;
            gap: 12px;
            justify-content: center;
        `;

        // Cancel button - glassmorphic
        const cancelBtn = document.createElement('button');
        cancelBtn.textContent = cancelText;
        cancelBtn.style.cssText = `
            padding: 14px 32px;
            border: 1.5px solid rgba(255, 255, 255, 0.25);
            border-radius: 14px;
            background: rgba(255, 255, 255, 0.08);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            color: rgba(255, 255, 255, 0.9);
            font-size: 15px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.3s ease;
            min-width: 140px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        `;
        cancelBtn.onmouseover = () => {
            cancelBtn.style.background = 'rgba(255, 255, 255, 0.15)';
            cancelBtn.style.transform = 'translateY(-2px)';
            cancelBtn.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.15)';
        };
        cancelBtn.onmouseout = () => {
            cancelBtn.style.background = 'rgba(255, 255, 255, 0.08)';
            cancelBtn.style.transform = 'translateY(0)';
            cancelBtn.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.1)';
        };
        cancelBtn.onclick = () => {
            closeDialog(false);
        };

        // Confirm button - vibrant with strong glow
        const confirmBtn = document.createElement('button');
        confirmBtn.style.cssText = `
            padding: 14px 32px;
            border: none;
            border-radius: 14px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #fff;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 
                0 0 30px rgba(102, 126, 234, 0.5),
                0 4px 15px rgba(102, 126, 234, 0.3),
                0 0 0 1px rgba(255, 255, 255, 0.1) inset;
            min-width: 140px;
            position: relative;
            overflow: hidden;
        `;

        // Glow effect on confirm button
        const glowLayer = document.createElement('div');
        glowLayer.style.cssText = `
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.2), transparent);
            opacity: 0;
            transition: opacity 0.3s ease;
            pointer-events: none;
        `;
        confirmBtn.appendChild(glowLayer);

        const textSpan = document.createElement('span');
        textSpan.textContent = confirmText;
        textSpan.style.position = 'relative';
        textSpan.style.zIndex = '1';
        confirmBtn.appendChild(textSpan);

        confirmBtn.onmouseover = () => {
            confirmBtn.style.transform = 'translateY(-2px)';
            confirmBtn.style.boxShadow = `
                0 0 40px rgba(102, 126, 234, 0.7),
                0 6px 25px rgba(102, 126, 234, 0.5),
                0 0 0 1px rgba(255, 255, 255, 0.2) inset
            `;
            glowLayer.style.opacity = '1';
        };
        confirmBtn.onmouseout = () => {
            confirmBtn.style.transform = 'translateY(0)';
            confirmBtn.style.boxShadow = `
                0 0 30px rgba(102, 126, 234, 0.5),
                0 4px 15px rgba(102, 126, 234, 0.3),
                0 0 0 1px rgba(255, 255, 255, 0.1) inset
            `;
            glowLayer.style.opacity = '0';
        };
        confirmBtn.onclick = () => {
            closeDialog(true);
        };

        function closeDialog(result) {
            overlay.style.animation = 'fadeOut 0.25s ease';
            dialog.style.animation = 'slideOutDialog 0.25s ease';
            setTimeout(() => {
                overlay.remove();
                resolve(result);
            }, 250);
        }

        // Assemble dialog
        buttonsDiv.appendChild(cancelBtn);
        buttonsDiv.appendChild(confirmBtn);
        dialog.appendChild(iconContainer);
        dialog.appendChild(messageDiv);
        dialog.appendChild(buttonsDiv);
        overlay.appendChild(dialog);

        // Inject animations if not present
        if (!document.getElementById('confirm-dialog-styles')) {
            const style = document.createElement('style');
            style.id = 'confirm-dialog-styles';
            style.textContent = `
                @keyframes fadeIn {
                    from { opacity: 0; }
                    to { opacity: 1; }
                }
                @keyframes fadeOut {
                    from { opacity: 1; }
                    to { opacity: 0; }
                }
                @keyframes slideInDialog {
                    from { 
                        transform: scale(0.9) translateY(-30px); 
                        opacity: 0; 
                    }
                    to { 
                        transform: scale(1) translateY(0); 
                        opacity: 1; 
                    }
                }
                @keyframes slideOutDialog {
                    from { 
                        transform: scale(1) translateY(0); 
                        opacity: 1; 
                    }
                    to { 
                        transform: scale(0.9) translateY(-30px); 
                        opacity: 0; 
                    }
                }
                @keyframes glowPulse {
                    0%, 100% { 
                        filter: drop-shadow(0 0 30px rgba(255, 200, 0, 0.6)) 
                                drop-shadow(0 0 60px rgba(255, 200, 0, 0.4)); 
                    }
                    50% { 
                        filter: drop-shadow(0 0 40px rgba(255, 200, 0, 0.8)) 
                                drop-shadow(0 0 80px rgba(255, 200, 0, 0.5)); 
                    }
                }
            `;
            document.head.appendChild(style);
        }

        document.body.appendChild(overlay);

        // ESC key to cancel
        const escHandler = (e) => {
            if (e.key === 'Escape') {
                closeDialog(false);
                document.removeEventListener('keydown', escHandler);
            }
        };
        document.addEventListener('keydown', escHandler);
    });
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;

    // Inject styles directly for keyframes if not present
    if (!document.getElementById('notification-styles')) {
        const style = document.createElement('style');
        style.id = 'notification-styles';
        style.textContent = `
            @keyframes slideIn {
                from { transform: translateX(400px); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            @keyframes slideOut {
                from { transform: translateX(0); opacity: 1; }
                to { transform: translateX(400px); opacity: 0; }
            }
        `;
        document.head.appendChild(style);
    }

    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: rgba(255, 255, 255, 0.2);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.3);
        border-radius: 15px;
        padding: 15px 25px;
        color: #fff;
        font-size: 14px;
        z-index: 1000;
        animation: slideIn 0.3s ease;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
        max-width: 300px;
    `;

    const icons = {
        success: '✓',
        error: '✕',
        warning: '⚠',
        info: 'ℹ'
    };

    // Fixed: Use textContent to prevent XSS
    notification.textContent = `${icons[type] || ''} ${message}`;
    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Start - Wait for DOM to be ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    // DOM is already loaded
    init();
}

// Expose globals for external modules (mass-download.js)
globalThis.state = state;
globalThis.API_BASE_URL = API_BASE_URL;
globalThis.showNotification = showNotification;
globalThis.cleanupFile = cleanupFile;
globalThis.activeSocketRooms = activeSocketRooms;
globalThis.socket = socket;