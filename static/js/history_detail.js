// Функция переключения вкладок
function switchTab(tabName) {
    // Убираем активный класс со всех кнопок и содержимого
    document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    
    // Добавляем активный класс к выбранной вкладке
    event.target.classList.add('active');
    document.getElementById('tab-' + tabName).classList.add('active');
}

// Функция выбора зоны опций
function selectOptionsZone(zoneIndex, zoneTitle) {
    // Убираем активный класс со всех заголовков зон
    document.querySelectorAll('.section-header').forEach(header => header.classList.remove('active'));
    // Добавляем активный класс к выбранному заголовку
    // Находим элемент с соответствующими data-атрибутами
    const targetHeader = document.querySelector(`.section-header[data-zone-index="${zoneIndex}"][data-zone-title="${zoneTitle}"]`);
    if (targetHeader) {
        targetHeader.classList.add('active');
    }
    
    const detailContent = document.getElementById('options-detail-content');
    
    // Получаем данные опций из глобальной переменной
    const optionsData = window.optionsData || [];
    
    if (!optionsData || !optionsData[zoneIndex]) {
        detailContent.innerHTML = '<div class="no-selection-message">Опции не найдены для данной зоны</div>';
        return;
    }
    
    const zone = optionsData[zoneIndex];
    const options = zone.options || [];
    
    if (!options || options.length === 0) {
        detailContent.innerHTML = '<div class="no-selection-message">Опции не найдены для данной зоны</div>';
        return;
    }
    
    if (options.length === 1 && options[0].title === "Нет соответствующих модельных опций для данной зоны") {
        detailContent.innerHTML = '<div class="no-selection-message">Нет соответствующих модельных опций для данной зоны</div>';
        return;
    }
    
    // Формируем HTML для опций
    let optionsHtml = `
        <h3 style="margin-bottom: 20px; color: #495057; border-bottom: 2px solid #e9ecef; padding-bottom: 10px;">
            ${zoneTitle}
        </h3>
        <div class="selected-zone-options">
    `;
    
    options.forEach(option => {
        // Убираем префикс "AZT -" из названия опции
        let displayTitle = option.title || "—";
        let displayCode = option.code || "—";
        
        if (displayTitle.startsWith("AZT - ")) {
            displayTitle = displayTitle.substring(6); // Убираем "AZT - "
            displayCode = "AZT"; // Устанавливаем код AZT
        }
        
        optionsHtml += `
            <div class="option-item">
                <span class="option-code">${displayCode}</span>
                <span class="option-title">${displayTitle}</span>
                <span class="option-status">
                    ${option.selected 
                        ? '<span class="option-selected">✅</span>' 
                        : '<span class="option-not-selected">❌</span>'
                    }
                </span>
            </div>
        `;
    });
    
    optionsHtml += '</div>';
    detailContent.innerHTML = optionsHtml;
}

// Упрощенная проверка файлов без async/await для лучшей производительности
function checkFileExists(url) {
    return new Promise((resolve) => {
        const img = new Image();
        img.onload = () => resolve(true);
        img.onerror = () => resolve(false);
        img.src = url;
    });
}

// Функция для скачивания SVG файлов
function downloadSVG(svgPath, filename) {
    if (!svgPath || svgPath.trim() === '') {
        alert('SVG файл недоступен');
        return;
    }
    
    const link = document.createElement('a');
    link.href = svgPath;
    link.download = filename || 'download.svg';
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Получаем данные зон из глобальной переменной
    const zoneData = window.zoneData || [];
    const zoneButtons = document.querySelectorAll('.zone-button');
    const detailsList = document.getElementById('details-list');
    const mainScreenshot = document.getElementById('main-screenshot');
    const allZonesButton = document.querySelector('.all-zones-button');

    if (allZonesButton) {
        allZonesButton.addEventListener('click', () => {
            // Убираем активный класс со всех кнопок зон
            zoneButtons.forEach(btn => btn.classList.remove('active'));
            // Добавляем активный класс к кнопке "Все зоны"
            allZonesButton.classList.add('active');
            
            if (detailsList) {
                detailsList.querySelectorAll('.item-button').forEach(btn => btn.classList.remove('active'));
                detailsList.innerHTML = '<div class="no-selection-message">Выберите зону для просмотра деталей</div>';
            }
            if (mainScreenshot) {
                // Возвращаем основной скриншот
                const originalSrc = mainScreenshot.getAttribute('data-original-src') || mainScreenshot.src;
                mainScreenshot.src = originalSrc;
            }
        });
    }

    zoneButtons.forEach(button => {
        button.addEventListener('click', () => {
            // Убираем активный класс со всех кнопок зон
            zoneButtons.forEach(btn => btn.classList.remove('active'));
            // Убираем активный класс с кнопки "Все зоны"
            if (allZonesButton) {
                allZonesButton.classList.remove('active');
            }
            // Добавляем активный класс к выбранной кнопке
            button.classList.add('active');

            const zoneTitle = button.getAttribute('data-zone-title');
            const zone = zoneData.find(z => z.title === zoneTitle);

            if (zone && mainScreenshot && detailsList) {
                const screenshotPath = zone.screenshot_path || mainScreenshot.getAttribute('data-original-src');
                mainScreenshot.src = screenshotPath;

                detailsList.innerHTML = '';
                let hasContent = false;

                // Добавляем детали
                if (zone.details && zone.details.length > 0) {
                    hasContent = true;
                    zone.details.forEach(detail => {
                        const detailSection = document.createElement('div');
                        detailSection.className = 'table-section';
                        detailSection.innerHTML = `
                            <div class="item-row">
                                ${detail.svg_path && detail.svg_path.trim() ? `<a href="${detail.svg_path}" download class="svg-download" title="Скачать SVG">
                                <span class="download-icon">⬇</span>
                            </a>` : ''}
                                <button class="item-button" data-detail-title="${detail.title}">${detail.title}</button>
                            </div>
                        `;
                        const detailButton = detailSection.querySelector('.item-button');
                        detailButton.addEventListener('click', () => {
                            detailsList.querySelectorAll('.item-button').forEach(btn => btn.classList.remove('active'));
                            detailButton.classList.add('active');
                            const detailSvgPath = detail.svg_path || zone.screenshot_path;
                            mainScreenshot.src = detailSvgPath;
                        });
                        detailsList.appendChild(detailSection);
                    });
                }

                // Исправил пути для пиктограмм
                if (zone.pictograms && zone.pictograms.length > 0) {
                    hasContent = true;
                    zone.pictograms.forEach(pictogram => {
                        if (pictogram.works && pictogram.works.length > 0) {
                            pictogram.works.forEach(work => {
                                const workTitle = work.work_name2 ? `${work.work_name1} (${work.work_name2})` : work.work_name1;
                                const pictogramSection = document.createElement('div');
                                pictogramSection.className = 'table-section';
                                pictogramSection.innerHTML = `
                                    <div class="item-row">
                                        ${work.svg_path && work.svg_path.trim() ? `<a href="${work.svg_path}" download class="svg-download" title="Скачать SVG">
                                    <span class="download-icon">⬇</span>
                                </a>` : ''}
                                        <button class="item-button" data-detail-title="${workTitle}">${workTitle}</button>
                                    </div>
                                `;
                                const workButton = pictogramSection.querySelector('.item-button');
                                workButton.addEventListener('click', () => {
                                    detailsList.querySelectorAll('.item-button').forEach(btn => btn.classList.remove('active'));
                                    workButton.classList.add('active');
                                    const workSvgPath = work.svg_path || zone.screenshot_path;
                                    mainScreenshot.src = workSvgPath;
                                });
                                detailsList.appendChild(pictogramSection);
                            });
                        }
                    });
                }

                if (!hasContent) {
                    detailsList.innerHTML = '<div class="no-selection-message">Нет деталей для данной зоны</div>';
                }
            }
        });
    });

    // Добавляем обработчики для зон опций с data-атрибутами
    document.querySelectorAll('.section-header[data-zone-index]').forEach(header => {
        header.addEventListener('click', function() {
            const zoneIndex = parseInt(this.getAttribute('data-zone-index'));
            const zoneTitle = this.getAttribute('data-zone-title');
            selectOptionsZone(zoneIndex, zoneTitle);
        });
    });
}); 