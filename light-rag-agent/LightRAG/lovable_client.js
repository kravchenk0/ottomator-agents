/**
 * LightRAG JavaScript Client (упрощённый)
 * Оставлен только функционал для отправки сообщений в /chat.
 *
 * Конфигурация базового URL:
 *  1) window.LIGHTRAG_BASE_URL (если задан в браузере до подключения скрипта)
 *  2) process.env.LIGHTRAG_BASE_URL (если используется bundler / Node среда)
 *  3) Жёсткий дефолт: https://bussinesindunes.ai
 */
const LIGHTRAG_DEFAULT_BASE_URL = (
    (typeof window !== 'undefined' && window.LIGHTRAG_BASE_URL) ||
    (typeof process !== 'undefined' && process.env && process.env.LIGHTRAG_BASE_URL) ||
    'https://bussinesindunes.ai'
);
class LightRAGClient {
    constructor(baseUrl = LIGHTRAG_DEFAULT_BASE_URL, options = {}) {
        this.baseUrl = baseUrl;
        this.conversationId = null;
        this.userId = options.userId || null;
        this.authToken = options.authToken || null; // JWT Bearer
        this.apiKey = options.apiKey || null;       // Optional X-API-Key
    }

    setConversationId(id) { this.conversationId = id; return this; }
    setUserId(id) { this.userId = id; return this; }
    setAuthToken(token) { this.authToken = token; return this; }
    setApiKey(key) { this.apiKey = key; return this; }
    resetConversation() { this.conversationId = null; return this; }

    async chat(message, { newConversation = false, conversation_id = null, user_id = null } = {}) {
        if (newConversation || (!this.conversationId && conversation_id)) {
            this.conversationId = conversation_id || `conv_${Date.now()}_${Math.random().toString(36).slice(2,10)}`;
        }
        const headers = { 'Content-Type': 'application/json' };
        if (this.authToken) headers['Authorization'] = `Bearer ${this.authToken}`;
        if (this.apiKey) headers['X-API-Key'] = this.apiKey;

        const body = {
            message,
            conversation_id: this.conversationId,
            user_id: user_id || this.userId,
        };
        const resp = await fetch(`${this.baseUrl}/chat`, { method: 'POST', headers, body: JSON.stringify(body) });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        if (!this.conversationId && data.conversation_id) this.conversationId = data.conversation_id;
        if (data && data.metadata) {
            data.rate_limit_remaining = data.metadata.rate_limit_remaining;
            data.rate_limit_reset_seconds = data.metadata.rate_limit_reset_seconds;
        }
        return data;
    }
}

/**
 * Минимальная интеграция с Lovable.
 * Автоматически перехватывает:
 *  - submit форм с классом .lovable-form
 *  - Enter в input/textarea с классом .lovable-chat-input
 * Показывает простой чат-контейнер.
 */
class LovableLightRAGIntegration {
    constructor(apiUrl, options = {}) {
        this.client = new LightRAGClient(apiUrl, options.client || {});
        this.options = {
            autoGenerateConversationId: true,
            showTypingIndicator: true,
            ...options
        };
        this._bind();
    }

    _bind() {
        document.addEventListener('submit', (e) => {
            if (e.target.classList && e.target.classList.contains('lovable-form')) {
                e.preventDefault();
                this._handleForm(e.target);
            }
        });
        document.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && e.target.classList && e.target.classList.contains('lovable-chat-input')) {
                e.preventDefault();
                this._handleInput(e.target);
            }
        });
    }

    async _handleForm(form) {
        const btn = form.querySelector('button[type="submit"]');
        const original = btn ? btn.textContent : null;
        if (btn) { btn.disabled = true; btn.textContent = '...'; }
        try {
            const fd = new FormData(form);
            const message = fd.get('message') || fd.get('question') || fd.get('input');
            if (!message) throw new Error('Нет текста');
            if (this.options.autoGenerateConversationId && !this.client.conversationId) {
                this.client.setConversationId(`conv_${Date.now()}_${Math.random().toString(36).slice(2,10)}`);
            }
            const r = await this.client.chat(message);
            this._renderFormAnswer(form, r);
        } catch (err) {
            this._renderFormError(form, err.message || String(err));
        } finally {
            if (btn) { btn.disabled = false; btn.textContent = original; }
        }
    }

    async _handleInput(inputEl) {
        const message = inputEl.value.trim();
        if (!message) return;
        inputEl.value = '';
        this._appendUser(message);
        try {
            if (this.options.showTypingIndicator) this._showTyping();
            if (this.options.autoGenerateConversationId && !this.client.conversationId) {
                this.client.setConversationId(`conv_${Date.now()}_${Math.random().toString(36).slice(2,10)}`);
            }
            const r = await this.client.chat(message);
            if (this.options.showTypingIndicator) this._hideTyping();
            this._appendAI(r);
        } catch (err) {
            if (this.options.showTypingIndicator) this._hideTyping();
            this._appendError(err.message || String(err));
        }
    }

    _renderFormAnswer(form, resp) {
        let c = form.querySelector('.lightrag-response');
        if (!c) { c = document.createElement('div'); c.className = 'lightrag-response'; form.appendChild(c); }
        c.innerHTML = `<div><strong>Ответ:</strong><p>${resp.response}</p><p><small>ID: ${resp.conversation_id || this.client.conversationId || ''}</small></p>${resp.metadata ? this._meta(resp.metadata) : ''}</div>`;
    }
    _renderFormError(form, msg) {
        let c = form.querySelector('.lightrag-error');
        if (!c) { c = document.createElement('div'); c.className = 'lightrag-error'; form.appendChild(c); }
        c.innerHTML = `<div style="color:red"><strong>Ошибка:</strong> ${msg}</div>`;
    }

    _appendUser(text) {
        const chat = this._chat();
        const d = document.createElement('div');
        d.className = 'user-msg';
        d.innerHTML = `<p><strong>Вы:</strong> ${text}</p>`;
        chat.appendChild(d); chat.scrollTop = chat.scrollHeight;
    }
    _appendAI(resp) {
        const chat = this._chat();
        const d = document.createElement('div');
        d.className = 'ai-msg';
        d.innerHTML = `<p><strong>AI:</strong> ${resp.response}</p>${resp.metadata ? this._meta(resp.metadata) : ''}`;
        chat.appendChild(d); chat.scrollTop = chat.scrollHeight;
    }
    _appendError(msg) {
        const chat = this._chat();
        const d = document.createElement('div');
        d.className = 'err-msg';
        d.innerHTML = `<p style="color:red"><strong>Ошибка:</strong> ${msg}</p>`;
        chat.appendChild(d); chat.scrollTop = chat.scrollHeight;
    }
    _showTyping() {
        const chat = this._chat();
        if (chat.querySelector('.typing')) return;
        const d = document.createElement('div'); d.className = 'typing'; d.innerHTML = '<p><em>...</em></p>'; chat.appendChild(d); chat.scrollTop = chat.scrollHeight;
    }
    _hideTyping() {
        const chat = this._chat(); const t = chat.querySelector('.typing'); if (t) t.remove();
    }
    _meta(meta) {
        const parts = [];
        if (meta.processing_time) parts.push(`t:${meta.processing_time.toFixed ? meta.processing_time.toFixed(2) : meta.processing_time}s`);
        if (meta.history_messages !== undefined) parts.push(`h:${meta.history_messages}`);
        if (meta.rate_limit_remaining !== undefined) parts.push(`left:${meta.rate_limit_remaining}`);
        if (meta.rate_limit_reset_seconds !== undefined) parts.push(`reset:${meta.rate_limit_reset_seconds}s`);
        return parts.length ? `<p><small>${parts.join(' | ')}</small></p>` : '';
    }
    _chat() {
        let c = document.querySelector('.lightrag-chat');
        if (!c) {
            c = document.createElement('div');
            c.className = 'lightrag-chat';
            c.style.cssText = 'max-height:400px;overflow-y:auto;border:1px solid #ccc;padding:8px;margin:10px 0;font:14px sans-serif;';
            const anchor = document.querySelector('.lovable-form, .lovable-chat-input');
            if (anchor) anchor.parentNode.insertBefore(c, anchor.nextSibling); else document.body.appendChild(c);
        }
        return c;
    }
}

// Exports
if (typeof module !== 'undefined' && module.exports) module.exports = { LightRAGClient, LovableLightRAGIntegration };
if (typeof window !== 'undefined') { window.LightRAGClient = LightRAGClient; window.LovableLightRAGIntegration = LovableLightRAGIntegration; }