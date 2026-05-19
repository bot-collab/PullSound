// ========== AUDIO PREVIEW MODULE ==========

// Note: API_BASE_URL is defined in script.js which loads first

class AudioPreview {
    audio = null;
    isPlaying = false;
    currentObjectUrl = null;
    urlHistory = [];  // FIX: Track all URLs for cleanup

    async generate(url, duration = 15) {
        let indicator = null;
        try {
            indicator = StateIndicator.show('Generando preview...', 'loading', 0);
            
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

            if (indicator) StateIndicator.hide(indicator);
            return audioUrl;
            
        } catch (error) {
            if (indicator) StateIndicator.hide(indicator);
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

// Initialize and export
const audioPreview = new AudioPreview();
globalThis.audioPreview = audioPreview;

// ========== GLOBAL CLEANUP ==========
// FIX: Cleanup all Object URLs on page unload
globalThis.addEventListener('beforeunload', () => {
    if (globalThis.audioPreview) {
        globalThis.audioPreview.destroy();
    }
});
