/**
 * Инициализация данных из Jinja2 шаблонов
 * Этот файл загружается после данных в HTML шаблоне
 */

(function() {
    'use strict';
    
    // Глобальные переменные с данными
    window.zoneData = [];
    window.optionsData = [];
    
    /**
     * Безопасная загрузка JSON данных из элементов
     * @param {string} elementId - ID элемента с JSON данными
     * @param {*} defaultValue - Значение по умолчанию при ошибке
     * @returns {*} Загруженные данные или значение по умолчанию
     */
    function loadJsonData(elementId, defaultValue = []) {
        try {
            const element = document.getElementById(elementId);
            if (!element) {
                console.warn(`Элемент с ID '${elementId}' не найден`);
                return defaultValue;
            }
            
            const data = JSON.parse(element.textContent.trim());
            console.log(`Данные загружены из '${elementId}':`, data);
            return data;
            
        } catch (error) {
            console.error(`Ошибка при загрузке данных из '${elementId}':`, error);
            return defaultValue;
        }
    }
    
    /**
     * Инициализация всех данных из шаблона
     */
    function initializeTemplateData() {
        // Загружаем данные зон
        window.zoneData = loadJsonData('zone-data', []);
        
        // Загружаем данные опций
        window.optionsData = loadJsonData('options-data', []);
        
        // Логируем результат инициализации
        console.log('Инициализация данных завершена:', {
            zoneDataLength: window.zoneData.length,
            optionsDataLength: window.optionsData.length
        });
    }
    
    // Запускаем инициализацию после загрузки DOM
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeTemplateData);
    } else {
        initializeTemplateData();
    }
    
})(); 