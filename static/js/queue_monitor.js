// Глобальные переменные
let refreshInterval = null;
let lastKnownData = {
    queue_length: 0,
    processing_count: 0,
    processed_count: 0,
    failed_count: 0,
    is_running: false
};

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    loadQueueStatus();
    setupEventListeners();
    
    // Убираем автообновление - данные загружаются только по требованию
    // refreshInterval = setInterval(loadQueueStatus, 30000);
});

// Настройка обработчиков событий
function setupEventListeners() {
    document.getElementById('start-btn').addEventListener('click', startProcessing);
    document.getElementById('stop-btn').addEventListener('click', stopProcessing);
    document.getElementById('clear-btn').addEventListener('click', clearQueue);
    document.getElementById('refresh-btn').addEventListener('click', loadQueueStatus);
    
    // Обновляем данные при возвращении на страницу
    document.addEventListener('visibilitychange', function() {
        if (!document.hidden) {
            // При возвращении на страницу обновляем данные
            loadQueueStatus();
        }
    });
    
    // Периодическая проверка расхождений (без запросов к серверу)
    setInterval(function() {
        // Проверяем, есть ли расхождения между отображаемыми и сохраненными данными
        const currentDisplayed = {
            queue_length: parseInt(document.getElementById('queue-length').textContent) || 0,
            processing_count: parseInt(document.getElementById('processing-count').textContent) || 0,
            processed_count: parseInt(document.getElementById('processed-count').textContent) || 0,
            failed_count: parseInt(document.getElementById('failed-count').textContent) || 0,
            is_running: document.getElementById('processing-status').textContent === 'Запущена'
        };
        
        const hasDiscrepancy = 
            currentDisplayed.queue_length !== lastKnownData.queue_length ||
            currentDisplayed.processing_count !== lastKnownData.processing_count ||
            currentDisplayed.processed_count !== lastKnownData.processed_count ||
            currentDisplayed.failed_count !== lastKnownData.failed_count ||
            currentDisplayed.is_running !== lastKnownData.is_running;
        
        if (hasDiscrepancy) {
            document.getElementById('info-text').style.display = 'block';
        }
    }, 10000); // Проверяем каждые 10 секунд
}

// Загрузка статуса очереди
async function loadQueueStatus() {
    const refreshBtn = document.getElementById('refresh-btn');
    const originalText = refreshBtn.textContent;
    
    try {
        // Показываем индикатор загрузки
        refreshBtn.textContent = 'Обновление...';
        refreshBtn.disabled = true;
        
        const [statusResponse, requestsResponse, scheduleResponse] = await Promise.all([
            fetch('/api/queue/status'),
            fetch('/api/queue/requests'),
            fetch('/api/schedule/status')
        ]);
        
        const statusData = await statusResponse.json();
        const requestsData = await requestsResponse.json();
        const scheduleData = await scheduleResponse.json();
        
        if (statusData.success) {
            updateStatusDisplay(statusData.data);
        }
        
        if (requestsData.success) {
            updateQueuesDisplay(requestsData.data);
            // Обновляем счетчики из данных заявок
            updateCountersFromRequests(requestsData.data);
        }
        
        // Обновляем статус времени работы парсера
        updateScheduleStatus(scheduleData);
        
        // Проверяем расхождения и скрываем предупреждение
        checkDataDiscrepancy(statusData.data, requestsData.data);
        
        // Скрываем предупреждение после успешного обновления
        document.getElementById('info-text').style.display = 'none';
        
        // Показываем уведомление об успешном обновлении
        showSuccess('Данные обновлены');
        
    } catch (error) {
        console.error('Ошибка загрузки статуса очереди:', error);
        showError('Ошибка загрузки данных');
    } finally {
        // Восстанавливаем кнопку
        refreshBtn.textContent = originalText;
        refreshBtn.disabled = false;
    }
}

// Обновление отображения статуса
function updateStatusDisplay(stats) {
    const statusElement = document.getElementById('processing-status');
    const queueLengthElement = document.getElementById('queue-length');
    const processingCountElement = document.getElementById('processing-count');
    const processedCountElement = document.getElementById('processed-count');
    const failedCountElement = document.getElementById('failed-count');
    
    // Статус обработки
    if (stats.is_running) {
        statusElement.textContent = 'Запущена';
        statusElement.className = 'status-value running';
    } else {
        statusElement.textContent = 'Остановлена';
        statusElement.className = 'status-value stopped';
    }
    
    // Счетчики
    queueLengthElement.textContent = stats.queue_length || 0;
    processingCountElement.textContent = stats.processing_count || 0;
    processedCountElement.textContent = stats.processed_count || 0;
    failedCountElement.textContent = stats.failed_count || 0;
    
    // Сохраняем текущие данные для сравнения
    lastKnownData = {
        queue_length: stats.queue_length || 0,
        processing_count: stats.processing_count || 0,
        processed_count: stats.processed_count || 0,
        failed_count: stats.failed_count || 0,
        is_running: stats.is_running || false
    };
}

// Обновление счетчиков из данных заявок
function updateCountersFromRequests(data) {
    const queueLengthElement = document.getElementById('queue-length');
    const processingCountElement = document.getElementById('processing-count');
    const processedCountElement = document.getElementById('processed-count');
    
    // Обновляем счетчики из актуальных данных
    queueLengthElement.textContent = data.pending_count || 0;
    processingCountElement.textContent = data.processing_count || 0;
    
    // Подсчитываем успешно завершенные заявки
    const completedRequests = data.completed_requests || [];
    const successfulCount = completedRequests.filter(req => req.success !== false).length;
    const failedCount = completedRequests.filter(req => req.success === false).length;
    
    processedCountElement.textContent = successfulCount;
    document.getElementById('failed-count').textContent = failedCount;
}

// Проверка расхождений между отображаемыми и реальными данными
function checkDataDiscrepancy(statusData, requestsData) {
    const infoText = document.getElementById('info-text');
    
    // Получаем текущие отображаемые значения
    const currentDisplayed = {
        queue_length: parseInt(document.getElementById('queue-length').textContent) || 0,
        processing_count: parseInt(document.getElementById('processing-count').textContent) || 0,
        processed_count: parseInt(document.getElementById('processed-count').textContent) || 0,
        failed_count: parseInt(document.getElementById('failed-count').textContent) || 0,
        is_running: document.getElementById('processing-status').textContent === 'Запущена'
    };
    
    // Получаем реальные данные из ответа сервера
    const realData = {
        queue_length: statusData.queue_length || 0,
        processing_count: statusData.processing_count || 0,
        processed_count: statusData.processed_count || 0,
        failed_count: statusData.failed_count || 0,
        is_running: statusData.is_running || false
    };
    
    // Проверяем расхождения
    const hasDiscrepancy = 
        currentDisplayed.queue_length !== realData.queue_length ||
        currentDisplayed.processing_count !== realData.processing_count ||
        currentDisplayed.processed_count !== realData.processed_count ||
        currentDisplayed.failed_count !== realData.failed_count ||
        currentDisplayed.is_running !== realData.is_running;
    
    // Показываем или скрываем предупреждение
    if (hasDiscrepancy) {
        infoText.style.display = 'block';
        console.log('Обнаружено расхождение данных:', {
            displayed: currentDisplayed,
            real: realData
        });
    } else {
        infoText.style.display = 'none';
    }
}

// Обновление статуса времени работы парсера
function updateScheduleStatus(scheduleData) {
    const scheduleStatusElement = document.getElementById('schedule-status');
    
    if (!scheduleStatusElement) return;
    
    if (scheduleData.status === 'active') {
        scheduleStatusElement.textContent = `Активен (${scheduleData.settings.start_time}-${scheduleData.settings.end_time})`;
        scheduleStatusElement.className = 'status-value running';
    } else if (scheduleData.status === 'waiting') {
        const hours = Math.floor(scheduleData.time_to_start_minutes / 60);
        const minutes = scheduleData.time_to_start_minutes % 60;
        scheduleStatusElement.textContent = `Ожидание (${scheduleData.settings.start_time}-${scheduleData.settings.end_time}, через ${hours}ч ${minutes}м)`;
        scheduleStatusElement.className = 'status-value waiting';
    } else {
        scheduleStatusElement.textContent = 'Не настроено';
        scheduleStatusElement.className = 'status-value stopped';
    }
}

// Обновление отображения очередей
function updateQueuesDisplay(data) {
    updateQueueList('queue-list', data.pending_requests || [], 'pending');
    updateQueueList('processing-list', data.processing_requests || [], 'processing');
    updateQueueList('completed-list', data.completed_requests || [], 'completed');
}

// Обновление списка заявок
function updateQueueList(containerId, requests, status) {
    const container = document.getElementById(containerId);
    
    if (requests.length === 0) {
        let emptyMessage = 'Нет заявок';
        if (containerId === 'queue-list') {
            emptyMessage = 'Очередь пуста';
        } else if (containerId === 'processing-list') {
            emptyMessage = 'Нет заявок в обработке';
        } else if (containerId === 'completed-list') {
            emptyMessage = 'Нет завершенных заявок';
        }
        container.innerHTML = `<div class="empty-message">${emptyMessage}</div>`;
        return;
    }
    
    container.innerHTML = requests.map(request => createQueueItem(request, status)).join('');
}

// Создание элемента заявки
function createQueueItem(request, status) {
    const claimNumber = request.claim_number || 'Не указан';
    const vinNumber = request.vin_number || 'Не указан';
    const addedAt = request.added_at ? new Date(request.added_at).toLocaleString('ru-RU') : 'Неизвестно';
    const startedAt = request.started_at ? new Date(request.started_at).toLocaleString('ru-RU') : '';
    const completedAt = request.completed_at ? new Date(request.completed_at).toLocaleString('ru-RU') : '';
    
    let statusText = '';
    let statusClass = '';
    
    switch (status) {
        case 'pending':
            statusText = 'В очереди';
            statusClass = 'pending';
            break;
        case 'processing':
            statusText = 'В обработке';
            statusClass = 'processing';
            break;
        case 'completed':
            statusText = request.success ? 'Завершена' : 'Ошибка';
            statusClass = request.success ? 'completed' : 'failed';
            break;
    }
    
    return `
        <div class="queue-item">
            <div class="queue-item-header">
                <div class="queue-item-title">
                    ${claimNumber} | ${vinNumber}
                </div>
                <span class="queue-item-status ${statusClass}">${statusText}</span>
            </div>
            <div class="queue-item-details">
                <div>Добавлена: ${addedAt}</div>
                ${startedAt ? `<div>Начата: ${startedAt}</div>` : ''}
                ${completedAt ? `<div>Завершена: ${completedAt}</div>` : ''}
                <div>SVG: ${request.svg_collection ? 'Включен' : 'Отключен'}</div>
            </div>
        </div>
    `;
}

// Запуск обработки
async function startProcessing() {
    try {
        const response = await fetch('/api/queue/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            showSuccess('Обработка очереди запущена');
            // Показываем предупреждение о возможном расхождении
            document.getElementById('info-text').style.display = 'block';
            loadQueueStatus();
        } else {
            showError(data.message || 'Ошибка запуска обработки');
        }
        
    } catch (error) {
        console.error('Ошибка запуска обработки:', error);
        showError('Ошибка запуска обработки');
    }
}

// Остановка обработки
async function stopProcessing() {
    try {
        const response = await fetch('/api/queue/stop', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            showSuccess('Остановка обработки запрошена');
            // Показываем предупреждение о возможном расхождении
            document.getElementById('info-text').style.display = 'block';
            loadQueueStatus();
        } else {
            showError(data.message || 'Ошибка остановки обработки');
        }
        
    } catch (error) {
        console.error('Ошибка остановки обработки:', error);
        showError('Ошибка остановки обработки');
    }
}

// Очистка очереди
async function clearQueue() {
    if (!confirm('Вы уверены, что хотите очистить очередь? Это действие нельзя отменить.')) {
        return;
    }
    
    try {
        const response = await fetch('/api/queue/clear', {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            showSuccess(data.message || 'Очередь очищена');
            // Показываем предупреждение о возможном расхождении
            document.getElementById('info-text').style.display = 'block';
            // Принудительно обновляем данные через небольшую задержку
            setTimeout(() => {
                loadQueueStatus();
            }, 500);
        } else {
            showError(data.message || 'Ошибка очистки очереди');
        }
        
    } catch (error) {
        console.error('Ошибка очистки очереди:', error);
        showError('Ошибка очистки очереди');
    }
}

// Показать уведомление об успехе
function showSuccess(message) {
    showNotification(message, 'success');
}

// Показать уведомление об ошибке
function showError(message) {
    showNotification(message, 'error');
}

// Показать уведомление
function showNotification(message, type) {
    // Удаляем существующие уведомления
    const existingNotifications = document.querySelectorAll('.notification');
    existingNotifications.forEach(notification => notification.remove());
    
    // Создаем новое уведомление
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <div class="notification-content">
            <span class="notification-icon">${type === 'success' ? '✓' : '✕'}</span>
            <span class="notification-message">${message}</span>
        </div>
    `;
    
    // Добавляем стили
    notification.style.transform = 'translateX(100%)';
    
    document.body.appendChild(notification);
    
    // Анимация появления
    setTimeout(() => {
        notification.style.transform = 'translateX(0)';
    }, 100);
    
    // Автоматическое удаление через 3 секунды
    setTimeout(() => {
        notification.style.transform = 'translateX(100%)';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 300);
    }, 3000);
}

// Очистка интервала при закрытии страницы (на всякий случай)
window.addEventListener('beforeunload', function() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
    }
}); 