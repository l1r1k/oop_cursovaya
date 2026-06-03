async function trackRequest(){
    const id=document.getElementById('requestIdInput').value;
    if (!id) return;
    try { 
        const data=await apiRequest(`/api/request/${id}/track/`);
        renderRequestInfo(data)
    } catch(e){
        alert('Заявка не найдена')
    }
}
function renderRequestInfo(d){
    document.getElementById('requestInfo').innerHTML=`
        <h2>Заявка #${d.id}</h2>
        <p>Дата: ${d.date} ${d.time}</p>
        <p>Статус: <span class="status-badge status-${d.status.toLowerCase().replace(/\s/g,'-')}">${d.status}</span></p>
        ${d.rent?`<h3 style="margin-top:2rem">Аренда</h3><p>С ${d.rent.date_start} по ${d.rent.date_end}</p><p>Статус: ${d.rent.status}</p>`:''}
        <h3 style="margin-top:2rem">Состав заявки</h3>
        <div class="request-items">
            ${d.items.map(i=>
                `
                <div class="item-card">
                    <img src="${i.photo||''}" class="item-image">
                    <div>
                        <h4>${i.name}</h4>
                        <p>Количество: ${i.quantity} шт.</p>
                        <span class="cost-per-day-label">Стоимость за сутки:</span>
                        <span class="cost-per-day">
                            ${i.cost} ₽
                        </span>
                    </div>
                </div>`).join('')}
        </div>
        <div class="rent-final-block">
            <div class="rent-final-info">
                <div>
                    <div class="rent-final-info-days">
                        Количество суток: <strong>${d.rent.delta}</strong>
                    </div>
                    <div class="rent-final-info-cost-label">
                        Итоговая стоимость аренды:
                    </div>
                </div>
                <div class="rent-final-info-cost-block">
                    <div class="rent-final-total-cost">
                        ${d.rent.total_cost} ₽
                    </div>
                </div>
            </div>
        </div>
        `;
    document.getElementById('requestInfo').style.display='block'
}