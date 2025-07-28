// Глобальные переменные
let addedRequests = [];
let processingStats = null;

// Загрузка статистики при загрузке страницы
document.addEventListener('DOMContentLoaded', async function() {
    await loadProcessingStats();
});

// Загрузка статистики времени обработки
async function loadProcessingStats() {
    try {
        const response = await fetch('/api/processing-stats');
        const data = await response.json();
        processingStats = data;
        
        document.getElementById('average-time').textContent = data.average_time;
        updateTotalTime();
    } catch (error) {
        console.error('Ошибка загрузки статистики:', error);
    }
}

// Добавление заявки
document.getElementById('add-request-btn').addEventListener('click', function() {
    const claimNumber = document.getElementById('claim_number').value.trim();
    const vinNumber = document.getElementById('vin_number').value.trim();
    
    if (!claimNumber && !vinNumber) {
        alert('Введите номер дела или VIN номер');
        return;
    }
    
    // Проверка на дубликаты
    const isDuplicate = addedRequests.some(request => 
        (request.claimNumber === (claimNumber || 'Не задано') && 
         request.vinNumber === (vinNumber || 'Не задано')) ||
        (claimNumber && request.claimNumber === claimNumber) ||
        (vinNumber && request.vinNumber === vinNumber)
    );
    
    if (isDuplicate) {
        alert('Такая заявка уже добавлена!');
        return;
    }
    
    const request = {
        id: Date.now(),
        claimNumber: claimNumber || 'Не задано',
        vinNumber: vinNumber || 'Не задано'
    };
    
    addedRequests.push(request);
    updateRequestsList();
    updateTotalTime();
    
    // Очищаем поля формы
    document.getElementById('claim_number').value = '';
    document.getElementById('vin_number').value = '';
});

// Удаление заявки
function removeRequest(requestId) {
    addedRequests = addedRequests.filter(req => req.id !== requestId);
    updateRequestsList();
    updateTotalTime();
}

// Обновление списка заявок
function updateRequestsList() {
    const requestsList = document.getElementById('requests-list');
    const totalRequests = document.getElementById('total-requests');
    
    totalRequests.textContent = addedRequests.length;
    
    if (addedRequests.length === 0) {
        requestsList.innerHTML = '<div class="empty-state">Нет добавленных заявок</div>';
        return;
    }
    
    requestsList.innerHTML = addedRequests.map((request, index) => `
        <div class="request-item" data-id="${request.id}" draggable="true">
            <div class="request-number">${index + 1}</div>
            <div class="request-info">
                <div class="request-field">
                    <span class="field-label">Номер дела:</span>
                    <span class="field-value">${request.claimNumber}</span>
                </div>
                <div class="request-field">
                    <span class="field-label">VIN:</span>
                    <span class="field-value">${request.vinNumber}</span>
                </div>
            </div>
            <button class="remove-btn" onclick="removeRequest(${request.id})" title="Удалить заявку">
                <span class="remove-icon">×</span>
            </button>
        </div>
    `).join('');
    
    // Добавляем обработчики drag & drop
    addDragAndDropHandlers();
}

// Добавление обработчиков drag & drop
function addDragAndDropHandlers() {
    const requestItems = document.querySelectorAll('.request-item');
    
    requestItems.forEach(item => {
        item.addEventListener('dragstart', handleDragStart);
        item.addEventListener('dragover', handleDragOver);
        item.addEventListener('drop', handleDrop);
        item.addEventListener('dragenter', handleDragEnter);
        item.addEventListener('dragleave', handleDragLeave);
    });
}

// Drag & Drop переменные
let draggedItem = null;
let draggedIndex = null;

function handleDragStart(e) {
    draggedItem = this;
    draggedIndex = Array.from(this.parentNode.children).indexOf(this);
    this.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
}

function handleDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
}

function handleDragEnter(e) {
    e.preventDefault();
    this.classList.add('drag-over');
}

function handleDragLeave(e) {
    this.classList.remove('drag-over');
}

function handleDrop(e) {
    e.preventDefault();
    this.classList.remove('drag-over');
    
    if (draggedItem === this) return;
    
    const dropIndex = Array.from(this.parentNode.children).indexOf(this);
    
    // Перемещаем элемент в массиве
    const [movedItem] = addedRequests.splice(draggedIndex, 1);
    addedRequests.splice(dropIndex, 0, movedItem);
    
    // Обновляем отображение
    updateRequestsList();
    updateTotalTime();
    
    // Очищаем состояние
    draggedItem.classList.remove('dragging');
    draggedItem = null;
    draggedIndex = null;
}

// Обновление общего времени обработки
function updateTotalTime() {
    if (!processingStats || addedRequests.length === 0) {
        document.getElementById('total-time').textContent = '0м 0с';
        return;
    }
    
    // Парсим среднее время
    const avgTimeMatch = processingStats.average_time.match(/(\d+)м (\d+)с/);
    if (avgTimeMatch) {
        const avgMinutes = parseInt(avgTimeMatch[1]);
        const avgSeconds = parseInt(avgTimeMatch[2]);
        const avgTotalSeconds = avgMinutes * 60 + avgSeconds;
        
        const totalSeconds = avgTotalSeconds * addedRequests.length;
        const totalMinutes = Math.floor(totalSeconds / 60);
        const remainingSeconds = totalSeconds % 60;
        
        document.getElementById('total-time').textContent = `${totalMinutes}м ${remainingSeconds}с`;
    }
}

// Обработчик кнопки остановки парсера
document.getElementById('stop-parser-btn').addEventListener('click', async function() {
    const btn = this;
    btn.disabled = true;
    btn.textContent = 'Остановка...';

    console.log('Отправка POST запроса на /terminate для остановки парсера');

    try {
        const response = await fetch('/terminate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        console.log('Ответ от /terminate:', response);

        const data = await response.json();
        console.log('Данные ответа:', data);

        const notif = document.getElementById('stop-parser-notification');
        if (response.ok && data.status === 'success') {
            notif.textContent = data.message || 'Парсер успешно остановлен.';
            notif.className = 'notification success';
        } else {
            notif.textContent = data.error || data.message || 'Ошибка при остановке парсера.';
            notif.className = 'notification error';
        }
        notif.classList.remove('hidden');
    } catch (e) {
        console.error('Ошибка при обращении к /terminate:', e);
        const notif = document.getElementById('stop-parser-notification');
        notif.textContent = 'Ошибка соединения с сервером.';
        notif.className = 'notification error';
        notif.classList.remove('hidden');
    }
    btn.disabled = false;
    btn.textContent = 'Остановить парсер';
    window.open('/', '_self');
});

// Обработчик переключателя сбора SVG
document.getElementById('svg_collection').addEventListener('change', function() {
    const statusText = document.getElementById('svg-status');
    if (this.checked) {
        statusText.textContent = 'Включен';
        statusText.classList.remove('disabled');
        statusText.classList.add('enabled');
    } else {
        statusText.textContent = 'Отключен';
        statusText.classList.remove('enabled');
        statusText.classList.add('disabled');
    }
}); 