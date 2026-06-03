class Cart {
    constructor() {
        this.items = this.load();
        this.updateBadge();
    }
    
    load() {
        const data = localStorage.getItem('cart');
        if (data) {
            const cart = JSON.parse(data);
            if (cart.expires && new Date(cart.expires) > new Date()) {
                return cart.items || [];
            }
        }
        return [];
    }
    
    save() {
        const expires = new Date();
        expires.setHours(expires.getHours() + 24);
        
        localStorage.setItem('cart', JSON.stringify({
            items: this.items,
            expires: expires.toISOString()
        }));
        
        this.updateBadge();
    }
    
    async checkAvailability(costumeId) {
        try {
            const response = await fetch(`/api/costume/${costumeId}/availability/`);
            if (!response.ok) {
                throw new Error('Failed to check availability');
            }
            const data = await response.json();
            return {
                available: data.total_count,
                isAvailable: data.is_available
            };
        } catch (error) {
            console.error('Error checking availability:', error);
            return null;
        }
    }
    
    async add(costumeId, quantity = 1) {
        const availability = await this.checkAvailability(costumeId);
        
        if (!availability) {
            showNotification('Ошибка при проверке доступности', 'error');
            return false;
        }
        
        if (!availability.isAvailable) {
            showNotification('Этот костюм недоступен для заказа', 'error');
            return false;
        }
        
        const existing = this.items.find(item => item.costumeId === costumeId);
        const currentInCart = existing ? existing.quantity : 0;
        const newTotal = currentInCart + quantity;
        
        if (newTotal > availability.available) {
            const maxCanAdd = availability.available - currentInCart;
            if (maxCanAdd <= 0) {
                showNotification(
                    `Вы уже добавили максимум доступных костюмов (${availability.available} шт.)`,
                    'error'
                );
            } else {
                showNotification(
                    `Доступно только ${availability.available} шт. В корзине уже ${currentInCart} шт. ` +
                    `Можно добавить еще максимум ${maxCanAdd} шт.`,
                    'error'
                );
            }
            return false;
        }
        
        if (existing) {
            existing.quantity += quantity;
        } else {
            this.items.push({ costumeId, quantity });
        }
        
        this.save();
        return true;
    }
    
    async update(costumeId, quantity) {
        if (quantity <= 0) {
            this.remove(costumeId);
            return true;
        }
        
        const availability = await this.checkAvailability(costumeId);
        
        if (!availability) {
            showNotification('Ошибка при проверке доступности', 'error');
            return false;
        }
        
        if (quantity > availability.available) {
            showNotification(
                `Доступно только ${availability.available} шт.`,
                'error'
            );
            return false;
        }
        
        const item = this.items.find(item => item.costumeId === costumeId);
        if (item) {
            item.quantity = quantity;
            this.save();
            return true;
        }
        
        return false;
    }
    
    async increment(costumeId) {
        const item = this.items.find(item => item.costumeId === costumeId);
        if (!item) return false;
        
        return await this.update(costumeId, item.quantity + 1);
    }
    
    async decrement(costumeId) {
        const item = this.items.find(item => item.costumeId === costumeId);
        if (!item) return false;
        
        const newQuantity = item.quantity - 1;
        
        if (newQuantity <= 0) {
            if (confirm('Удалить этот костюм из корзины?')) {
                this.remove(costumeId);
                return true;
            }
            return false;
        }
        
        return await this.update(costumeId, newQuantity);
    }
    
    remove(costumeId) {
        this.items = this.items.filter(item => item.costumeId !== costumeId);
        this.save();
    }
    
    clear() {
        this.items = [];
        this.save();
    }
    
    getCount() {
        return this.items.reduce((sum, item) => sum + item.quantity, 0);
    }
    
    updateBadge() {
        const badge = document.getElementById('cartCount');
        if (badge) {
            const count = this.getCount();
            badge.textContent = count;
            badge.style.display = count > 0 ? 'flex' : 'none';
        }
    }
    
    getItem(costumeId) {
        return this.items.find(item => item.costumeId === costumeId);
    }
}

const cart = new Cart();


function toggleMobileMenu() {
    const nav = document.getElementById('navbarNav');
    nav.classList.toggle('active');
}

async function apiRequest(url, options = {}) {
    try {
        const response = await fetch(url, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

function showNotification(message, type = 'success') {
    const notifications = document.querySelectorAll('.notification');

    if (notifications.length > 0){
        notifications.forEach(n => {
            setTimeout(() => {
                n.style.animation = 'fadeOut 0.3s ease';
                setTimeout(() => n.remove(), 100);
            }, 100);
        });
    }
    
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    const messageSpan = document.createElement('span');
    messageSpan.style.marginRight = '0.5rem';
    messageSpan.textContent = message;
    notification.appendChild(messageSpan);
    
    const colors = {
        success: 'var(--primary)',
        error: 'var(--accent)',
        warning: '#ff9800',
        info: '#2196F3'
    };
    
    Object.assign(notification.style, {
        position: 'fixed',
        top: '20px',
        left: '20px',
        padding: '1rem 1.5rem',
        background: colors[type] || colors.info,
        color: 'white',
        borderRadius: '8px',
        boxShadow: '0 8px 20px var(--shadow-strong)',
        zIndex: '3000',
        animation: 'slideIn 0.3s ease',
        maxWidth: '400px',
        wordWrap: 'break-word'
    });
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'fadeOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 4000);
}

if (!document.querySelector('#notification-styles')) {
    const style = document.createElement('style');
    style.id = 'notification-styles';
    style.textContent = `
        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateX(-100px);
            }
            to {
                opacity: 1;
                transform: translateX(0);
            }
        }
        
        @keyframes fadeOut {
            from {
                opacity: 1;
                transform: translateX(0);
            }
            to {
                opacity: 0;
                transform: translateX(-100px);
            }
        }
    `;
    document.head.appendChild(style);
}

function showActiveTab(){
    const windowUrl = window.location.pathname;
    const navLinks = document.querySelectorAll('#navLink');
    navLinks.forEach((item) => {
        const itemHref = item.getAttribute('href');
        if (windowUrl == itemHref) item.classList.add('active');
    });
}

showActiveTab();

function isSupportChatPage() {
    return /\/support(-panel)?\/?$/.test(window.location.pathname);
}

function initRenterUuidSocket() {
    if (isSupportChatPage()) {
        return;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const socket = new WebSocket(`${protocol}//${window.location.host}/ws`);
    let renterUUID = sessionStorage.getItem('renterUUID');

    socket.onopen = function () {
        if (!renterUUID) {
            socket.send(JSON.stringify({ type: 'REG' }));
        } else {
            socket.send(JSON.stringify({ type: 'AUTH', id: renterUUID }));
        }
    };

    socket.onmessage = function (event) {
        if (!event.data) {
            return;
        }
        try {
            const response = JSON.parse(event.data);
            if (response.type === 'REG') {
                sessionStorage.setItem('renterUUID', response.id);
                window.renterUUID = response.id;
            }
        } catch (error) {
            console.error('Error handling WebSocket message:', error);
        }
    };

    window.renterUUID = renterUUID || sessionStorage.getItem('renterUUID');
}

initRenterUuidSocket();