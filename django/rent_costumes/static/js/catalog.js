let filters = {
    size: [],
    classification: [],
    color: [],
    search: '',
    page: 1
};

let allFilters = {
    sizes: [],
    classifications: [],
    colors: []
};

let isLoading = false;
let hasMorePages = true;
let allProducts = []; // Храним все загруженные продукты

let observer = null;

function setupInfiniteScroll() {
    // Создаем sentinel элемент для отслеживания
    const sentinel = document.createElement('div');
    sentinel.id = 'scroll-sentinel';
    sentinel.style.height = '1px';
    
    const grid = document.getElementById('productsGrid');
    if (grid.parentNode) {
        grid.parentNode.appendChild(sentinel);
    }
    
    // Создаем observer
    observer = new IntersectionObserver(
        (entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting && hasMorePages && !isLoading) {
                    // Пользователь достиг конца списка - загружаем следующую страницу
                    loadMoreProducts();
                }
            });
        },
        {
            root: null, // viewport
            rootMargin: '200px', // Загружаем за 200px до конца
            threshold: 0
        }
    );
    
    observer.observe(sentinel);
}

function destroyInfiniteScroll() {
    if (observer) {
        observer.disconnect();
        observer = null;
    }
    
    const sentinel = document.getElementById('scroll-sentinel');
    if (sentinel) {
        sentinel.remove();
    }
}

async function loadFilters() {
    try {
        const data = await apiRequest('/api/catalog/filters/');
        allFilters = data;
        
        renderSizeFilters(data.sizes);
        renderClassificationFilters(data.classifications);
        renderColorFilters(data.colors);
        setupAllFilterGroup();
    } catch (error) {
        console.error('Error loading filters:', error);
    }
}

function renderSizeFilters(sizes) {
    const container = document.getElementById('sizeFilters');
    container.innerHTML = sizes.map(size => `
        <label class="filter-checkbox">
            <input 
                type="checkbox" 
                value="${size.id}"
                onchange="updateFilter('size', ${size.id}, this.checked)"
            >
            <span>${size.label} ${size.is_child ? `(${size.min_age}-${size.max_age} лет)` : ``}</span>
        </label>
    `).join('');
}

function renderClassificationFilters(classifications) {
    const container = document.getElementById('classificationFilters');
    container.innerHTML = classifications.map(cls => `
        <label class="filter-checkbox">
            <input 
                type="checkbox" 
                value="${cls.id}"
                onchange="updateFilter('classification', ${cls.id}, this.checked)"
            >
            <span>${cls.name}</span>
        </label>
    `).join('');
}

function renderColorFilters(colors) {
    const container = document.getElementById('colorFilters');
    container.innerHTML = colors.map(color => `
        <label class="filter-checkbox">
            <input 
                type="checkbox" 
                value="${color.id}"
                onchange="updateFilter('color', ${color.id}, this.checked)"
            >
            <span class="color-chip" style="background: ${color.hex_code || '#ccc'}"></span>
            <span>${color.name}</span>
        </label>
    `).join('');
}

function updateFilter(type, value, checked) {
    if (checked) {
        filters[type].push(value);
    } else {
        filters[type] = filters[type].filter(v => v !== value);
    }
    filters.page = 1;
    resetAndLoadProducts();
}

let searchTimeout;
document.getElementById('searchInput').addEventListener('input', (e) => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        filters.search = e.target.value;
        filters.page = 1;
        resetAndLoadProducts();
    }, 500);
});

// Сброс и загрузка с первой страницы (при изменении фильтров)
async function resetAndLoadProducts() {
    allProducts = [];
    filters.page = 1;
    hasMorePages = true;
    
    const grid = document.getElementById('productsGrid');
    grid.innerHTML = ''; // Очищаем сетку
    
    await loadProducts();
}

// Загрузка текущей страницы
async function loadProducts() {
    if (isLoading || !hasMorePages) return;
    
    isLoading = true;
    const grid = document.getElementById('productsGrid');
    
    // Показываем индикатор загрузки
    showLoadingIndicator();
    
    try {
        const params = new URLSearchParams({
            page: filters.page,
            per_page: 12
        });
        
        if (filters.size.length) params.set('size', filters.size.join(','));
        if (filters.classification.length) params.set('classification', filters.classification.join(','));
        if (filters.color.length) params.set('color', filters.color.join(','));
        if (filters.search) params.set('search', filters.search);
        
        const data = await apiRequest(`/api/catalog/list/?${params}`);
        
        // Добавляем новые продукты к существующим
        allProducts = allProducts.concat(data.items);
        
        // Проверяем есть ли еще страницы
        hasMorePages = data.pagination.has_next;
        
        // Удаляем индикатор загрузки
        hideLoadingIndicator();
        
        // Рендерим все продукты
        renderProducts(allProducts);
        
        // Обновляем счетчик
        updateResultsCount(data.pagination.total);
        
        // Скрываем пагинацию (больше не нужна)
        document.getElementById('pagination').innerHTML = '';
        
    } catch (error) {
        console.error('Error loading products:', error);
        hideLoadingIndicator();
        
        if (allProducts.length === 0) {
            grid.innerHTML = `
                <div class="empty-state">
                    <h2 class="empty-state-title">Ошибка загрузки</h2>
                    <p>Попробуйте обновить страницу</p>
                </div>
            `;
        }
    } finally {
        isLoading = false;
    }
}

// Загрузка следующей страницы
async function loadMoreProducts() {
    if (!hasMorePages || isLoading) return;
    
    filters.page++;
    await loadProducts();
}

function showLoadingIndicator() {
    // Проверяем есть ли уже индикатор
    if (document.getElementById('loading-indicator')) return;
    
    const indicator = document.createElement('div');
    indicator.id = 'loading-indicator';
    indicator.style.cssText = `
        grid-column: 1 / -1;
        display: flex;
        justify-content: center;
        align-items: center;
        padding: 2rem;
        gap: 1rem;
    `;
    
    indicator.innerHTML = `
        <div style="
            width: 40px;
            height: 40px;
            border: 4px solid var(--border);
            border-top-color: var(--primary);
            border-radius: 50%;
            animation: spin 1s linear infinite;
        "></div>
        <span style="color: var(--text-light); font-size: 1rem;">
            Загрузка костюмов...
        </span>
    `;
    
    // Добавляем CSS анимацию если её еще нет
    if (!document.getElementById('spin-animation')) {
        const style = document.createElement('style');
        style.id = 'spin-animation';
        style.textContent = `
            @keyframes spin {
                to { transform: rotate(360deg); }
            }
        `;
        document.head.appendChild(style);
    }
    
    document.getElementById('productsGrid').appendChild(indicator);
}

function hideLoadingIndicator() {
    const indicator = document.getElementById('loading-indicator');
    if (indicator) {
        indicator.remove();
    }
}

function renderProducts(products) {
    const grid = document.getElementById('productsGrid');
    
    // Удаляем индикатор загрузки если есть
    const loadingIndicator = document.getElementById('loading-indicator');
    if (loadingIndicator) {
        loadingIndicator.remove();
    }
    
    if (!products.length) {
        grid.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">🔍</div>
                <h2 class="empty-state-title">Ничего не найдено</h2>
                <p>Попробуйте изменить фильтры</p>
            </div>
        `;
        return;
    }
    
    // Рендерим карточки
    const cardsHtml = products.map((product, index) => {
        // Проверяем сколько уже в корзине
        const inCart = cart.getItem(product.id);
        const quantityInCart = inCart ? inCart.quantity : 0;
        const remainingAvailable = product.count - quantityInCart;
        
        return `
            <div class="costume-card" style="animation-delay: ${(index % 12) * 0.05}s" onclick="goToDetail(${product.id})">
                ${product.photo 
                    ? `<img src="${product.photo}" alt="${product.name}" class="costume-image" style="background: ${product.colors[0].hex || 'var(--bg)'};">`
                    : `<div class="costume-image placeholder"></div>`
                }
                <div class="costume-info">
                    <div class="costume-classification">${product.classification}</div>
                    <h3 class="costume-title">${product.name}</h3>
                    ${product.count > 0 
                    ? `<div style="font-size: 0.85rem; color: var(--text-light); text-align: left;">
                        Доступно: ${product.count} шт.
                        ${quantityInCart > 0 
                            ? `<br><span style="color: var(--secondary); font-weight: 600;">
                                В корзине: ${quantityInCart} шт.
                                </span>`
                            : ''
                        }
                    </div>`
                    :
                    `<span style="font-size: 0.85rem; color: var(--accent); font-weight: 600;">
                        Нет в наличии
                    </span>`}
                    <span class="costume-size">Размер: ${product.size}</span>
                    <div class="costume-colors">
                        ${product.colors.map(c => `
                            <span class="color-chip" style="background: ${c.hex || '#ccc'}" title="${c.name}"></span>
                        `).join('')}
                    </div>
                    <div class="costume-footer">
                        <span class="costume-rent-cost">${product.rent_cost}₽</span>
                        <div style="display: flex; flex-direction: column; gap: 0.5rem; align-items: flex-end;">
                            ${product.count > 0 
                                ? `
                                    <button 
                                        class="add-to-cart-btn" 
                                        onclick="event.stopPropagation(); addToCart(${product.id})"
                                        ${remainingAvailable <= 0 ? 'disabled style="opacity: 0.5; cursor: not-allowed;"' : ''}
                                    >
                                        ${remainingAvailable > 0 
                                            ? 'В корзину' 
                                            : 'Больше нет'
                                        }
                                    </button>
                                `
                                : `
                                    <button 
                                        class="add-to-cart-btn" 
                                        style="opacity: 0.5; cursor: not-allowed;"
                                        disabled
                                    >
                                        Недоступно
                                    </button>
                                `
                            }
                        </div>
                    </div>
                </div>
            </div>
        `;
    }).join('');
    
    grid.innerHTML = cardsHtml;
    
    // Добавляем индикатор загрузки в конец если есть еще страницы
    if (hasMorePages) {
        showLoadingIndicator();
    } else {
        // Показываем сообщение что все загружено
        if (products.length > 12) {
            const endMessage = document.createElement('div');
            endMessage.style.cssText = `
                grid-column: 1 / -1;
                text-align: center;
                padding: 2rem;
                color: var(--text-light);
                font-size: 0.95rem;
            `;
            endMessage.textContent = 'Все костюмы загружены';
            grid.appendChild(endMessage);
        }
    }
}

function updateResultsCount(total) {
    const loaded = allProducts.length;
    const text = hasMorePages 
        ? `Показано ${loaded} из ${total} костюмов`
        : `Найдено костюмов: ${total}`;
    
    document.getElementById('resultsCount').textContent = text;
}

function clearFilters() {
    filters = {
        size: [],
        classification: [],
        color: [],
        search: '',
        page: 1
    };
    
    document.getElementById('searchInput').value = '';
    document.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = false);
    
    resetAndLoadProducts();
}

async function addToCart(costumeId) {
    const button = event.target;
    const originalText = button.textContent;
    button.textContent = 'Проверка...';
    button.disabled = true;
    
    try {
        const success = await cart.add(costumeId, 1);
        
        if (success) {
            showNotification('Добавлено в корзину!', 'success');
            button.style.transform = 'scale(1.1)';
            setTimeout(() => {
                button.style.transform = 'scale(1)';
            }, 200);
            
            renderProducts(allProducts);
        }
    } catch (error) {
        console.error('Error adding to cart:', error);
        showNotification('Произошла ошибка. Попробуйте еще раз.', 'error');
    } finally {
        button.textContent = originalText;
        button.disabled = false;
    }
}

function goToDetail(costumeId) {
    window.location.href = `/costume/${costumeId}/`;
}

function setupFilterGroup(group, visibleCount = 3) {
    const collapse = group.querySelector('.collapse');
    const options = group.querySelector('.filter-options');
    const btn = group.querySelector('[data-toggle]');

    const items = [...options.children];

    if (items.length <= visibleCount) {
        btn.style.display = 'none';
        return;
    }

    let closedHeight = 0;

    items.slice(0, visibleCount).forEach(el => {
        closedHeight += el.offsetHeight;
    });

    collapse.style.maxHeight = closedHeight + 'px';
    collapse.classList.add('closed');

    btn.onclick = () => {
        const opened = collapse.classList.toggle('open');

        if (opened) {
            collapse.style.maxHeight = options.scrollHeight + 'px';
            btn.textContent = 'Скрыть';
        } else {
            collapse.style.maxHeight = closedHeight + 'px';
            btn.textContent = 'Показать';
        }
    }
}

function setupAllFilterGroup(){
    document.querySelectorAll('.filter-group').forEach(group => {
        setupFilterGroup(group, 3);
    });
}

const filtersCollapse = document.getElementById('filtersCollapse');
const filtersToggle = document.getElementById('filtersToggle');

function toggleAllFilters() {
    const opened = filtersCollapse.classList.toggle('open');

    if (opened) {
        filtersCollapse.style.maxHeight = filtersCollapse.scrollHeight + 'px';
        filtersToggle.textContent = 'Скрыть фильтры';
    } else {
        filtersCollapse.style.maxHeight = '0px';
        filtersToggle.textContent = 'Показать фильтры';
    }
}

filtersToggle.addEventListener('click', toggleAllFilters);

function handleResize() {
    if (window.innerWidth > 1024) {
        filtersCollapse.style.maxHeight = 'none';
    } else if (!filtersCollapse.classList.contains('open')) {
        filtersCollapse.style.maxHeight = '0px';
    }
}

window.addEventListener('resize', handleResize);
handleResize();

document.addEventListener('DOMContentLoaded', () => {
    loadFilters();
    loadProducts().then(() => {
        // Настраиваем infinite scroll после первой загрузки
        setupInfiniteScroll();
    });
});

// Обновление при изменении корзины из другой вкладки
window.addEventListener('storage', (e) => {
    if (e.key === 'cart') {
        cart.items = cart.load();
        cart.updateBadge();
        renderProducts(allProducts);
    }
});

// Очистка при уходе со страницы
window.addEventListener('beforeunload', () => {
    destroyInfiniteScroll();
});