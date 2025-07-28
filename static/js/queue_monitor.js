// Глобальные переменные
let refreshInterval = null;

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    loadQueueStatus();
    setupEventListeners();
    
    // Автообновление каждые 5 секунд
    refreshInterval = setInterval(loadQueueStatus, 5000);
});

// Настройка обработчиков событий
function setupEventListeners() {
    document.getElementById('start-btn').addEventListener('click', startProcessing);
    document.getElementById('stop-btn').addEventListener('click', stopProcessing);
    document.getElementById('clear-btn').addEventListener('click', clearQueue);
    document.getElementById('refresh-btn').addEventListener('click', loadQueueStatus);
}

// Загрузка статуса очереди
async function loadQueueStatus() {
    try {
        const [statusResponse, requestsResponse] = await Promise.all([
            fetch('/api/queue/status'),
            fetch('/api/queue/requests')
        ]);
        
        const statusData = await statusResponse.json();
        const requestsData = await requestsResponse.json();
        
        if (statusData.success) {
            updateStatusDisplay(statusData.data);
        }
        
        if (requestsData.success) {
            updateQueuesDisplay(requestsData.data);
        }
        
    } catch (error) {
        console.error('Ошибка загрузки статуса очереди:', error);
        showError('Ошибка загрузки данных');
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
}

// Обновление отображения очередей
function updateQueuesDisplay(data) {
    updateQueueList('queue-list', data.processing_requests || [], 'pending');
    updateQueueList('processing-list', data.processing_requests || [], 'processing');
    updateQueueList('completed-list', data.completed_requests || [], 'completed');
}

// Обновление списка заявок
function updateQueueList(containerId, requests, status) {
    const container = document.getElementById(containerId);
    
    if (requests.length === 0) {
        container.innerHTML = '<div class="empty-message">Нет заявок</div>';
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

// Очистка интервала при закрытии страницы
window.addEventListener('beforeunload', function() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
    }
}); 