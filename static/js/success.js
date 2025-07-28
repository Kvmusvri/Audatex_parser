// Обработчики для истории запросов
document.addEventListener('DOMContentLoaded', function() {
    // Показ первого заказа по умолчанию
    const records = document.querySelectorAll('.history-record');
    const historyButtons = document.querySelectorAll('.history-button');
    if (records.length > 0) {
        records[0].classList.add('active');
        historyButtons[0].classList.add('active');
    }

    // Поиск по номеру дела или VIN
    const searchInput = document.getElementById('history-search');
    if (searchInput) {
        searchInput.addEventListener('input', () => {
            const query = searchInput.value.toLowerCase();
            historyButtons.forEach(button => {
                const text = button.textContent.toLowerCase();
                button.style.display = text.includes(query) ? 'block' : 'none';
            });
        });
    }

    // Переключение заказов
    historyButtons.forEach(button => {
        button.addEventListener('click', () => {
            const recordIndex = button.getAttribute('data-record');
            records.forEach(r => r.classList.remove('active'));
            historyButtons.forEach(b => b.classList.remove('active'));
            document.getElementById(`record-${recordIndex}`).classList.add('active');
            button.classList.add('active');
        });
    });

    // Обработчики для каждой записи истории
    document.querySelectorAll('.history-record').forEach(record => {
        const index = record.querySelector('.all-zones-button')?.getAttribute('data-record');
        if (!index) return;
        
        const zoneButtons = record.querySelectorAll(`#zones-table-${index} .zone-button`);
        const detailsList = record.querySelector(`#details-list-${index}`);
        const mainScreenshot = record.querySelector(`#main-screenshot-${index}`);
        const allZonesButton = record.querySelector(`.all-zones-button[data-record="${index}"]`);
        
        // Получаем данные зон из глобальной переменной или атрибута
        let zoneData = [];
        try {
            // Попытка получить данные из глобальной переменной
            if (typeof historyData !== 'undefined') {
                zoneData = historyData[index - 1]?.zone_data || [];
            }
        } catch (e) {
            console.warn('Не удалось получить данные зон:', e);
        }

        if (allZonesButton) {
            allZonesButton.addEventListener('click', () => {
                zoneButtons.forEach(btn => btn.classList.remove('active'));
                detailsList.querySelectorAll('.detail-button').forEach(btn => btn.classList.remove('active'));
                if (mainScreenshot && typeof historyData !== 'undefined') {
                    mainScreenshot.src = historyData[index - 1].main_screenshot_path;
                }
                if (detailsList) {
                    detailsList.innerHTML = '';
                }
            });
        }

        zoneButtons.forEach(button => {
            button.addEventListener('click', () => {
                zoneButtons.forEach(btn => btn.classList.remove('active'));
                button.classList.add('active');

                const zoneTitle = button.getAttribute('data-zone-title');
                const zone = zoneData.find(z => z.title === zoneTitle);

                if (zone && mainScreenshot) {
                    mainScreenshot.src = zone.screenshot_path;

                    if (detailsList) {
                        detailsList.innerHTML = '';
                        if (zone.details && zone.details.length > 0) {
                            zone.details.forEach(detail => {
                                const detailButton = document.createElement('div');
                                detailButton.className = 'detail-button';
                                detailButton.innerHTML = `
                                    ${detail.svg_path && detail.svg_path.trim() ? `<a href="${detail.svg_path}" download class="svg-download detail-svg-download" title="Скачать SVG">
                                        <span class="download-icon">⬇</span>
                                    </a>` : ''}
                                    <span>${detail.title}</span>
                                `;
                                detailButton.addEventListener('click', (e) => {
                                    if (e.target.classList.contains('svg-download') || e.target.classList.contains('download-icon')) return;
                                    detailsList.querySelectorAll('.detail-button').forEach(btn => btn.classList.remove('active'));
                                    detailButton.classList.add('active');
                                    if (mainScreenshot) {
                                        mainScreenshot.src = detail.svg_path;
                                    }
                                });
                                detailsList.appendChild(detailButton);
                            });
                        }
                    }
                }
            });
        });
    });
});

// Обработчики для обычной страницы результатов (не истории)
document.addEventListener('DOMContentLoaded', function() {
    // Проверяем, есть ли данные зон на странице
    const zoneDataElement = document.getElementById('zone-data');
    if (!zoneDataElement) return; // Если нет элемента с данными зон, выходим
    
    try {
        const zoneData = JSON.parse(zoneDataElement.textContent || '[]');
        const zoneButtons = document.querySelectorAll('.zone-button');
        const detailsList = document.getElementById('details-list');
        const mainScreenshot = document.getElementById('main-screenshot');
        const allZonesButton = document.querySelector('.all-zones-button');

        if (allZonesButton) {
            allZonesButton.addEventListener('click', () => {
                zoneButtons.forEach(btn => btn.classList.remove('active'));
                if (detailsList) {
                    detailsList.querySelectorAll('.detail-button').forEach(btn => btn.classList.remove('active'));
                }
                if (mainScreenshot) {
                    mainScreenshot.src = mainScreenshot.getAttribute('data-original-src') || mainScreenshot.src;
                }
                if (detailsList) {
                    detailsList.innerHTML = '';
                }
            });
        }

        zoneButtons.forEach(button => {
            button.addEventListener('click', () => {
                zoneButtons.forEach(btn => btn.classList.remove('active'));
                button.classList.add('active');

                const zoneTitle = button.getAttribute('data-zone-title');
                const zone = zoneData.find(z => z.title === zoneTitle);

                if (zone && mainScreenshot) {
                    mainScreenshot.src = zone.screenshot_path;

                    if (detailsList) {
                        detailsList.innerHTML = '';
                        if (zone.details && zone.details.length > 0) {
                            zone.details.forEach(detail => {
                                const detailButton = document.createElement('div');
                                detailButton.className = 'detail-button';
                                detailButton.innerHTML = `
                                    ${detail.svg_path && detail.svg_path.trim() ? `<a href="${detail.svg_path}" download class="svg-download detail-svg-download" title="Скачать SVG">
                                        <span class="download-icon">⬇</span>
                                    </a>` : ''}
                                    <span>${detail.title}</span>
                                `;
                                detailButton.addEventListener('click', (e) => {
                                    if (e.target.classList.contains('svg-download') || e.target.classList.contains('download-icon')) return;
                                    detailsList.querySelectorAll('.detail-button').forEach(btn => btn.classList.remove('active'));
                                    detailButton.classList.add('active');
                                    if (mainScreenshot) {
                                        mainScreenshot.src = detail.svg_path;
                                    }
                                });
                                detailsList.appendChild(detailButton);
                            });
                        }
                    }
                }
            });
        });
    } catch (e) {
        console.error('Ошибка при обработке данных зон:', e);
    }
}); 