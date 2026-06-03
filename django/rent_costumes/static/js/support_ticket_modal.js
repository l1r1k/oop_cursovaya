/**
 * Модальное окно создания тикета (только для арендатора).
 * Показывается после идентификации, если тикетов нет.
 */
class SupportTicketModal {
    constructor(chat) {
        this.chat = chat;
        this.modal = document.getElementById('ticketCreateModal');
        this.form = document.getElementById('ticketCreateForm');
        this.attachments = [];
        this._resolve = null;
        this._autoPrompt = false;

        if (!this.modal) {
            return;
        }

        this.previewEl = document.getElementById('ticketCreatePreview');
        this.fileInput = document.getElementById('ticketCreateMediaInput');
        this.errorEl = document.getElementById('ticketCreateError');

        document.getElementById('ticketCreateCloseBtn')?.addEventListener('click', () => this.hide(false));
        document.getElementById('ticketCreateAttachBtn')?.addEventListener('click', () => this.fileInput?.click());
        this.fileInput?.addEventListener('change', () => this.onFilesSelected(this.fileInput.files));
        this.form?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.submit();
        });

        SupportAttachDnd.setup({
            zones: [this.form, this.previewEl].filter(Boolean),
            onFiles: (files) => this.onFilesSelected(files),
            getCount: () => this.attachments.length,
            maxFiles: 5,
        });
    }

    showError(message) {
        if (!this.errorEl) {
            return;
        }
        this.errorEl.textContent = message || '';
        this.errorEl.style.display = message ? 'block' : 'none';
    }

    open(autoPrompt = false) {
        if (this.chat.hasOpenTicket()) {
            this.chat.notifyOpenTicketExists();
            return;
        }
        this._autoPrompt = autoPrompt;
        this.showError('');
        this.form?.reset();
        this.attachments = [];
        this.renderPreviews();
        this.modal.style.display = 'flex';
        this.modal.classList.add('active');
        document.getElementById('ticketTheme')?.focus();
    }

    hide(resolved = false) {
        this.modal.style.display = 'none';
        this.modal.classList.remove('active');
        this.attachments.forEach((item) => URL.revokeObjectURL(item.url));
        this.attachments = [];
        this.renderPreviews();
        if (this._resolve) {
            this._resolve(resolved);
            this._resolve = null;
        }
    }

    onFilesSelected(fileList) {
        const files = SupportAttachDnd.filterImages(fileList);

        for (const file of files) {
            if (this.attachments.length >= 5) {
                this.showError('Не более 5 изображений');
                break;
            }
            this.attachments.push({
                file,
                url: URL.createObjectURL(file),
            });
        }
        if (this.fileInput) {
            this.fileInput.value = '';
        }
        this.showError('');
        this.renderPreviews();
    }

    renderPreviews() {
        if (!this.previewEl) {
            return;
        }
        this.previewEl.innerHTML = '';
        this.attachments.forEach((item, index) => {
            const wrap = document.createElement('div');
            wrap.className = 'support-attach-thumb';
            const img = document.createElement('img');
            img.src = item.url;
            img.alt = 'Вложение';
            const removeBtn = document.createElement('button');
            removeBtn.type = 'button';
            removeBtn.className = 'support-attach-remove';
            removeBtn.textContent = '×';
            removeBtn.addEventListener('click', () => {
                URL.revokeObjectURL(item.url);
                this.attachments.splice(index, 1);
                this.renderPreviews();
            });
            wrap.appendChild(img);
            wrap.appendChild(removeBtn);
            this.previewEl.appendChild(wrap);
        });
    }

    async submit() {
        const theme = document.getElementById('ticketTheme')?.value.trim();
        const body = document.getElementById('ticketBody')?.value.trim();

        if (!theme) {
            this.showError('Укажите тему обращения');
            return;
        }
        if (!body && this.attachments.length === 0) {
            this.showError('Укажите текст или прикрепите изображения');
            return;
        }

        const btn = document.getElementById('ticketCreateSubmitBtn');
        const original = btn?.textContent;
        if (btn) {
            btn.disabled = true;
            btn.textContent = 'Создание...';
        }

        try {
            const formData = new FormData();
            formData.append('renter_uuid', this.chat.userUUID);
            formData.append('theme', theme);
            formData.append('body', body || '');
            this.attachments.forEach((item) => formData.append('media', item.file));

            const response = await fetch('/api/support/ticket/create/', {
                method: 'POST',
                body: formData,
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || 'Не удалось создать заявку');
            }

            if (typeof showNotification === 'function') {
                showNotification(data.message || 'Заявка создана', 'success');
            }

            this.hide(true);
            this.chat.currentTicketId = data.ticket?.ticket_id;
            await this.chat.loadTickets();
            if (data.ticket?.ticket_id) {
                await this.chat.selectTicket(data.ticket.ticket_id, data.ticket);
            }
        } catch (error) {
            this.showError(error.message || 'Ошибка создания заявки');
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.textContent = original;
            }
        }
    }

    /**
     * Автоматически предложить создание, если тикетов нет (после identity).
     */
    promptIfEmpty() {
        if (!this.modal) {
            return Promise.resolve();
        }
        return new Promise((resolve) => {
            this._resolve = resolve;
            this.open(true);
        });
    }
}
