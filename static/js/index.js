// Глобальные переменные
let addedRequests = [];
let processingStats = null;
let scheduleSettings = null;
let currentTimeInterval = null;

// Загрузка статистики при загрузке страницы
document.addEventListener('DOMContentLoaded', async function() {
    await loadProcessingStats();
    await loadScheduleSettings();
    startTimeUpdates();
    setupTimeValidation();
    restoreTimeToStart();
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

// Загрузка настроек расписания
async function loadScheduleSettings() {
    try {
        const response = await fetch('/api/schedule/settings');
        if (response.ok) {
            const data = await response.json();
            scheduleSettings = data;
            
            // Заполняем поля времени
            if (data.start_time) {
                document.getElementById('start-time').value = data.start_time;
            }
            if (data.end_time) {
                document.getElementById('end-time').value = data.end_time;
            }
            
            updateScheduleStatus();
        }
    } catch (error) {
        console.error('Ошибка загрузки настроек расписания:', error);
    }
}

// Сохранение настроек расписания
async function saveScheduleSettings() {
    const startTime = document.getElementById('start-time').value;
    const endTime = document.getElementById('end-time').value;
    
    if (!startTime || !endTime) {
        return false;
    }
    
    try {
        const response = await fetch('/api/schedule/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                start_time: startTime,
                end_time: endTime
            })
        });
        
        if (response.ok) {
            const data = await response.json();
            scheduleSettings = data;
            updateScheduleStatus();
            return true;
        }
    } catch (error) {
        console.error('Ошибка сохранения настроек расписания:', error);
    }
    
    return false;
}

// Запуск обновления времени
function startTimeUpdates() {
    updateCurrentTime();
    currentTimeInterval = setInterval(updateCurrentTime, 1000);
}

// Обновление текущего времени
function updateCurrentTime() {
    const now = new Date();
    const timeString = now.toLocaleTimeString('ru-RU', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        timeZone: 'Europe/Moscow'
    });
    
    const currentTimeElement = document.getElementById('current-time');
    if (currentTimeElement) {
        currentTimeElement.textContent = timeString;
    }
    updateScheduleStatus();
}

// Настройка валидации времени
function setupTimeValidation() {
    const startTimeInput = document.getElementById('start-time');
    const endTimeInput = document.getElementById('end-time');
    
    startTimeInput.addEventListener('change', validateTimeInputs);
    endTimeInput.addEventListener('change', validateTimeInputs);
    
    // Автоматическое сохранение при изменении
    startTimeInput.addEventListener('blur', async function() {
        if (validateTimeInputs()) {
            await saveScheduleSettings();
        }
    });
    
    endTimeInput.addEventListener('blur', async function() {
        if (validateTimeInputs()) {
            await saveScheduleSettings();
        }
    });
}

// Валидация полей времени
function validateTimeInputs() {
    const startTime = document.getElementById('start-time').value;
    const endTime = document.getElementById('end-time').value;
    const startValidation = document.getElementById('start-validation');
    const endValidation = document.getElementById('end-validation');
    
    // Очищаем предыдущие сообщения
    startValidation.textContent = '';
    startValidation.className = 'time-validation';
    endValidation.textContent = '';
    endValidation.className = 'time-validation';
    
    // Проверяем, что оба поля заполнены
    if (!startTime || !endTime) {
        return false;
    }
    
    // Парсим время
    const startParts = startTime.split(':').map(Number);
    const endParts = endTime.split(':').map(Number);
    
    // Проверяем корректность времени
    if (startParts[0] < 0 || startParts[0] > 23 || startParts[1] < 0 || startParts[1] > 59) {
        startValidation.textContent = 'Некорректное время';
        startValidation.className = 'time-validation error';
        return false;
    }
    
    if (endParts[0] < 0 || endParts[0] > 23 || endParts[1] < 0 || endParts[1] > 59) {
        endValidation.textContent = 'Некорректное время';
        endValidation.className = 'time-validation error';
        return false;
    }
    
    // Проверяем, что время начала меньше времени окончания
    const startMinutes = startParts[0] * 60 + startParts[1];
    const endMinutes = endParts[0] * 60 + endParts[1];
    
    if (startMinutes >= endMinutes) {
        startValidation.textContent = 'Время начала должно быть раньше окончания';
        startValidation.className = 'time-validation error';
        endValidation.textContent = 'Время окончания должно быть позже начала';
        endValidation.className = 'time-validation error';
        return false;
    }
    
    // Показываем успешную валидацию
    startValidation.textContent = '✓ Валидно';
    startValidation.className = 'time-validation success';
    endValidation.textContent = '✓ Валидно';
    endValidation.className = 'time-validation success';
    
    return true;
}

// Обновление статуса расписания
function updateScheduleStatus() {
    const statusDot = document.getElementById('status-dot');
    const statusText = document.getElementById('status-text');
    const timeToStartElement = document.getElementById('time-to-start');
    
    if (!scheduleSettings || !scheduleSettings.start_time || !scheduleSettings.end_time) {
        if (statusDot && statusText) {
            statusDot.className = 'status-dot inactive';
            statusText.textContent = 'Парсер неактивен';
            statusText.className = 'status-text inactive';
        }
        if (timeToStartElement) {
            timeToStartElement.style.display = 'none';
        }
        return;
    }
    
    const now = new Date();
    const currentTime = now.toLocaleTimeString('ru-RU', {
        hour: '2-digit',
        minute: '2-digit',
        timeZone: 'Europe/Moscow'
    });
    
    const startTime = scheduleSettings.start_time;
    const endTime = scheduleSettings.end_time;
    
    // Проверяем, находимся ли мы в рабочем времени
    const isInWorkingHours = isTimeInRange(currentTime, startTime, endTime);
    
    if (!statusDot || !statusText) return;
    
    if (isInWorkingHours) {
        statusDot.className = 'status-dot active';
        statusText.textContent = 'Парсер активен';
        statusText.className = 'status-text active';
        
        if (timeToStartElement) {
            timeToStartElement.style.display = 'none';
        }
    } else {
        // Проверяем, ждем ли мы начала или уже закончили
        const timeToStart = getTimeToStart(currentTime, startTime);
        const timeToEnd = getTimeToEnd(currentTime, endTime);
        
        if (timeToStart > 0) {
            const timeToStartFormatted = formatTimeToStart(timeToStart);
            statusDot.className = 'status-dot waiting';
            statusText.textContent = 'Ожидание начала';
            statusText.className = 'status-text waiting';
            
            // Обновляем время до запуска
            if (timeToStartElement) {
                timeToStartElement.style.display = 'block';
                timeToStartElement.textContent = `${timeToStartFormatted.hours}ч ${timeToStartFormatted.minutes}м`;
                
                // Сохраняем время до запуска в localStorage
                localStorage.setItem('timeToStart', JSON.stringify({
                    hours: timeToStartFormatted.hours,
                    minutes: timeToStartFormatted.minutes,
                    timestamp: Date.now()
                }));
            }
        } else {
            statusDot.className = 'status-dot inactive';
            statusText.textContent = 'Парсер неактивен';
            statusText.className = 'status-text inactive';
            
            if (timeToStartElement) {
                timeToStartElement.style.display = 'none';
            }
        }
    }
}

// Проверка, находится ли время в диапазоне
function isTimeInRange(currentTime, startTime, endTime) {
    const current = timeToMinutes(currentTime);
    const start = timeToMinutes(startTime);
    const end = timeToMinutes(endTime);
    
    if (start <= end) {
        // Обычный случай: 09:00 - 18:00
        return current >= start && current <= end;
    } else {
        // Переход через полночь: 22:00 - 06:00
        return current >= start || current <= end;
    }
}

// Получение времени до начала работы
function getTimeToStart(currentTime, startTime) {
    const current = timeToMinutes(currentTime);
    const start = timeToMinutes(startTime);
    
    if (current < start) {
        return start - current;
    } else {
        // До следующего дня
        return (24 * 60) - current + start;
    }
}

// Получение времени до окончания работы
function getTimeToEnd(currentTime, endTime) {
    const current = timeToMinutes(currentTime);
    const end = timeToMinutes(endTime);
    
    if (current <= end) {
        return end - current;
    } else {
        // До следующего дня
        return (24 * 60) - current + end;
    }
}

// Конвертация времени в минуты
function timeToMinutes(timeString) {
    const parts = timeString.split(':').map(Number);
    return parts[0] * 60 + parts[1];
}

// Форматирование времени в часы и минуты
function formatTimeToStart(minutes) {
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return { hours, minutes: mins };
}

// Восстановление времени до запуска из localStorage
function restoreTimeToStart() {
    const timeToStartElement = document.getElementById('time-to-start');
    if (!timeToStartElement) return;
    
    const savedTime = localStorage.getItem('timeToStart');
    if (savedTime) {
        try {
            const timeData = JSON.parse(savedTime);
            const now = Date.now();
            const timeDiff = now - timeData.timestamp;
            
            // Если прошло больше 5 минут, считаем данные устаревшими
            if (timeDiff > 5 * 60 * 1000) {
                localStorage.removeItem('timeToStart');
                timeToStartElement.style.display = 'none';
                return;
            }
            
            // Показываем сохраненное время
            timeToStartElement.style.display = 'block';
            timeToStartElement.textContent = `${timeData.hours}ч ${timeData.minutes}м`;
            
            // Обновляем статус
            const statusDot = document.getElementById('status-dot');
            const statusText = document.getElementById('status-text');
            
            if (statusDot && statusText) {
                statusDot.className = 'status-dot waiting';
                statusText.textContent = 'Ожидание начала';
                statusText.className = 'status-text waiting';
            }
            
        } catch (error) {
            console.error('Ошибка восстановления времени до запуска:', error);
            localStorage.removeItem('timeToStart');
        }
    }
}

// Добавление заявки
document.getElementById('add-request-btn').addEventListener('click', function() {
    const claimNumber = document.getElementById('claim_number').value.trim();
    const vinNumber = document.getElementById('vin_number').value.trim();
    
    if (!claimNumber && !vinNumber) {
        showErrorModal('Введите номер дела или VIN номер');
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
        showErrorModal('Такая заявка уже добавлена!');
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

// Обработчик отправки формы
document.getElementById('login-form').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const formData = new FormData(this);
    const username = formData.get('username');
    const password = formData.get('password');
    const svgCollection = formData.get('svg_collection');
    
    // Проверяем, что есть заявки в списке
    if (addedRequests.length === 0) {
        showErrorModal('Очередь пуста. Добавьте заявки перед отправкой.');
        return;
    }
    
    // Проверяем настройки времени работы
            const startTime = document.getElementById('start-time').value;
        const endTime = document.getElementById('end-time').value;
    
    if (!startTime || !endTime) {
        showErrorModal('Настройте время работы парсера перед отправкой заявок.');
        return;
    }
    
    if (!validateTimeInputs()) {
        showErrorModal('Проверьте корректность настроек времени работы.');
        return;
    }
    
    try {
        // Показываем индикатор прогресса
        const submitBtn = this.querySelector('button[type="submit"]');
        const originalText = submitBtn.textContent;
        submitBtn.disabled = true;
        submitBtn.textContent = 'Отправка заявок...';
        
        // Отправляем все заявки из списка
        for (let i = 0; i < addedRequests.length; i++) {
            const request = addedRequests[i];
            
            // Обновляем текст кнопки с прогрессом
            submitBtn.textContent = `Отправка заявки ${i + 1} из ${addedRequests.length}...`;
            
            // Создаем FormData для каждой заявки
            const requestFormData = new FormData();
            requestFormData.append('username', username);
            requestFormData.append('password', password);
            requestFormData.append('claim_number', request.claimNumber === 'Не задано' ? '' : request.claimNumber);
            requestFormData.append('vin_number', request.vinNumber === 'Не задано' ? '' : request.vinNumber);
            requestFormData.append('svg_collection', svgCollection);
            
            // Отправляем заявку на сервер
            const response = await fetch('/login', {
                method: 'POST',
                body: requestFormData
            });
            
            const data = await response.json();
            
            if (!data.success) {
                showErrorModal(`Ошибка добавления заявки ${i + 1}: ${data.error}`);
                submitBtn.disabled = false;
                submitBtn.textContent = originalText;
                return;
            }
            
            // Если парсер не в рабочем времени, показываем дополнительную информацию
            if (!data.is_working_hours && data.time_to_start_minutes > 0) {
                const hours = Math.floor(data.time_to_start_minutes / 60);
                const minutes = data.time_to_start_minutes % 60;
                
                showNotification(
                    `⏰ Обработка начнется в ${data.start_time} (через ${hours}ч ${minutes}м)`,
                    'info'
                );
            }
            
            // Небольшая задержка между заявками
            if (i < addedRequests.length - 1) {
                await new Promise(resolve => setTimeout(resolve, 100));
            }
        }
        
        // Проверяем, есть ли информация о времени начала обработки
        const lastResponse = await fetch('/api/schedule/status');
        const scheduleStatus = await lastResponse.json();
        
        if (scheduleStatus.status === 'waiting' && scheduleStatus.time_to_start_minutes > 0) {
            const hours = Math.floor(scheduleStatus.time_to_start_minutes / 60);
            const minutes = scheduleStatus.time_to_start_minutes % 60;
            
            showNotification(
                `✅ Все ${addedRequests.length} заявок добавлены в очередь. Обработка начнется в ${scheduleStatus.settings.start_time} (через ${hours}ч ${minutes}м)`,
                'success'
            );
        } else {
            showNotification(`✅ Все ${addedRequests.length} заявок добавлены в очередь и начали обрабатываться`, 'success');
        }
        
        // Очищаем список заявок после успешной отправки
        addedRequests = [];
        updateRequestsList();
        updateTotalTime();
        
        // Восстанавливаем кнопку
        submitBtn.disabled = false;
        submitBtn.textContent = originalText;
        
    } catch (error) {
        console.error('Ошибка отправки формы:', error);
        showErrorModal('Ошибка соединения с сервером');
        
        // Восстанавливаем кнопку при ошибке
        const submitBtn = this.querySelector('button[type="submit"]');
        submitBtn.disabled = false;
        submitBtn.textContent = 'Войти';
    }
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

// Функции для работы с модальным окном ошибок
function showErrorModal(message) {
    const modal = document.getElementById('error-modal');
    const errorMessage = document.getElementById('error-message');
    
    errorMessage.textContent = message;
    modal.classList.add('show');
    
    // Закрытие по клику вне модального окна
    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            closeErrorModal();
        }
    });
    
    // Закрытие по Escape
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeErrorModal();
        }
    });
}

function closeErrorModal() {
    const modal = document.getElementById('error-modal');
    modal.classList.remove('show');
}

// Функция для показа уведомлений
function showNotification(message, type) {
    // Создаем элемент уведомления
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 12px 16px;
        border-radius: 6px;
        color: white;
        font-weight: 500;
        z-index: 1000;
        transform: translateX(100%);
        transition: transform 0.3s ease;
        ${type === 'success' ? 'background: #059669;' : 'background: #dc2626;'}
    `;
    
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

// Очистка интервала при уходе со страницы
window.addEventListener('beforeunload', function() {
    if (currentTimeInterval) {
        clearInterval(currentTimeInterval);
    }
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