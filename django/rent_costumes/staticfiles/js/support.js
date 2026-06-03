/**
 * Чат поддержки: арендатор (/support/) и сотрудники (/support-panel/).
 */
class SupportChat {
    constructor() {
        this.mode = window.location.pathname.includes('support-panel') ? 'staff' : 'renter';
        this.socket = null;
        this.userUUID = null;
        this.currentTicketId = null;
        this.currentTicketMeta = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 3000;
        this.lastTicketCount = 0;
        this.ticketsData = [];
        this.hasOpenTicketFlag = false;
        this.pendingAttachments = [];
        this.maxAttachments = 5;
        this.messageInputBlock = document.getElementById('messageInputBlock');

        this.ticketsBlock = document.getElementById('ticketsBlock');
        this.ticketsList = document.getElementById('ticketsList');
        this.ticketsEmpty = document.getElementById('ticketsEmpty');
        this.messagesBlock = document.getElementById('messagesBlock');
        this.messagesEmpty = document.getElementById('messagesEmpty');
        this.messageInput = document.getElementById('messageInp');
        this.sendButton = document.getElementById('sendBtn');
        this.closeButton = document.getElementById('closeTicketBtn');
        this.attachButton = document.getElementById('attachMediaBtn');
        this.attachInput = document.getElementById('messageMediaInput');
        this.attachPreview = document.getElementById('messageAttachPreview');
        this.createTicketButton = document.getElementById('createTicketBtn');

        this.ticketModal = this.mode === 'renter' ? new SupportTicketModal(this) : null;
        this.initLightbox();
    }

    static async create() {
        const chat = new SupportChat();
        await chat.initialize();
        return chat;
    }

    async initialize() {
        const identity = new SupportIdentity(this.mode);
        this.userUUID = await identity.ensure();
        if (!this.userUUID) {
            return;
        }

        this.initEventListeners();
        this.clearPlaceholderContent();
        this.connectWebSocket();
        await this.loadTickets();

        if (this.mode === 'renter' && this.lastTicketCount === 0 && !this.hasOpenTicket() && this.ticketModal) {
            await this.ticketModal.promptIfEmpty();
        }

        this.setupMessageDragAndDrop();
    }

    hasOpenTicket() {
        if (this.hasOpenTicketFlag) {
            return true;
        }
        return this.ticketsData.some((ticket) => !ticket.is_closed);
    }

    notifyOpenTicketExists() {
        const message = 'У вас уже есть открытая заявка. Закройте её, чтобы создать новую.';
        if (typeof showNotification === 'function') {
            showNotification(message, 'warning');
        } else {
            this.showError(message);
        }
    }

    tryOpenCreateTicket() {
        if (this.mode !== 'renter') {
            return;
        }
        if (this.hasOpenTicket()) {
            this.notifyOpenTicketExists();
            return;
        }
        this.ticketModal?.open(false);
    }

    setupMessageDragAndDrop() {
        SupportAttachDnd.setup({
            zones: [this.messageInputBlock, this.attachPreview, this.messagesBlock].filter(Boolean),
            onFiles: (files) => this.onAttachSelected(files),
            getCount: () => this.pendingAttachments.length,
            maxFiles: this.maxAttachments,
        });
    }

    apiQueryParams() {
        if (this.mode === 'staff') {
            return `grant_person_uuid=${encodeURIComponent(this.userUUID)}`;
        }
        return `renter_uuid=${encodeURIComponent(this.userUUID)}`;
    }

    initEventListeners() {
        this.sendButton?.addEventListener('click', () => this.sendMessage());
        this.messageInput?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        this.closeButton?.addEventListener('click', () => this.closeCurrentTicket());
        this.createTicketButton?.addEventListener('click', () => this.tryOpenCreateTicket());
        this.attachButton?.addEventListener('click', () => this.attachInput?.click());
        this.attachInput?.addEventListener('change', () => this.onAttachSelected(this.attachInput.files));
    }

    initLightbox() {
        this.lightbox = document.getElementById('supportLightbox');
        this.lightboxImage = document.getElementById('supportLightboxImage');
        this.lightboxCounter = document.getElementById('supportLightboxCounter');
        this._lightboxUrls = [];
        this._lightboxIndex = 0;

        document.getElementById('supportLightboxClose')?.addEventListener('click', () => this.closeLightbox());
        document.getElementById('supportLightboxPrev')?.addEventListener('click', () => this.shiftLightbox(-1));
        document.getElementById('supportLightboxNext')?.addEventListener('click', () => this.shiftLightbox(1));
        this.lightbox?.addEventListener('click', (e) => {
            if (e.target === this.lightbox) {
                this.closeLightbox();
            }
        });
        document.addEventListener('keydown', (e) => {
            if (!this.lightbox || this.lightbox.style.display === 'none') {
                return;
            }
            if (e.key === 'Escape') {
                this.closeLightbox();
            }
            if (e.key === 'ArrowLeft') {
                this.shiftLightbox(-1);
            }
            if (e.key === 'ArrowRight') {
                this.shiftLightbox(1);
            }
        });
    }

    openLightbox(urls, startIndex = 0) {
        if (!this.lightbox || !urls.length) {
            return;
        }
        this._lightboxUrls = urls;
        this._lightboxIndex = startIndex;
        this.lightbox.style.display = 'flex';
        this.lightbox.setAttribute('aria-hidden', 'false');
        this.updateLightboxImage();
    }

    closeLightbox() {
        if (!this.lightbox) {
            return;
        }
        this.lightbox.style.display = 'none';
        this.lightbox.setAttribute('aria-hidden', 'true');
    }

    shiftLightbox(delta) {
        if (!this._lightboxUrls.length) {
            return;
        }
        this._lightboxIndex = (this._lightboxIndex + delta + this._lightboxUrls.length) % this._lightboxUrls.length;
        this.updateLightboxImage();
    }

    updateLightboxImage() {
        if (!this.lightboxImage) {
            return;
        }
        this.lightboxImage.src = this._lightboxUrls[this._lightboxIndex];
        if (this.lightboxCounter) {
            this.lightboxCounter.textContent = `${this._lightboxIndex + 1} / ${this._lightboxUrls.length}`;
        }
    }

    clearPlaceholderContent() {
        this.ticketsList?.querySelectorAll('.ticket').forEach((el) => el.remove());
        this.messagesBlock?.querySelectorAll('.message-from, .message-to').forEach((el) => el.remove());
        this.messagesBlock?.querySelectorAll('[data-message-id]').forEach((el) => el.remove());
    }

    connectWebSocket() {
        try {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const host = window.location.hostname;
            const port = parseInt(window.WS_PORT, 10) || 8001;
            this.socket = new WebSocket(`${protocol}//${host}:${port}/ws`);

            this.socket.onopen = () => {
                this.reconnectAttempts = 0;
                this.authenticate();
            };
            this.socket.onmessage = (event) => this.handleSocketMessage(event);
            this.socket.onerror = (error) => console.error('WebSocket error:', error);
            this.socket.onclose = () => this.attemptReconnect();
        } catch (error) {
            console.error('Error connecting to WebSocket:', error);
            this.attemptReconnect();
        }
    }

    attemptReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            this.showError('Соединение с чатом потеряно');
            return;
        }
        this.reconnectAttempts += 1;
        setTimeout(() => this.connectWebSocket(), this.reconnectDelay);
    }

    authenticate() {
        if (!this.socket || this.socket.readyState !== WebSocket.OPEN || !this.userUUID) {
            return;
        }
        this.socket.send(JSON.stringify({ type: 'AUTH', id: this.userUUID }));
    }

    handleSocketMessage(event) {
        try {
            const message = JSON.parse(event.data);
            if (!message || typeof message !== 'object') {
                return;
            }
            if (message.type === 'ERROR') {
                this.showError(message.error || 'Ошибка WebSocket');
                return;
            }
            if (message.type === 'MSG') {
                if (message.ticket_id) {
                    this.loadTickets();
                }
                if (message.ticket_id === this.currentTicketId) {
                    this.displayMessage(message, true);
                }
            }
        } catch (error) {
            console.error('Error handling message:', error);
        }
    }

    setTicketsEmptyVisible(visible) {
        if (this.ticketsEmpty) {
            this.ticketsEmpty.style.display = visible ? 'block' : 'none';
        }
    }

    setMessagesEmptyVisible(visible) {
        if (this.messagesEmpty) {
            this.messagesEmpty.style.display = visible ? 'block' : 'none';
        }
    }

    async loadTickets() {
        if (!this.userUUID) {
            return;
        }

        try {
            const response = await fetch(
                `/api/support/tickets/?page=1&per_page=50&${this.apiQueryParams()}`
            );
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || 'Ошибка загрузки заявок');
            }

            const tickets = data.items && Array.isArray(data.items) ? data.items : [];
            this.lastTicketCount = tickets.length;
            this.hasOpenTicketFlag = Boolean(data.has_open_ticket);
            this.ticketsData = tickets;
            this.renderTickets(tickets);
        } catch (error) {
            console.error('Error loading tickets:', error);
            this.showError('Не удалось загрузить список заявок');
        }
    }

    renderTickets(tickets) {
        const list = this.ticketsList || this.ticketsBlock;
        if (!list) {
            return;
        }

        list.querySelectorAll('.ticket').forEach((el) => el.remove());
        this.setTicketsEmptyVisible(tickets.length === 0);

        tickets.forEach((ticket) => {
            const ticketEl = document.createElement('div');
            ticketEl.className = 'ticket';
            ticketEl.dataset.ticketId = String(ticket.ticket_id);
            ticketEl.dataset.renterUuid = ticket.renter_uuid || '';
            ticketEl.dataset.supportUuid = ticket.support_uuid || '';
            ticketEl.dataset.isClosed = ticket.is_closed ? '1' : '0';

            const senderInfo = document.createElement('span');
            senderInfo.className = 'sender-info';
            senderInfo.textContent = this.mode === 'staff'
                ? (ticket.renter || 'Арендатор')
                : (ticket.theme || `Заявка #${ticket.ticket_id}`);

            const lastMsg = document.createElement('span');
            lastMsg.className = 'last-msg';
            lastMsg.textContent = ticket.last_msg ? ticket.last_msg.msg : 'Нет сообщений';

            const status = document.createElement('span');
            status.className = 'status';
            status.style.fontSize = '0.8em';
            status.style.color = 'var(--border)';
            status.textContent = ticket.status || '';

            const datetime = document.createElement('span');
            datetime.className = 'datetime-last-msg';
            datetime.textContent = ticket.last_msg
                ? this.formatDateTime(ticket.last_msg.datetime)
                : '';
            ticketEl.appendChild(senderInfo);
            ticketEl.appendChild(lastMsg);
            ticketEl.appendChild(datetime);
            ticketEl.appendChild(status);
            ticketEl.addEventListener('click', () => this.selectTicket(ticket.ticket_id, ticket));
            list.appendChild(ticketEl);
        });

        if (!this.currentTicketId && tickets.length > 0) {
            this.selectTicket(tickets[0].ticket_id, tickets[0]);
        } else if (tickets.length === 0) {
            this.currentTicketId = null;
            this.renderMessages([]);
        }
    }

    async selectTicket(ticketId, ticketMeta = null) {
        this.currentTicketId = ticketId;
        this.currentTicketMeta = ticketMeta;
        this.updateCloseButtonState(ticketMeta);

        document.querySelectorAll('.ticket').forEach((t) => {
            t.style.backgroundColor = parseInt(t.dataset.ticketId, 10) === ticketId ? 'var(--secondary)' : '';
        });

        await this.loadMessages(ticketId);
    }

    updateCloseButtonState(meta = null) {
        if (!this.closeButton) {
            return;
        }
        const info = meta || this.currentTicketMeta || {};
        const isClosed = Boolean(info.is_closed);
        const canClose = Boolean(info.can_close);
        const hint = info.close_hint || '';

        this.closeButton.disabled = !canClose || isClosed;
        this.closeButton.title = hint || (canClose ? 'Закрыть заявку' : 'Закрытие недоступно');
        this.closeButton.style.display = isClosed ? 'none' : '';

        const chatLocked = isClosed;
        if (this.messageInputBlock) {
            this.messageInput.display = chatLocked ? 'none' : 'flex';
        }
    }

    async loadMessages(ticketId) {
        if (!ticketId) {
            this.renderMessages([]);
            return;
        }

        try {
            const response = await fetch(
                `/api/support/ticket/${ticketId}/ticket-messages/?${this.apiQueryParams()}`
            );
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || 'Ошибка загрузки сообщений');
            }

            if (data.ticket) {
                this.currentTicketMeta = {
                    ...this.currentTicketMeta,
                    renter_uuid: data.renter?.uuid,
                    support_uuid: data.ticket.support_uuid,
                    theme: data.ticket.theme,
                    status: data.ticket.status,
                    is_closed: data.ticket.is_closed,
                    can_close: data.ticket.can_close,
                    close_hint: data.ticket.close_hint,
                };
                this.updateChatHeader(data.renter, data.ticket);
                this.updateCloseButtonState(this.currentTicketMeta);
            }

            this.renderMessages(data.msgs && Array.isArray(data.msgs) ? data.msgs : []);
        } catch (error) {
            console.error('Error loading messages:', error);
            this.showError('Не удалось загрузить сообщения');
        }
    }

    updateChatHeader(renter, ticket) {
        const chatUserInfo = document.querySelector('.chat-user-info');
        if (!chatUserInfo) {
            return;
        }
        const nameEl = chatUserInfo.querySelector('.chat-user-profile-name');
        const themeEl = chatUserInfo.querySelector('.chat-user-theme');
        if (nameEl && renter) {
            const middle = renter.middle_name ? ` ${renter.middle_name}` : '';
            nameEl.textContent = this.model === 'staff' ? `${renter.last_name} ${renter.first_name}${middle}`.trim() : 'Поддержка';
        }
        if (themeEl && ticket) {
            themeEl.textContent = `Тема тикета: ${ticket.theme}` || '';
        }
    }

    renderMessages(messages) {
        if (!this.messagesBlock) {
            return;
        }

        this.messagesBlock.querySelectorAll('[data-message-id]').forEach((m) => m.remove());
        this.setMessagesEmptyVisible(!messages.length);

        messages.forEach((msg) => this.displayMessage(msg, false));
        this.messagesBlock.scrollTop = this.messagesBlock.scrollHeight;
    }

    buildMediaGallery(media, messageDiv) {
        if (!media || !media.length) {
            return;
        }

        const gallery = document.createElement('div');
        gallery.className = 'message-media-gallery';

        const urls = media.map((m) => m.url).filter(Boolean);
        media.forEach((item, index) => {
            if (!item.url) {
                return;
            }
            const thumb = document.createElement('button');
            thumb.type = 'button';
            thumb.className = 'message-media-thumb';
            const img = document.createElement('img');
            img.src = item.url;
            img.alt = 'Вложение';
            img.loading = 'lazy';
            thumb.appendChild(img);
            thumb.addEventListener('click', () => this.openLightbox(urls, index));
            gallery.appendChild(thumb);
        });

        messageDiv.appendChild(gallery);
    }

    displayMessage(msg, scroll = true) {
        if (!this.messagesBlock || !msg) {
            return;
        }

        if (msg.msg_id && this.messagesBlock.querySelector(`[data-message-id="${msg.msg_id}"]`)) {
            return;
        }

        this.setMessagesEmptyVisible(false);

        const isOwnMessage = msg.sender_id === this.userUUID;
        const messageDiv = document.createElement('div');
        messageDiv.className = isOwnMessage ? 'message-to' : 'message-from';
        if (msg.msg_id) {
            messageDiv.dataset.messageId = msg.msg_id;
        }

        const senderInfo = document.createElement('span');
        senderInfo.className = 'sender-info';
        senderInfo.textContent = isOwnMessage ? 'Вы' : (this.mode === 'staff' ? 'Арендатор' : 'Поддержка');

        messageDiv.appendChild(senderInfo);

        if (msg.msg) {
            const messageText = document.createElement('p');
            messageText.className = 'sender-msg';
            messageText.textContent = msg.msg;
            messageDiv.appendChild(messageText);
        }

        this.buildMediaGallery(msg.media, messageDiv);

        const dateTime = document.createElement('span');
        dateTime.className = 'sender-datetime';
        dateTime.textContent = this.formatDateTime(msg.datetime);
        messageDiv.appendChild(dateTime);
        this.messagesBlock.appendChild(messageDiv);

        if (scroll) {
            this.messagesBlock.scrollTop = this.messagesBlock.scrollHeight;
        }
    }

    onAttachSelected(fileList) {
        if (this.currentTicketMeta?.is_closed) {
            return;
        }

        const files = SupportAttachDnd.filterImages(fileList);

        for (const file of files) {
            if (this.pendingAttachments.length >= this.maxAttachments) {
                this.showError('Не более 5 изображений');
                break;
            }
            this.pendingAttachments.push({
                file,
                url: URL.createObjectURL(file),
            });
        }
        if (this.attachInput) {
            this.attachInput.value = '';
        }
        this.renderAttachPreview();
    }

    renderAttachPreview() {
        if (!this.attachPreview) {
            return;
        }
        this.attachPreview.innerHTML = '';
        this.pendingAttachments.forEach((item, index) => {
            const wrap = document.createElement('div');
            wrap.className = 'support-attach-thumb';
            const img = document.createElement('img');
            img.src = item.url;
            img.alt = 'Превью';
            const removeBtn = document.createElement('button');
            removeBtn.type = 'button';
            removeBtn.className = 'support-attach-remove';
            removeBtn.textContent = '×';
            removeBtn.addEventListener('click', () => {
                URL.revokeObjectURL(item.url);
                this.pendingAttachments.splice(index, 1);
                this.renderAttachPreview();
            });
            wrap.appendChild(img);
            wrap.appendChild(removeBtn);
            this.attachPreview.appendChild(wrap);
        });
    }

    clearAttachments() {
        this.pendingAttachments.forEach((item) => URL.revokeObjectURL(item.url));
        this.pendingAttachments = [];
        this.renderAttachPreview();
    }

    getRecipientUUID() {
        const meta = this.currentTicketMeta || {};
        if (this.mode === 'staff') {
            return meta.renter_uuid
                || document.querySelector(`.ticket[data-ticket-id="${this.currentTicketId}"]`)?.dataset.renterUuid;
        }
        return meta.support_uuid
            || document.querySelector(`.ticket[data-ticket-id="${this.currentTicketId}"]`)?.dataset.supportUuid
            || null;
    }

    async sendMessage() {
        if (!this.currentTicketId) {
            this.showError('Выберите заявку');
            return;
        }

        if (this.currentTicketMeta?.is_closed) {
            this.showError('Заявка закрыта — отправка сообщений недоступна');
            return;
        }

        const text = this.messageInput?.value.trim() || '';
        const files = this.pendingAttachments.map((a) => a.file);

        if (!text && files.length === 0) {
            this.showError('Введите сообщение или прикрепите изображения');
            return;
        }

        if (text.length > 1024) {
            this.showError('Сообщение не длиннее 1024 символов');
            return;
        }

        const formData = new FormData();
        formData.append('ticket_id', String(this.currentTicketId));
        formData.append('sender_id', this.userUUID);
        formData.append('msg', text);
        files.forEach((file) => formData.append('media', file));

        if (this.sendButton) {
            this.sendButton.disabled = true;
        }

        try {
            const response = await fetch('/api/support/ticket/message/create/', {
                method: 'POST',
                body: formData,
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || 'Ошибка отправки');
            }

            this.messageInput.value = '';
            this.clearAttachments();
            this.displayMessage(data, true);
            this.broadcastMessage(data);
            await this.loadTickets();
            if (this.currentTicketId) {
                await this.loadMessages(this.currentTicketId);
            }
        } catch (error) {
            this.showError(error.message || 'Не удалось отправить сообщение');
        } finally {
            if (this.sendButton) {
                this.sendButton.disabled = false;
            }
        }
    }

    broadcastMessage(data) {
        if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
            return;
        }
        this.socket.send(JSON.stringify({
            type: 'MSG',
            ticket_id: data.ticket_id || this.currentTicketId,
            from: this.userUUID,
            to: this.getRecipientUUID(),
            msg: data.msg || '',
            msg_id: data.msg_id,
            datetime: data.datetime,
            media: data.media || [],
        }));
    }

    async closeCurrentTicket() {
        if (!this.currentTicketId) {
            this.showError('Выберите заявку');
            return;
        }

        const meta = this.currentTicketMeta || {};
        if (!meta.can_close) {
            this.showError(meta.close_hint || 'Закрытие заявки сейчас недоступно');
            return;
        }

        if (!confirm('Закрыть эту заявку?')) {
            return;
        }

        const body = this.mode === 'staff'
            ? { grant_person_uuid: this.userUUID }
            : { renter_uuid: this.userUUID };

        try {
            const response = await fetch(`/api/support/ticket/${this.currentTicketId}/close/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || 'Не удалось закрыть заявку');
            }
            if (typeof showNotification === 'function') {
                showNotification(data.message || 'Заявка закрыта', 'success');
            }
            await this.loadTickets();
            if (this.currentTicketId) {
                await this.loadMessages(this.currentTicketId);
            }
        } catch (error) {
            this.showError(error.message || 'Не удалось закрыть заявку');
        }
    }

    formatDateTime(datetime) {
        if (!datetime) {
            return '';
        }
        try {
            return new Date(datetime).toLocaleString('ru-RU', {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
            });
        } catch {
            return String(datetime);
        }
    }

    showError(message) {
        if (typeof showNotification === 'function') {
            showNotification(message, 'error');
        } else {
            console.error(message);
        }
    }
}

document.addEventListener('DOMContentLoaded', async () => {
    if (document.getElementById('ticketsBlock')) {
        window.supportChat = await SupportChat.create();
    }
});
