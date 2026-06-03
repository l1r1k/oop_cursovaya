/**
 * Модальная идентификация по email для страниц поддержки (Renter / GrantPerson).
 */
class SupportIdentity {
    constructor(mode) {
        this.mode = mode;
        this.storageKey = mode === 'staff' ? 'grantPersonUUID' : 'renterUUID';
        this.apiPrefix = mode === 'staff' ? '/api/identity/grant-person' : '/api/identity/renter';
        this.pendingEmail = '';
        this.pendingUuid = this.generateUUID();

        this.modal = document.getElementById('identityModal');
        this.titleEl = document.getElementById('identityModalTitle');
        this.hintEl = document.getElementById('identityModalHint');
        this.errorEl = document.getElementById('identityError');

        this.stepEmail = document.getElementById('identityStepEmail');
        this.stepCode = document.getElementById('identityStepCode');
        this.registerForm = document.getElementById('identityRegisterForm');

        this.emailInput = document.getElementById('identityEmail');
        this.codeInput = document.getElementById('identityCode');
        this.registerEmailInput = document.getElementById('identityRegisterEmail');

        this.bindEvents();
        this.setTexts();
    }

    onCloseAttempt() {
        if (typeof showNotification === 'function') {
            showNotification('Для доступа к поддержке необходимо подтвердить личность', 'info');
        }
    }

    setTexts() {
        if (this.mode === 'staff') {
            this.titleEl.textContent = 'Вход в панель поддержки';
            this.hintEl.textContent =
                'Укажите рабочую почту сотрудника. Если профиль найден, мы отправим код подтверждения.';
        } else {
            this.titleEl.textContent = 'Доступ к поддержке';
            this.hintEl.textContent =
                'Укажите email, который вы использовали при оформлении заказа. Если профиль найден, мы отправим код подтверждения.';
        }
    }

    bindEvents() {
        document.getElementById('identityEmailBtn')?.addEventListener('click', () => this.onEmailSubmit());
        this.emailInput?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                this.onEmailSubmit();
            }
        });

        document.getElementById('identityCodeBtn')?.addEventListener('click', () => this.onCodeSubmit());
        this.codeInput?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                this.onCodeSubmit();
            }
        });

        document.getElementById('identityBackToEmailBtn')?.addEventListener('click', () => this.showStep('email'));
        document.getElementById('identityRegisterBackBtn')?.addEventListener('click', () => this.showStep('email'));
        document.getElementById('identityModalCloseBtn')?.addEventListener('click', () => this.onCloseAttempt());

        this.registerForm?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.onRegisterSubmit();
        });
    }

    generateUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
            const r = Math.random() * 16 | 0;
            const v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    showError(message) {
        if (!this.errorEl) {
            return;
        }
        this.errorEl.textContent = message;
        this.errorEl.style.display = message ? 'block' : 'none';
    }

    showStep(step) {
        this.showError('');
        this.stepEmail.style.display = step === 'email' ? 'block' : 'none';
        this.stepCode.style.display = step === 'code' ? 'block' : 'none';
        this.registerForm.style.display = step === 'register' ? 'block' : 'none';
    }

    hideModal() {
        if (this.modal) {
            this.modal.classList.remove('active');
            this.modal.style.display = 'none';
        }
        document.getElementById('supportMain')?.classList.remove('support-locked');
    }

    showModal() {
        if (this.modal) {
            this.modal.classList.add('active');
            this.modal.style.display = 'flex';
        }
        document.getElementById('supportMain')?.classList.add('support-locked');
    }

    async ensure() {
        const stored = sessionStorage.getItem(this.storageKey);
        if (stored) {
            const exists = await this.checkUuid(stored);
            if (exists) {
                this.hideModal();
                return stored;
            }
            sessionStorage.removeItem(this.storageKey);
        }

        this.showModal();
        this.showStep('email');

        return new Promise((resolve) => {
            this._resolve = resolve;
        });
    }

    async checkUuid(uuid) {
        try {
            const response = await fetch(`${this.apiPrefix}/${encodeURIComponent(uuid)}/check/`);
            if (!response.ok) {
                return false;
            }
            const data = await response.json();
            return Boolean(data.exists);
        } catch {
            return false;
        }
    }

    finish(uuid) {
        sessionStorage.setItem(this.storageKey, uuid);
        if (this.mode === 'renter') {
            window.renterUUID = uuid;
        }
        this.hideModal();
        if (this._resolve) {
            this._resolve(uuid);
        }
    }

    async onEmailSubmit() {
        const email = this.emailInput?.value.trim();
        if (!email) {
            this.showError('Введите email');
            return;
        }

        this.showError('');
        const btn = document.getElementById('identityEmailBtn');
        const originalText = btn?.textContent;
        if (btn) {
            btn.disabled = true;
            btn.textContent = 'Проверка...';
        }

        try {
            const response = await fetch(`${this.apiPrefix}/request-code/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email }),
            });
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Ошибка запроса');
            }

            this.pendingEmail = email;

            if (data.found) {
                this.showStep('code');
                this.codeInput.value = '';
                this.codeInput.focus();
                if (typeof showNotification === 'function') {
                    showNotification(data.message || 'Код отправлен на email', 'success');
                }
            } else {
                this.pendingUuid = this.generateUUID();
                this.registerEmailInput.value = email;
                this.showStep('register');
            }
        } catch (error) {
            this.showError(error.message || 'Не удалось выполнить запрос');
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.textContent = originalText;
            }
        }
    }

    async onCodeSubmit() {
        const code = this.codeInput?.value.trim();
        if (!code) {
            this.showError('Введите код из письма');
            return;
        }

        const btn = document.getElementById('identityCodeBtn');
        const originalText = btn?.textContent;
        if (btn) {
            btn.disabled = true;
            btn.textContent = 'Проверка...';
        }

        try {
            const response = await fetch(`${this.apiPrefix}/verify-code/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    email: this.pendingEmail,
                    code,
                }),
            });
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Неверный код');
            }

            this.finish(data.uuid);
        } catch (error) {
            this.showError(error.message || 'Не удалось подтвердить код');
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.textContent = originalText;
            }
        }
    }

    async onRegisterSubmit() {
        if (!this.registerForm?.checkValidity()) {
            this.registerForm.reportValidity();
            return;
        }

        const formData = new FormData(this.registerForm);
        const payload = {
            uuid: this.pendingUuid,
            email: this.pendingEmail || formData.get('email'),
            first_name: formData.get('first_name'),
            last_name: formData.get('last_name'),
            middle_name: formData.get('middle_name') || '',
            phone_number: formData.get('phone_number'),
        };

        const btn = document.getElementById('identityRegisterBtn');
        const originalText = btn?.textContent;
        if (btn) {
            btn.disabled = true;
            btn.textContent = 'Сохранение...';
        }

        try {
            const response = await fetch(`${this.apiPrefix}/register/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Не удалось создать профиль');
            }

            if (typeof showNotification === 'function') {
                showNotification(data.message || 'Профиль создан', 'success');
            }
            this.finish(data.uuid);
        } catch (error) {
            this.showError(error.message || 'Ошибка регистрации');
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.textContent = originalText;
            }
        }
    }
}
