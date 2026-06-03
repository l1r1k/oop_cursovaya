let currentTab = 'requests';
let currentRequestId = null;
let statuses = {};

let requestsState = {
    items: [],
    page: 1,
    hasMore: true,
    isLoading: false
};

let rentsState = {
    items: [],
    page: 1,
    hasMore: true,
    isLoading: false
};

let scrollObserver = null;

function setupInfiniteScroll() {
    // Создаем sentinel элемент
    const sentinel = document.createElement('div');
    sentinel.id = 'scroll-sentinel-manager';
    sentinel.style.height = '1px';
    
    const content = document.getElementById('content');
    if (content) {
        content.appendChild(sentinel);
    }
    
    // Создаем observer
    scrollObserver = new IntersectionObserver(
        (entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    if (currentTab === 'requests' && requestsState.hasMore && !requestsState.isLoading) {
                        loadMoreRequests();
                    } else if (currentTab === 'rents' && rentsState.hasMore && !rentsState.isLoading) {
                        loadMoreRents();
                    }
                }
            });
        },
        {
            root: null,
            rootMargin: '200px',
            threshold: 0
        }
    );
    
    scrollObserver.observe(sentinel);
}

function destroyInfiniteScroll() {
    if (scrollObserver) {
        scrollObserver.disconnect();
        scrollObserver = null;
    }
    
    const sentinel = document.getElementById('scroll-sentinel-manager');
    if (sentinel) {
        sentinel.remove();
    }
}

async function loadStats() {
    try {
        const data = await apiRequest('/api/manager/stats/');
        document.getElementById('stats').innerHTML = `
            <div class="stat-card">
                <h3>Заявки</h3>
                <p style="font-size:2rem;font-weight:700">${data.requests.total}</p>
            </div>
            <div class="stat-card">
                <h3>Аренды</h3>
                <p style="font-size:2rem;font-weight:700">${data.rents.total}</p>
            </div>
        `;
    } catch (error) {
    }
}

async function loadStatuses() {
    try {
        statuses = await apiRequest('/api/manager/statuses/');
    } catch (error) {
    }
}

function switchTab(tab) {
    currentTab = tab;
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    event.target.classList.add('active');
    
    if (tab === 'requests') {
        // Сбрасываем состояние и загружаем заново
        requestsState = {
            items: [],
            page: 1,
            hasMore: true,
            isLoading: false
        };
        loadRequests();
    } else {
        // Сбрасываем состояние и загружаем заново
        rentsState = {
            items: [],
            page: 1,
            hasMore: true,
            isLoading: false
        };
        loadRents();
    }
}

async function loadRequests() {
    if (requestsState.isLoading || !requestsState.hasMore) return;
    
    requestsState.isLoading = true;
    showLoadingIndicator();
    
    try {
        const params = new URLSearchParams({
            page: requestsState.page,
            per_page: 20
        });
        
        const data = await apiRequest(`/api/manager/requests/?${params}`);
        
        // Добавляем новые элементы
        requestsState.items = requestsState.items.concat(data.items);
        requestsState.hasMore = requestsState.page < data.pagination.pages;
        
        renderRequests();
        
    } catch (error) {
        showNotification('Ошибка загрузки заявок', 'error');
    } finally {
        requestsState.isLoading = false;
        hideLoadingIndicator();
    }
}

async function loadMoreRequests() {
    if (!requestsState.hasMore || requestsState.isLoading) return;
    requestsState.page++;
    await loadRequests();
}

function renderRequests() {
    const html = `
        <table class="table">
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Дата</th>
                    <th>Арендатор</th>
                    <th>Статус</th>
                    <th>Позиций</th>
                    <th>Действия</th>
                </tr>
            </thead>
            <tbody>
                ${requestsState.items.map(r => `
                    <tr>
                        <td>#${r.id}</td>
                        <td>${r.date} ${r.time}</td>
                        <td>
                            <div>${r.renter.last_name} ${r.renter.first_name}</div>
                            <button class="view-renter-btn" onclick="showRenterInfo(${JSON.stringify(r.renter).replace(/"/g, '&quot;')}, ${r.id})">
                                Подробнее
                            </button>
                        </td>
                        <td>
                            ${r.status.name === 'Выполнена' || r.status.name === 'Отменена'
                                ? `<span>${r.status.name}</span>`
                                : `<select onchange="updateRequestStatus(${r.id}, this.value)">
                                        ${statuses.request_statuses.map(s => `
                                            <option value="${s.id}" ${s.id === r.status.id ? 'selected' : ''}>
                                                ${s.name}
                                            </option>
                                        `).join('')}
                                    </select>` 
                            }
                        </td>
                        <td>${r.items_count}</td>
                        <td>
                            ${!r.has_rent && r.status.name === 'Одобрена' 
                                ? `<button class="btn btn-primary" onclick="openRentModal(${r.id})">Создать аренду</button>` 
                                : ''}
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
        
        ${requestsState.hasMore 
            ? '<div id="loading-placeholder"></div>'
            : requestsState.items.length > 0 
                ? '<div style="text-align: center; padding: 2rem; color: var(--text-light);">Все заявки загружены</div>'
                : ''
        }
    `;
    
    document.getElementById('content').innerHTML = html;
    
    // Переустанавливаем observer для нового sentinel
    destroyInfiniteScroll();
    if (requestsState.hasMore) {
        setupInfiniteScroll();
    }
}

async function loadRents() {
    if (rentsState.isLoading || !rentsState.hasMore) return;
    
    rentsState.isLoading = true;
    showLoadingIndicator();
    
    try {
        const params = new URLSearchParams({
            page: rentsState.page,
            per_page: 20
        });
        
        const data = await apiRequest(`/api/manager/rents/?${params}`);
        
        // Добавляем новые элементы
        rentsState.items = rentsState.items.concat(data.items);
        rentsState.hasMore = rentsState.page < data.pagination.pages;
        
        renderRents();
        
    } catch (error) {
        showNotification('Ошибка загрузки аренд', 'error');
    } finally {
        rentsState.isLoading = false;
        hideLoadingIndicator();
    }
}

async function loadMoreRents() {
    if (!rentsState.hasMore || rentsState.isLoading) return;
    rentsState.page++;
    await loadRents();
}

function renderRents() {
    const html = `
        <table class="table">
            <thead>
                <tr>
                    <th>Заявка</th>
                    <th>Арендатор</th>
                    <th>Период</th>
                    <th>Статус</th>
                </tr>
            </thead>
            <tbody>
                ${rentsState.items.map(r => `
                    <tr>
                        <td>#${r.request_id}</td>
                        <td>
                            <div>${r.renter.last_name} ${r.renter.first_name}</div>
                            <button class="view-renter-btn" onclick="showRenterInfo(${JSON.stringify(r.renter).replace(/"/g, '&quot;')})">
                                Подробнее
                            </button>
                        </td>
                        <td>${r.date_start} - ${r.date_end}</td>
                        <td>
                            ${r.status.name === 'Завершена' || r.status.name === 'Отменена' 
                            ? `<span>${r.status.name}</span>`
                            : `<select onchange="updateRentStatus(${r.id}, this.value)">
                                    ${statuses.rent_statuses.map(s => `
                                        <option value="${s.id}" ${s.id === r.status.id ? 'selected' : ''}>
                                            ${s.name}
                                        </option>
                                    `).join('')}
                                </select>`
                            }
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
        
        ${rentsState.hasMore 
            ? '<div id="loading-placeholder"></div>'
            : rentsState.items.length > 0
                ? '<div style="text-align: center; padding: 2rem; color: var(--text-light);">Все аренды загружены</div>'
                : ''
        }
    `;
    
    document.getElementById('content').innerHTML = html;
    
    // Переустанавливаем observer для нового sentinel
    destroyInfiniteScroll();
    if (rentsState.hasMore) {
        setupInfiniteScroll();
    }
}

function showLoadingIndicator() {
    const placeholder = document.getElementById('loading-placeholder');
    if (placeholder) {
        placeholder.innerHTML = `
            <div style="
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 2rem;
                gap: 1rem;
            ">
                <div style="
                    width: 30px;
                    height: 30px;
                    border: 3px solid var(--border);
                    border-top-color: var(--primary);
                    border-radius: 50%;
                    animation: spin 1s linear infinite;
                "></div>
                <span style="color: var(--text-light);">
                    Загрузка...
                </span>
            </div>
        `;
    }
}

function hideLoadingIndicator() {
    const placeholder = document.getElementById('loading-placeholder');
    if (placeholder) {
        placeholder.innerHTML = '';
    }
}

async function updateRequestStatus(id, statusId) {
    try {
        await apiRequest(`/api/manager/request/${id}/status/`, {
            method: 'POST',
            body: JSON.stringify({status_id: parseInt(statusId)})
        });
        showNotification('Статус заявки обновлен', 'success');
        
        // Обновляем локально
        const item = requestsState.items.find(r => r.id === id);
        if (item) {
            const newStatus = statuses.request_statuses.find(s => s.id === parseInt(statusId));
            item.status = newStatus;
            renderRequests();
        }
    } catch (error) {
        showNotification('Ошибка обновления статуса', 'error');
    }
}

async function updateRentStatus(id, statusId) {
    try {
        await apiRequest(`/api/manager/rent/${id}/status/`, {
            method: 'POST',
            body: JSON.stringify({status_id: parseInt(statusId)})
        });
        showNotification('Статус аренды обновлен', 'success');
        
        // Обновляем локально
        const item = rentsState.items.find(r => r.id === id);
        if (item) {
            const newStatus = statuses.rent_statuses.find(s => s.id === parseInt(statusId));
            item.status = newStatus;
            renderRents();
        }
    } catch (error) {
        showNotification('Ошибка обновления статуса', 'error');
    }
}

async function showRenterInfo(renter, requestId) {    
    try {
        const data = await apiRequest(`/api/manager/requests/${requestId}/items/`);
        
        rentItems = data.items;
        
        renderRentItems(true);
        
        document.getElementById('rentItemsListRenter').style.display = 'block';
    } catch (error){
        console.error(error);
        showRentError('Не удалось загрузить состав заявки. Попробуйте еще раз.');
    }

    const fullName = `${renter.last_name} ${renter.first_name} ${renter.middle_name || ''}`.trim();
    
    const content = `
        <div class="renter-name">${fullName}</div>
        
        ${renter.phone_number ? `
            <div class="renter-field">
                <span class="renter-label">Телефон</span>
                <div class="renter-value">
                    <a href="tel:${renter.phone_number}" style="color:inherit;text-decoration:none">
                        ${renter.phone_number}
                    </a>
                </div>
            </div>
        ` : ''}
        
        ${renter.email ? `
            <div class="renter-field">
                <span class="renter-label">Email</span>
                <div class="renter-value">
                    <a href="mailto:${renter.email}" style="color:inherit;text-decoration:none">
                        ${renter.email}
                    </a>
                </div>
            </div>
        ` : ''}
        
        <div class="renter-field">
            <span class="renter-label">ID арендатора</span>
            <div class="renter-value">#${renter.id}</div>
        </div>
    `;
    
    document.getElementById('renterInfoContent').innerHTML = content;
    document.getElementById('renterInfoModal').classList.add('active');
}

function closeRenterModal() {
    document.getElementById('renterInfoModal').classList.remove('active');
}

let rentCostPerDay = 0;
let rentItems = [];

async function openRentModal(requestId) {
    currentRequestId = requestId;
    document.getElementById('createRentModal').classList.add('active');
    resetRentModal();
    document.getElementById('rentItemsLoading').style.display = 'block';
    
    try {
        const data = await apiRequest(`/api/manager/requests/${requestId}/items/`);
        
        rentItems = data.items;
        rentCostPerDay = data.final_cost_per_day;
        
        document.getElementById('rentItemsLoading').style.display = 'none';
        
        renderRentItems(false);
        
        document.getElementById('rentItemsList').style.display = 'block';
        document.getElementById('rentForm').style.display = 'block';
        
        let min_date_for_rent = new Date();
        min_date_for_rent.setDate(min_date_for_rent.getDate() + 14);
        let min_date_for_end_rent = min_date_for_rent;
        min_date_for_end_rent.setDate(min_date_for_end_rent.getDate() + 1);
        const min_date_start_for_rent = min_date_for_rent.toISOString().split('T')[0];
        const min_date_end_for_rent = min_date_for_end_rent.toISOString().split('T')[0];

        document.getElementById('dateStart').min = min_date_start_for_rent;
        document.getElementById('dateEnd').min = min_date_end_for_rent;
        
        document.getElementById('dateStart').value = min_date_start_for_rent;
        
        const now = new Date();
        const currentTime = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
        document.getElementById('timeStart').value = currentTime;
        
        updateEndDate();
        syncEndTime();
        calculateTotalCost();
        
    } catch (error) {
        document.getElementById('rentItemsLoading').style.display = 'none';
        console.error(error);
        showRentError('Не удалось загрузить состав заявки. Попробуйте еще раз.');
    }
}

function resetRentModal() {
    document.getElementById('rentItemsLoading').style.display = 'none';
    document.getElementById('rentItemsList').style.display = 'none';
    document.getElementById('rentForm').style.display = 'none';
    document.getElementById('rentErrorMessage').style.display = 'none';
    document.getElementById('rentForm').reset();
    
    rentCostPerDay = 0;
    rentItems = [];
}

function renderRentItems(isRenter) {    
    const html = rentItems.map((item, index) => {
        const itemData = item.item;
        
        return `
            <div class="rent-item" style="animation-delay: ${index * 0.1}s;">
                ${itemData.photo 
                    ? `<img src="${itemData.photo}" class="rent-item-image" alt="${itemData.name}">`
                    : `<div class="rent-item-image placeholder"></div>`
                }
                <div class="rent-item-info">
                    <div class="rent-item-name">${itemData.name}</div>
                    <div class="rent-item-details">
                        <div class="rent-item-detail">
                            <span>Количество: <strong>${itemData.quantity} шт.</strong></span>
                        </div>
                        <div class="rent-item-detail">
                            <span>Стоимость: <strong>${itemData.rent_cost} ₽/сут.</strong></span>
                        </div>
                        <div class="rent-item-detail">
                            <span>Итого: <strong>${itemData.rent_cost * itemData.quantity} ₽/сут.</strong></span>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }).join('');
    
    if (isRenter){
        document.getElementById('rentItemsContentRenter').innerHTML = html;
    } else {
        document.getElementById('rentItemsContent').innerHTML = html;
    }
    document.getElementById('costPerDay').textContent = `${rentCostPerDay.toLocaleString('ru-RU')} ₽`;
}

function updateEndDate() {
    const dateStart = document.getElementById('dateStart').value;
    
    if (!dateStart) return;
    
    const startDate = new Date(dateStart);
    startDate.setDate(startDate.getDate() + 1);
    
    const endDate = startDate.toISOString().split('T')[0];
    document.getElementById('dateEnd').value = endDate;
    document.getElementById('dateEnd').min = endDate;
    
    calculateTotalCost();
}

function syncEndTime() {
    const timeStart = document.getElementById('timeStart').value;
    document.getElementById('timeEnd').value = timeStart;
}

function calculateTotalCost() {
    const dateStart = document.getElementById('dateStart').value;
    const dateEnd = document.getElementById('dateEnd').value;
    
    if (!dateStart || !dateEnd) {
        document.getElementById('totalDays').textContent = '0';
        document.getElementById('totalCost').textContent = '0 ₽';
        return;
    }
    
    const start = new Date(dateStart);
    const end = new Date(dateEnd);
    const diffTime = Math.abs(end - start);
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    
    if (diffDays < 1) {
        showRentError('Минимальная длительность аренды - 1 сутки');
        document.getElementById('submitRentBtn').disabled = true;
        return;
    } else {
        document.getElementById('rentErrorMessage').style.display = 'none';
        document.getElementById('submitRentBtn').disabled = false;
    }
    
    const totalCost = rentCostPerDay * diffDays;
    
    document.getElementById('totalDays').textContent = diffDays;
    document.getElementById('totalCost').textContent = `${totalCost.toLocaleString('ru-RU')} ₽`;
}

function showRentError(message) {
    const errorDiv = document.getElementById('rentErrorMessage');
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
}

function closeRentModal() {
    document.getElementById('createRentModal').classList.remove('active');
    resetRentModal();
}

async function createRent(e) {
    e.preventDefault();
    const form = e.target;
    const formData = new FormData(form);
    const data = {};
    formData.forEach((v, k) => data[k] = v);
    
    const submitBtn = document.getElementById('submitRentBtn');
    const originalText = submitBtn.textContent;
    submitBtn.textContent = 'Создание...';
    submitBtn.disabled = true;
    
    try {
        await apiRequest(`/api/manager/request/${currentRequestId}/create-rent/`, {
            method: 'POST',
            body: JSON.stringify(data)
        });
        
        closeRentModal();
        showNotification('Аренда успешно создана', 'success');
        
        requestsState = {
            items: [],
            page: 1,
            hasMore: true,
            isLoading: false
        };
        loadRequests();
        
    } catch (error) {
        let errorMessage = 'Произошла ошибка при создании аренды';
        try {
            const errorData = await error.json();
            errorMessage = errorData.error || errorMessage;
        } catch (e) {
        }
        
        showRentError(errorMessage);
        
    } finally {
        submitBtn.textContent = originalText;
        submitBtn.disabled = false;
    }
}
window.onclick = function(event) {
    const createRentModal = document.getElementById('createRentModal');
    const renterInfoModal = document.getElementById('renterInfoModal');
    
    if (event.target === createRentModal) {
        closeRentModal();
    }
    if (event.target === renterInfoModal) {
        closeRenterModal();
    }
}

document.addEventListener('DOMContentLoaded', async () => {
    // Добавляем CSS для анимации спиннера
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
    
    loadStats();
    await loadStatuses();
    await loadRequests();
});

// Очистка при уходе со страницы
window.addEventListener('beforeunload', () => {
    destroyInfiniteScroll();
});