// ========== VISUAL ENHANCEMENTS MODULE ==========

// Ripple Effect for Buttons
function createRippleEffect(e) {
    const button = e.currentTarget;
    const circle = document.createElement('span');
    const diameter = Math.max(button.clientWidth, button.clientHeight);
    const radius = diameter / 2;

    const rect = button.getBoundingClientRect();
    circle.style.width = circle.style.height = `${diameter}px`;
    circle.style.left = `${e.clientX - rect.left - radius}px`;
    circle.style.top = `${e.clientY - rect.top - radius}px`;
    circle.classList.add('ripple');

    const existingRipple = button.getElementsByClassName('ripple')[0];
    if (existingRipple) {
        existingRipple.remove();
    }

    button.appendChild(circle);
}

// Auto-detect System Theme
function detectSystemTheme() {
    if (globalThis.matchMedia?.('(prefers-color-scheme: dark)')?.matches) {
        return 'dark';
    } else if (globalThis.matchMedia?.('(prefers-color-scheme: light)')?.matches) {
        return 'light';
    }
    return 'dark'; // Default
}

// Apply Theme with Smooth Transition
function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    document.body.dataset.theme = theme;
    localStorage.setItem('theme', theme);
}

// Watch for System Theme Changes
function watchSystemTheme() {
    const darkModeQuery = globalThis.matchMedia?.('(prefers-color-scheme: dark)');
    darkModeQuery?.addEventListener('change', (e) => {
        const userTheme = localStorage.getItem('theme');
        if (!userTheme) { // Only auto-switch if user hasn't set preference
            applyTheme(e.matches ? 'dark' : 'light');
        }
    });
}

// Enhanced State Indicators with Animations
class StateIndicator {
    static show(message, type = 'info', duration = 3000) {
        const indicator = document.createElement('div');
        indicator.className = `state-indicator state-${type}`;
        
        const icons = {
            success: 'fa-check-circle',
            error: 'fa-exclamation-circle',
            warning: 'fa-exclamation-triangle',
            info: 'fa-info-circle',
            loading: 'fa-spinner fa-spin'
        };
        
        const iconEl = document.createElement('i');
        iconEl.className = `fas ${icons[type]}`;
        const spanEl = document.createElement('span');
        spanEl.textContent = message;
        indicator.appendChild(iconEl);
        indicator.appendChild(document.createTextNode(' '));
        indicator.appendChild(spanEl);
        
        document.body.appendChild(indicator);
        
        // Trigger animation
        requestAnimationFrame(() => {
            indicator.classList.add('show');
        });
        
        if (duration > 0) {
            setTimeout(() => {
                indicator.classList.remove('show');
                setTimeout(() => indicator.remove(), 300);
            }, duration);
        }
        
        return indicator;
    }

    static hide(indicator) {
        if (!indicator) {
            document.querySelectorAll('.state-indicator').forEach(el => {
                el.classList.remove('show');
                setTimeout(() => el.remove(), 300);
            });
            return;
        }
        indicator.classList.remove('show');
        setTimeout(() => indicator.remove(), 300);
    }
}

// Smooth Page Transitions
function showElementSmooth(element) {
    element.style.display = 'block';
    requestAnimationFrame(() => {
        element.classList.add('fade-in');
    });
}

function hideElementSmooth(element) {
    element.classList.add('fade-out');
    setTimeout(() => {
        element.style.display = 'none';
        element.classList.remove('fade-out', 'fade-in');
    }, 300);
}

// Initialize Visual Enhancements
function initVisualEnhancements() {
    // Add ripple effect to all buttons
    const buttons = document.querySelectorAll('button, .option-btn, .btn-download');
    buttons.forEach(button => {
        button.addEventListener('click', createRippleEffect);
    });
    
    // Auto-detect and apply system theme on first load
    const savedTheme = localStorage.getItem('theme');
    if (!savedTheme) {
        const systemTheme = detectSystemTheme();
        applyTheme(systemTheme);
    }
    
    // Watch for system theme changes
    watchSystemTheme();
    
}

// Export for global use
globalThis.createRippleEffect = createRippleEffect;
globalThis.StateIndicator = StateIndicator;
globalThis.showElementSmooth = showElementSmooth;
globalThis.hideElementSmooth = hideElementSmooth;
globalThis.applyTheme = applyTheme;

// Auto-initialize on DOM load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initVisualEnhancements);
} else {
    initVisualEnhancements();
}
