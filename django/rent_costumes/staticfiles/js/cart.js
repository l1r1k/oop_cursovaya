let cartItems = [];

async function loadCart() {
    const items = cart.items;
    
    if (!items.length) {
        renderEmptyCart();
        const cartSummary = document.getElementById('cartSummary');
        if (cartSummary){
            cartSummary.remove();
        }
        return;
    }
    
    try {
        const cartContentItems = document.getElementsByClassName('cart-item');
        if (cartContentItems.length === 0){
            document.getElementById('cartContent').innerHTML = `
                <div class="cart-item-skeleton skeleton">
                    <div class="skeleton-cart-img skeleton"></div>
                    <div class="cart-item-skeleton-info">
                        <h3 class="skeleton-text skeleton"></h3>
                        <p class="skeleton-text short skeleton"></p>
                        <p class="skeleton-text short skeleton"></p>
                        <div style="margin-top: 0.5rem; font-size: 0.9rem;">
                            <span class="skeleton-text skeleton"></span>
                        </div>
                    </div>
                </div>
            `;
        }
        
        const promises = items.map(item => 
            apiRequest(`/api/costume/${item.costumeId}/`)
        );
        cartItems = await Promise.all(promises);
        
        const availabilityPromises = items.map(item =>
            apiRequest(`/api/costume/${item.costumeId}/availability/`)
        );
        const availabilities = await Promise.all(availabilityPromises);
        
        cartItems = cartItems.map((c, i) => ({
            ...c,
            quantity: items[i].quantity,
            maxAvailable: availabilities[i].total_count
        }));
        
        renderCart();
    } catch (e) {
        console.error(e);
        document.getElementById('cartContent').innerHTML = `
            <div style="text-align: center; padding: 2rem;">
                <h3>Ошибка загрузки корзины</h3>
                <p>Попробуйте обновить страницу</p>
            </div>
        `;
    }
}

function renderEmptyCart() {
    document.getElementById('cartContent').innerHTML = `
        <div class="cart-empty">
            <div class="cart-empty-icon">🛒</div>
            <h2>Корзина пуста</h2>
            <p>Добавьте костюмы из каталога</p>
            <a href="/" class="btn btn-primary" style="margin-top:1rem">В каталог</a>
        </div>
    `;
}

function updateFinalCost(){
    const costs = document.querySelectorAll('#costumeCost');
    const finalCost = document.getElementById('totalCost');
    let cost = 0;
    costs.forEach((item) => {
        cost += Number(item.textContent.replace('₽', ''));
    });
    finalCost.textContent = String(cost) + '₽';
}

function renderCart() {
    const html = cartItems.map(item => `
        <div class="cart-item" id="cart-item-${item.id}">
            <img src="${item.photos[0]?.url || ''}" class="cart-item-image" alt="${item.description}">
            
            <div class="cart-item-info">
                <h3 style="cursor: pointer;" onclick="window.location.href='/costume/${item.id}/'">
                    ${item.name}
                </h3>
                <p style="color: var(--secondary);">${item.classification}</p>
                <p class="costume-rent-cost" id="costumeCost">${item.rent_cost * item.quantity}₽</p>
                
                <div style="margin-top: 0.5rem; font-size: 0.9rem;">
                    <span style="color: ${item.quantity <= item.maxAvailable ? 'var(--primary)' : 'var(--accent)'};">
                        ${item.quantity <= item.maxAvailable 
                            ? `Доступно: ${item.maxAvailable} шт.`
                            : `Доступно только ${item.maxAvailable} шт.!`
                        }
                    </span>
                </div>
            </div>
            
            <div class="cart-item-actions">
                <div class="quantity-control">
                    <button 
                        class="quantity-btn" 
                        onclick="decrementQuantity(${item.id})"
                        title="Уменьшить количество"
                    >
                        −
                    </button>
                    <input 
                        class="quantity-input" 
                        type="number" 
                        value="${item.quantity}" 
                        min="1"
                        max="${item.maxAvailable}"
                        onchange="changeQuantity(${item.id}, this.value)"
                        id="quantity-${item.id}"
                    >
                    <button 
                        class="quantity-btn" 
                        onclick="incrementQuantity(${item.id})"
                        ${item.quantity >= item.maxAvailable ? 'disabled style="opacity: 0.5; cursor: not-allowed;"' : ''}
                        title="${item.quantity >= item.maxAvailable ? 'Достигнут максимум' : 'Увеличить количество'}"
                    >
                        +
                    </button>
                </div>
                
                ${item.quantity > item.maxAvailable 
                    ? `<div style="color: var(--accent); font-size: 0.85rem; text-align: center; margin-top: 0.5rem;">
                        Превышен лимит!<br>
                        <button 
                            class="btn btn-secondary" 
                            style="padding: 0.5rem 1rem; margin-top: 0.5rem;"
                            onclick="fixQuantity(${item.id}, ${item.maxAvailable})"
                        >
                            Исправить (${item.maxAvailable} шт.)
                        </button>
                       </div>`
                    : ''
                }
                
                <button class="remove-btn" onclick="removeFromCart(${item.id})">
                    Удалить
                </button>
            </div>
        </div>
    `).join('');
    
    document.getElementById('cartContent').innerHTML = html;
    const cartSummary = document.getElementById('cartSummary');
    const totalItems = document.getElementById('totalCost');
    if (totalItems.classList.contains('skeleton')){
        cartSummary.innerHTML = `
            <h3>Итого</h3>
            <p>Костюмов: <strong id="totalItems">0</strong></p>
            <p>Общая стоимость за сутки: <strong class="costume-rent-cost" id="totalCost">0₽</strong></p>
            <button class="btn btn-primary checkout-btn" onclick="openCheckoutModal()">Оформить заявку</button>
        `
    }
    updateSummary();
    updateFinalCost();
}

function updateSummary() {
    const totalItems = cartItems.reduce((sum, item) => sum + item.quantity, 0);
    const hasErrors = cartItems.some(item => item.quantity > item.maxAvailable);
    
    document.getElementById('totalItems').textContent = totalItems;
    
    const checkoutBtn = document.querySelector('.checkout-btn');
    if (hasErrors) {
        checkoutBtn.disabled = true;
        checkoutBtn.style.opacity = '0.5';
        checkoutBtn.style.cursor = 'not-allowed';
        checkoutBtn.textContent = 'Исправьте количество';
    } else {
        checkoutBtn.disabled = false;
        checkoutBtn.style.opacity = '1';
        checkoutBtn.style.cursor = 'pointer';
        checkoutBtn.textContent = 'Оформить заявку';
    }
}

async function incrementQuantity(costumeId) {
    showNotification('Проверяем наличие товара', 'info')
    const success = await cart.increment(costumeId);
    
    if (success) {
        await loadCart();
        showNotification('Количество товаров увеличено', 'success')
    }
}

async function decrementQuantity(costumeId) {
    showNotification('Проверяем наличие товара', 'info')
    const success = await cart.decrement(costumeId);

    if (success) {
        await loadCart();
        showNotification('Количество товаров уменьшено', 'success')
    }
}

async function changeQuantity(costumeId, value) {
    const quantity = parseInt(value);
    if (isNaN(quantity) || quantity < 1) {
        showNotification('Количество должно быть не менее 1', 'error');
        await loadCart();
        return;
    }
    await cart.update(costumeId, quantity);
    await loadCart();
}

async function fixQuantity(costumeId, maxQuantity) {
    await cart.update(costumeId, maxQuantity);
    showNotification(`Количество исправлено на ${maxQuantity} шт.`, 'success');
    await loadCart();
}

function removeFromCart(costumeId) {
    if (confirm('Удалить этот костюм из корзины?')) {
        cart.remove(costumeId);
        loadCart();
        showNotification('Костюм удален из корзины', 'info');
    }
}

function openCheckoutModal() {
    const hasErrors = cartItems.some(item => item.quantity > item.maxAvailable);
    
    if (hasErrors) {
        showNotification('Сначала исправьте количество костюмов', 'error');
        return;
    }

    const result = apiRequest(`/api/renter/${renterUUID}/`);
    result.then(response => {
        document.getElementById('last_name').value = response.last_name;
        document.getElementById('first_name').value = response.first_name;
        document.getElementById('middle_name').value = response.middle_name;
        document.getElementById('phone_number').value = response.phone_number;
        document.getElementById('email').value = response.email;
    }).catch(error => {
        showNotification('Вы ничего еще не заказывали, заполните пожалуйста форму!', 'info');
    });

    document.getElementById('checkoutModal').classList.add('active');


}

function closeCheckoutModal() {
    document.getElementById('checkoutModal').classList.remove('active');
    
    const form = document.getElementById('checkoutForm');
    if (form) {
        form.reset();
        form.style.display = 'block';
    }
    
    const msg = document.getElementById('successMessage');
    if (msg) {
        msg.style.display = 'none';
    }
}

async function submitRequest(e) {
    e.preventDefault();
    const form = e.target;
    const formData = new FormData(form);
    const renterData = {};
    formData.forEach((v, k) => renterData[k] = v);
    renterData['uuid'] = renterUUID;
    
    const itemsData = cart.items.map(i => ({
        costume_id: i.costumeId,
        quantity: i.quantity
    }));
    
    const submitBtn = form.querySelector('button[type="submit"]');
    const originalBtnText = submitBtn.textContent;
    submitBtn.textContent = 'Отправка...';
    submitBtn.disabled = true;
    
    try {
        const result = await apiRequest('/api/request/create/', {
            method: 'POST',
            body: JSON.stringify({
                renter: renterData,
                items: itemsData
            })
        });
        
        form.style.display = 'none';
        const msg = document.getElementById('successMessage');
        msg.style.display = 'block';
        document.getElementById('requestIdMessage').innerHTML = 
            `<strong>Номер заявки: #${result.request_id}</strong>`;
        
        cart.clear();
        
        setTimeout(() => {
            window.location.href = `/track/?request_id=${result.request_id}`;
        }, 3000);
        
    } catch (error) {
        submitBtn.textContent = originalBtnText;
        submitBtn.disabled = false;
        
        let errorMessage = 'Произошла ошибка при создании заявки';
        
        try {
            const errorText = await error.text();
            const errorData = JSON.parse(errorText);
            errorMessage = errorData.error || errorMessage;
        } catch (e) {
            console.error('Error parsing error response:', e);
        }
        
        showNotification(errorMessage, 'error');
    }
}

document.addEventListener('DOMContentLoaded', loadCart);

window.onclick = function(event) {
    const modal = document.getElementById('checkoutModal');
    if (event.target === modal) {
        closeCheckoutModal();
    }
};

window.addEventListener('storage', (e) => {
    if (e.key === 'cart') {
        loadCart();
    }
});