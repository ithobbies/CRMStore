(function () {
    const doc = document;
    const root = doc.documentElement;
    const THEME_KEY = 'crm_theme';

    function setTheme(theme) {
        root.setAttribute('data-theme', theme);
        localStorage.setItem(THEME_KEY, theme);
        const toggle = doc.getElementById('themeToggle');
        if (toggle) {
            const isDark = theme === 'dark';
            toggle.innerHTML = isDark
                ? '<i class="bi bi-sun"></i><span>Світла тема</span>'
                : '<i class="bi bi-moon-stars"></i><span>Темна тема</span>';
        }
    }

    function initTheme() {
        const savedTheme = localStorage.getItem(THEME_KEY);
        if (savedTheme) {
            setTheme(savedTheme);
        } else {
            setTheme(window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
        }

        doc.getElementById('themeToggle')?.addEventListener('click', () => {
            setTheme(root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
        });
    }

    function initSidebar() {
        const sidebar = doc.getElementById('sidebar');
        const toggle = doc.getElementById('sidebarToggle');
        const backdrop = doc.getElementById('sidebarBackdrop');
        if (!sidebar || !backdrop) return;

        const close = () => {
            sidebar.classList.remove('is-open');
            backdrop.classList.remove('is-open');
        };

        const open = () => {
            sidebar.classList.add('is-open');
            backdrop.classList.add('is-open');
        };

        toggle?.addEventListener('click', open);
        backdrop.addEventListener('click', close);
        doc.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') close();
        });
    }

    function hideToast(toast) {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(10px)';
        setTimeout(() => toast.remove(), 200);
    }

    function initToasts() {
        doc.querySelectorAll('.toast-item').forEach((toast) => {
            const closeBtn = toast.querySelector('.toast-close');
            closeBtn?.addEventListener('click', () => hideToast(toast));
            setTimeout(() => hideToast(toast), 4500);
        });
    }

    function setButtonLoadingState(button) {
        if (!button || button.dataset.loadingBound === '1') return;
        button.dataset.loadingBound = '1';
        const label = button.dataset.loadingText || 'Збереження...';
        button.classList.add('btn-loading');
        button.disabled = true;
        button.innerHTML = `<span class="btn-spinner"></span><span class="btn-label">${label}</span>`;
    }

    function initLoadingButtons() {
        doc.querySelectorAll('form').forEach((form) => {
            form.addEventListener('submit', () => {
                const submit = form.querySelector('button[type="submit"],input[type="submit"]');
                if (submit) setButtonLoadingState(submit);
            });
        });
    }

    function initCopyButtons() {
        async function copyText(text) {
            if (!text) return false;
            if (navigator.clipboard?.writeText) {
                await navigator.clipboard.writeText(text);
                return true;
            }
            const input = doc.createElement('textarea');
            input.value = text;
            doc.body.appendChild(input);
            input.select();
            const ok = doc.execCommand('copy');
            doc.body.removeChild(input);
            return ok;
        }

        doc.addEventListener('click', async (event) => {
            const button = event.target.closest('[data-copy]');
            if (!button) return;
            event.preventDefault();
            const ok = await copyText(button.dataset.copy);
            if (!ok) return;
            button.classList.add('is-copied');
            const icon = button.querySelector('i');
            if (icon) {
                icon.classList.remove('bi-clipboard');
                icon.classList.add('bi-check2');
            }
            setTimeout(() => {
                button.classList.remove('is-copied');
                if (icon) {
                    icon.classList.remove('bi-check2');
                    icon.classList.add('bi-clipboard');
                }
            }, 1400);
        });
    }

    function initRowClick() {
        doc.querySelectorAll('[data-row-link]').forEach((row) => {
            row.addEventListener('click', (event) => {
                if (event.target.closest('a,button,input,select,textarea,label')) return;
                const href = row.getAttribute('data-row-link');
                if (href) window.location.href = href;
            });
        });
    }

    function initConfirmModal() {
        const modalElement = doc.getElementById('confirmActionModal');
        const acceptButton = doc.getElementById('confirmActionAccept');
        const textNode = doc.getElementById('confirmActionBody');
        if (!modalElement || !acceptButton || !textNode || !window.bootstrap) return;

        const modal = new bootstrap.Modal(modalElement);
        let pendingAction = null;

        doc.addEventListener('click', (event) => {
            const trigger = event.target.closest('[data-confirm]');
            if (!trigger) return;
            event.preventDefault();
            pendingAction = trigger;
            textNode.textContent = trigger.dataset.confirm || 'Ви впевнені, що хочете продовжити?';
            modal.show();
        });

        acceptButton.addEventListener('click', () => {
            if (!pendingAction) return;
            if (pendingAction.tagName === 'A' && pendingAction.href) {
                window.location.href = pendingAction.href;
            } else if (pendingAction.type === 'submit') {
                pendingAction.closest('form')?.requestSubmit(pendingAction);
            }
            modal.hide();
            pendingAction = null;
        });
    }

    function initShortcuts() {
        const searchInput = doc.getElementById('globalSearchInput');
        doc.addEventListener('keydown', (event) => {
            const typing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(doc.activeElement?.tagName);
            if (typing && event.key.toLowerCase() !== 'escape') return;

            if (event.key.toLowerCase() === 'n') {
                event.preventDefault();
                const newOrderLink = doc.querySelector('a[href*="/orders/create/"]');
                if (newOrderLink) window.location.href = newOrderLink.href;
            }

            if (event.key.toLowerCase() === 'f') {
                event.preventDefault();
                searchInput?.focus();
                searchInput?.select();
            }
        });
    }

    function renderSearchResults(container, payload) {
        const groups = [
            { key: 'orders', title: 'Замовлення' },
            { key: 'customers', title: 'Клієнти' },
            { key: 'products', title: 'Товари' },
        ];

        let html = '';
        groups.forEach((group) => {
            const items = payload[group.key] || [];
            if (!items.length) return;
            html += `<section class="global-search-group"><div class="global-search-group-title">${group.title}</div>`;
            items.forEach((item) => {
                html += `<a class="global-search-item" href="${item.url}"><span>${item.title}</span><span class="global-search-meta">${item.meta || ''}</span></a>`;
            });
            html += '</section>';
        });

        container.innerHTML = html || '<div class="global-search-empty">Нічого не знайдено</div>';
        container.hidden = false;
    }

    function initGlobalSearch() {
        const form = doc.getElementById('globalSearchForm');
        const input = doc.getElementById('globalSearchInput');
        const panel = doc.getElementById('globalSearchResults');
        if (!form || !input || !panel) return;

        const endpoint = form.dataset.searchEndpoint;
        let timer = null;

        input.addEventListener('input', () => {
            const query = input.value.trim();
            clearTimeout(timer);
            if (query.length < 2) {
                panel.hidden = true;
                panel.innerHTML = '';
                return;
            }

            timer = setTimeout(async () => {
                try {
                    const response = await fetch(`${endpoint}?q=${encodeURIComponent(query)}`, {
                        headers: { 'X-Requested-With': 'XMLHttpRequest' },
                    });
                    if (!response.ok) throw new Error('search');
                    const payload = await response.json();
                    renderSearchResults(panel, payload);
                } catch (error) {
                    panel.hidden = false;
                    panel.innerHTML = '<div class="global-search-empty">Помилка пошуку</div>';
                }
            }, 180);
        });

        doc.addEventListener('click', (event) => {
            if (!form.contains(event.target)) panel.hidden = true;
        });

        doc.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') {
                panel.hidden = true;
                input.blur();
            }
        });
    }

    function initCustomDateRange() {
        const dateSelect = doc.getElementById('dateRangePreset');
        const customRange = doc.getElementById('customDateRange');
        if (!dateSelect || !customRange) return;

        const sync = () => {
            customRange.style.display = dateSelect.value === 'custom' ? 'flex' : 'none';
        };

        dateSelect.addEventListener('change', sync);
        sync();
    }

    function init() {
        initTheme();
        initSidebar();
        initToasts();
        initLoadingButtons();
        initCopyButtons();
        initRowClick();
        initConfirmModal();
        initShortcuts();
        initGlobalSearch();
        initCustomDateRange();
    }

    if (doc.readyState === 'loading') {
        doc.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
