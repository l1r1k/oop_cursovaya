let costumeData = null;
let photos = [];
let currentPhotoIndex = 0;

async function loadCostume() {
    try {
        const id = window.location.pathname.split('/')[2];
        costumeData = await apiRequest(`/api/costume/${id}/`);
        photos = costumeData.photos;
        renderCostume();
        const infoCollapse = document.querySelector('.details');
        const infoToggle = document.getElementById('infoToggle');
        infoToggle.addEventListener('click', () => {
            toggleInfo(infoToggle, infoCollapse);
        });
    } catch (e) {
        console.error(e);
        document.getElementById('costumeInfo').innerHTML = `
            <div style="text-align: center; padding: 2rem;">
                <h2>Ошибка загрузки</h2>
                <p>Костюм не найден или произошла ошибка.</p>
                <a href="/" class="btn btn-primary">Вернуться в каталог</a>
            </div>
        `;
    }
}

function renderCostume() {
    const d = costumeData;
    
    document.getElementById('mainImage').src = photos[0]?.url || '';
    document.getElementById('mainImage').classList.remove('skeleton');
    
    document.getElementById('thumbnails').innerHTML = photos.map((p, i) => 
        `<img src="${p.url}" class="thumbnail ${i === 0 ? 'active' : ''}" onclick="selectPhoto(${i})" alt="">`
    ).join('');
    
    // Проверяем сколько уже в корзине
    const inCart = cart.getItem(d.id);
    const quantityInCart = inCart ? inCart.quantity : 0;
    const remainingAvailable = d.count - quantityInCart;
    const isAvailable = d.count > 0;
    
    // Формируем информацию о доступности
    let availabilityInfo = '';
    if (isAvailable) {
        if (quantityInCart > 0) {
            availabilityInfo = `
                <div style="display: flex; flex-direction: column; gap: 0.5rem;">
                    <span style="color: var(--primary); font-weight: 600;">
                        Всего в наличии: ${d.count} шт.
                    </span>
                    <span style="color: var(--secondary); font-weight: 600;">
                        В вашей корзине: ${quantityInCart} шт.
                    </span>
                    <span style="color: ${remainingAvailable > 0 ? 'var(--primary)' : 'var(--accent)'}; font-weight: 600;">
                        ${remainingAvailable > 0 
                            ? `Можно добавить еще: ${remainingAvailable} шт.`
                            : 'Вы добавили все доступные экземпляры'
                        }
                    </span>
                </div>
            `;
        } else {
            availabilityInfo = `
                <span style="color: var(--primary); font-weight: 600;">
                    В наличии: ${d.count} шт.
                </span>
            `;
        }
    } else {
        availabilityInfo = `
            <span style="color: var(--accent); font-weight: 600;">
                Нет в наличии
            </span>
        `;
    }
    
    document.getElementById('costumeInfo').innerHTML = `
        <span class="badge">${d.classification}</span>
        <h1>${d.name}</h1>
        
        <div class="details">
            <div class="detail-row">
                <span class="detail-label">Доступность:</span>
                <div>${availabilityInfo}</div>
            </div>

            <div class="detail-row">
                <span class="detail-label">Стоимость аренды:</span>
                <span class="costume-rent-cost">${d.rent_cost}₽</span>
            </div>
            
            <div class="detail-row">
                <span class="detail-label">Размер:</span>
                <span>${d.size.label} ${d.size.is_child ? `(${d.size.min_age}-${d.size.max_age} лет)` : ''}</span>
            </div>

            <div class="detail-row">
                <span class="detail-label">Пол:</span>
                <span>${d.gender}</span>
            </div>
            
            <div class="detail-row">
                <span class="detail-label">Состояние:</span>
                <span>${d.state}</span>
            </div>
            
            <div class="detail-row">
                <span class="detail-label">Сезон:</span>
                <span>${d.season}</span>
            </div>
            
            <div class="detail-row">
                <span class="detail-label">Цвета:</span>
                <div class="colors">
                    ${d.colors.map(c => `
                        <span class="color-chip" style="background: ${c.hex || '#ccc'}" title="${c.name}"></span>
                    `).join('')}
                </div>
            </div>
            
            <div class="detail-row">
                <span class="detail-label">Материалы:</span>
                <div class="material-list">
                    ${d.materials.map(m => `<span class="material-tag">${m.name}</span>`).join('')}
                </div>
            </div>
            
            ${d.note ? `
                <div class="detail-row">
                    <span class="detail-label">Примечание:</span>
                    <span>${d.note}</span>
                </div>
            ` : ''}
        </div>

        <div class="filter-expand-btn" id="infoToggle">
            Показать
        </div>
        
        <div class="actions">
            ${isAvailable && remainingAvailable > 0
                ? `
                    <button class="btn btn-primary" onclick="addToCart(${d.id})" id="addToCartBtn">
                        Добавить в корзину
                    </button>
                    <button class="btn btn-outline" onclick="window.location.href='/cart/'">
                        Перейти в корзину
                    </button>
                `
                : isAvailable && remainingAvailable === 0
                ? `
                    <button class="btn btn-primary" disabled style="opacity: 0.6; cursor: not-allowed;">
                        Все экземпляры уже в корзине
                    </button>
                    <button class="btn btn-secondary" onclick="window.location.href='/cart/'">
                        Перейти в корзину
                    </button>
                `
                : `
                    <button class="btn btn-primary" disabled style="opacity: 0.5; cursor: not-allowed;">
                        Недоступно для заказа
                    </button>
                    <p style="color: var(--accent); margin-top: 1rem;">
                        Этот костюм временно недоступен. Пожалуйста, выберите другой.
                    </p>
                `
            }
        </div>
    `;
}

async function addToCart(costumeId) {
    const button = document.getElementById('addToCartBtn');
    if (!button) return;
    
    const originalText = button.textContent;
    button.textContent = 'Добавление...';
    button.disabled = true;
    
    try {
        const success = await cart.add(costumeId, 1);
        
        if (success) {
            showNotification('Костюм добавлен в корзину!', 'success');
            
            renderCostume();
            
            button.style.background = 'var(--secondary)';
            setTimeout(() => {
                button.style.background = '';
            }, 500);
        }
    } catch (error) {
        console.error('Error adding to cart:', error);
        showNotification('Произошла ошибка. Попробуйте еще раз.', 'error');
    } finally {
        button.textContent = originalText;
        button.disabled = false;
    }
}

function selectPhoto(i) {
    currentPhotoIndex = i;
    document.getElementById('mainImage').src = photos[i].url;
    document.querySelectorAll('.thumbnail').forEach((t, idx) => 
        t.classList.toggle('active', idx === i)
    );
}

function openFullscreen() {
    document.getElementById('fullscreenImage').src = photos[currentPhotoIndex].url;
    document.getElementById('fullscreenOverlay').classList.add('active');
}

function closeFullscreen() {
    document.getElementById('fullscreenOverlay').classList.remove('active');
}

function prevImage() {
    currentPhotoIndex = (currentPhotoIndex - 1 + photos.length) % photos.length;
    document.getElementById('fullscreenImage').src = photos[currentPhotoIndex].url;
}

function nextImage() {
    currentPhotoIndex = (currentPhotoIndex + 1) % photos.length;
    document.getElementById('fullscreenImage').src = photos[currentPhotoIndex].url;
}

document.addEventListener('DOMContentLoaded', loadCostume);

function toggleInfo(infoToggle, infoCollapse) {
    const opened = infoCollapse.classList.toggle('open')

    if (opened) {
        infoCollapse.style.maxHeight = infoCollapse.scrollHeight + 'px'
        infoToggle.textContent = 'Скрыть'
    } else {
        infoCollapse.style.maxHeight = '330px'
        infoToggle.textContent = 'Показать'
    }
}

document.addEventListener('keydown', e => {
    const overlay = document.getElementById('fullscreenOverlay');
    if (overlay && overlay.classList.contains('active')) {
        if (e.key === 'Escape') closeFullscreen();
        if (e.key === 'ArrowLeft') prevImage();
        if (e.key === 'ArrowRight') nextImage();
    }
});

window.addEventListener('storage', (e) => {
    if (e.key === 'cart' && costumeData) {
        renderCostume();
    }
});