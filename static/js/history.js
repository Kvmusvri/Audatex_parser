// Глобальные переменные
let processingStats = null;

// Загрузка статистики времени обработки
async function loadProcessingStats() {
    try {
        const response = await fetch('/api/processing-stats');
        const data = await response.json();
        processingStats = data;
        
        document.getElementById('average-time').textContent = data.average_time;
        document.getElementById('total-completed').textContent = data.total_completed;
    } catch (error) {
        console.error('Ошибка загрузки статистики:', error);
        document.getElementById('average-time').textContent = '—';
        document.getElementById('total-completed').textContent = '0';
    }
}

// Загрузка статистики при загрузке страницы
document.addEventListener('DOMContentLoaded', async function() {
    await loadProcessingStats();
    
    const filterButtons = document.querySelectorAll('.history-button');
    const historyRecords = document.querySelectorAll('.history-record');
    
    // Функция определения статуса записи
    function getRecordStatus(record) {
        const jsonCompleted = record.dataset.jsonCompleted === 'true';
        const dbSaved = record.dataset.dbSaved === 'true';
        const optionsSuccess = record.dataset.optionsSuccess === 'true';
        const totalZones = parseInt(record.dataset.totalZones || '0');
        const status = record.dataset.status.toLowerCase();
        
        // Если все флаги true и total_zones > 0 - завершено
        if (jsonCompleted && dbSaved && optionsSuccess && totalZones > 0) {
            return 'completed';
        }
        
        // Если статус "в процессе"
        if (status.includes('в процессе')) {
            return 'in-process';
        }
        
        // Если есть ошибки в флагах (любой флаг false)
        if (!jsonCompleted || !dbSaved || !optionsSuccess || totalZones === 0) {
            return 'error';
        }
        
        return 'unknown';
    }

    // Функция для показа модального окна с ошибкой
    function showErrorModal(errorType, errorMessage, buttonElement) {
        // Удаляем существующее модальное окно если есть
        const existingModal = document.querySelector('.error-modal');
        if (existingModal) {
            existingModal.remove();
        }

        const modal = document.createElement('div');
        modal.className = 'error-modal';
        modal.innerHTML = `
            <div class="error-modal-content">
                <div class="error-modal-header">
                    <h3>${errorType}</h3>
                    <button class="error-modal-close">&times;</button>
                </div>
                <div class="error-modal-body">
                    <p>${errorMessage}</p>
                </div>
            </div>
        `;

        // Позиционируем модальное окно относительно плашки
        const recordElement = buttonElement.closest('.history-record');
        
        // Устанавливаем позиционирование для плашки
        recordElement.style.position = 'relative';
        recordElement.appendChild(modal);

        // Проверяем, не выходит ли модальное окно за правый край экрана
        setTimeout(() => {
            const modalRect = modal.getBoundingClientRect();
            const viewportWidth = window.innerWidth;
            
            if (modalRect.right > viewportWidth - 20) {
                // Если выходит за край, позиционируем слева от плашки
                modal.style.left = 'auto';
                modal.style.right = '100%';
                modal.style.transform = 'translateX(-20px)';
                modal.style.marginLeft = '0';
                modal.style.marginRight = '12px';
                
                // Меняем стрелку на левую сторону
                modal.style.setProperty('--arrow-left', 'auto');
                modal.style.setProperty('--arrow-right', '-8px');
                modal.style.setProperty('--arrow-border', 'border-left: 8px solid white; border-right: none;');
            }
        }, 10);

        // Анимация появления
        setTimeout(() => modal.classList.add('show'), 50);

        // Закрытие по клику на крестик
        modal.querySelector('.error-modal-close').addEventListener('click', () => {
            modal.classList.remove('show');
            setTimeout(() => modal.remove(), 400);
        });

        // Закрытие при клике вне модального окна
        document.addEventListener('click', function closeModal(e) {
            if (!modal.contains(e.target) && !buttonElement.contains(e.target)) {
                modal.classList.remove('show');
                setTimeout(() => modal.remove(), 400);
                document.removeEventListener('click', closeModal);
            }
        });
    }

    // Функция для определения типа ошибки и показа модального окна
    function handleErrorClick(record, buttonElement) {
        const jsonCompleted = record.dataset.jsonCompleted === 'true';
        const dbSaved = record.dataset.dbSaved === 'true';
        const optionsSuccess = record.dataset.optionsSuccess === 'true';
        const totalZones = parseInt(record.dataset.totalZones || '0');

        if (!jsonCompleted) {
            showErrorModal('Ошибка записи JSON', 'Ошибка при записи в JSON, заявка не завершена', buttonElement);
        } else if (!dbSaved) {
            showErrorModal('Ошибка базы данных', 'Ошибка при записи в базу данных', buttonElement);
        } else if (!optionsSuccess) {
            showErrorModal('Ошибка сбора опций', 'Ошибка при сборе опций автомобиля', buttonElement);
        } else if (totalZones === 0) {
            showErrorModal('Ошибка сбора SVG', 'Ошибка при сборе SVG схем', buttonElement);
        }
    }

    // Делаем функцию глобальной для использования в onclick
    window.handleErrorClick = handleErrorClick;
    
    // Функция обновления счетчиков
    function updateStatusCounts() {
        let completedCount = 0;
        let inProcessCount = 0;
        let errorCount = 0;
        
        historyRecords.forEach(record => {
            const recordStatus = getRecordStatus(record);
            if (recordStatus === 'completed') {
                completedCount++;
            } else if (recordStatus === 'in-process') {
                inProcessCount++;
            } else if (recordStatus === 'error') {
                errorCount++;
            }
        });
        
        document.getElementById('completed-count').textContent = completedCount;
        document.getElementById('in-process-count').textContent = inProcessCount;
        document.getElementById('error-count').textContent = errorCount;
    }
    
    // Функция фильтрации
    function filterRecords() {
        const activeFilter = document.querySelector('.history-button.active').dataset.filter;
        
        historyRecords.forEach(record => {
            const recordStatus = getRecordStatus(record);
            
            // Проверяем фильтр
            let matchesFilter = false;
            if (activeFilter === 'all') {
                matchesFilter = true;
            } else if (activeFilter === 'completed') {
                matchesFilter = recordStatus === 'completed';
            } else if (activeFilter === 'in-process') {
                matchesFilter = recordStatus === 'in-process';
            } else if (activeFilter === 'error') {
                matchesFilter = recordStatus === 'error';
            }
            
            // Показываем/скрываем запись
            if (matchesFilter) {
                record.style.display = 'block';
            } else {
                record.style.display = 'none';
            }
        });
    }
    

    
    // Обработчики фильтров
    filterButtons.forEach(button => {
        button.addEventListener('click', function() {
            // Убираем активный класс со всех кнопок
            filterButtons.forEach(btn => btn.classList.remove('active'));
            // Добавляем активный класс к нажатой кнопке
            this.classList.add('active');
            // Применяем фильтрацию
            filterRecords();
        });
    });
    
    // Инициализация счетчиков при загрузке страницы
    updateStatusCounts();
}); 