document.addEventListener('DOMContentLoaded', function() {
    const applyFiltersBtn = document.getElementById('apply-filters');
    const clearFiltersBtn = document.getElementById('clear-filters');
    const clearDatesBtn = document.getElementById('clear-dates');
    const exportExcelBtn = document.getElementById('export-excel');
    const startDateInput = document.getElementById('start-date');
    const endDateInput = document.getElementById('end-date');
    const statusFilterSelect = document.getElementById('status-filter');
    const tableContainer = document.querySelector('.table-container');

    applyFiltersBtn.addEventListener('click', applyFilters);
    clearFiltersBtn.addEventListener('click', clearFilters);
    clearDatesBtn.addEventListener('click', clearDates);
    exportExcelBtn.addEventListener('click', exportExcel);

    function applyFilters() {
        const startDate = startDateInput.value;
        const endDate = endDateInput.value;
        const statusFilter = statusFilterSelect.value;

        console.log('Applying filters:', { startDate, endDate, statusFilter });

        const params = new URLSearchParams();
        if (startDate) params.append('start_date', startDate);
        if (endDate) params.append('end_date', endDate);
        if (statusFilter && statusFilter !== 'all') params.append('status_filter', statusFilter);

        const url = `/history_table_data?${params.toString()}`;
        console.log('Request URL:', url);

        fetch(url)
            .then(response => {
                console.log('Response status:', response.status);
                return response.json();
            })
            .then(data => {
                console.log('Response data:', data);
                if (data.error) {
                    showError(data.error);
                    return;
                }
                updateTable(data.table_data, data.date_range, statusFilter);
            })
            .catch(error => {
                console.error('Ошибка при применении фильтров:', error);
                showError('Ошибка при загрузке данных');
            });
    }

    function clearFilters() {
        startDateInput.value = '';
        endDateInput.value = '';
        statusFilterSelect.value = 'all';
        applyFilters();
    }

    function clearDates() {
        startDateInput.value = '';
        endDateInput.value = '';
        applyFilters();
    }

    function exportExcel() {
        const startDate = startDateInput.value;
        const endDate = endDateInput.value;
        const statusFilter = statusFilterSelect.value;

        const params = new URLSearchParams();
        if (startDate) params.append('start_date', startDate);
        if (endDate) params.append('end_date', endDate);
        if (statusFilter && statusFilter !== 'all') params.append('status_filter', statusFilter);

        const url = `/export_history_excel?${params.toString()}`;
        
        const link = document.createElement('a');
        link.href = url;
        link.download = `history_table_${new Date().toISOString().slice(0, 10)}.xlsx`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    function updateTable(tableData, dateRange, currentFilter = 'all') {
        if (!dateRange || dateRange.length === 0) {
            tableContainer.innerHTML = '<div class="no-data"><p>Нет данных для отображения</p></div>';
            return;
        }

        const showSuccess = currentFilter === 'all' || currentFilter === 'success';
        const showError = currentFilter === 'all' || currentFilter === 'error';

        let successRows = '';
        let errorRows = '';

        if (showSuccess) {
            successRows = `
                <tr class="success-count-row">
                    <td class="row-label">Успешно</td>
                    ${dateRange.map(date => {
                        const successData = tableData[date]?.success || { count: 0, claims: [] };
                        return `<td class="success-count-cell">${successData.count}</td>`;
                    }).join('')}
                </tr>
                ${[0, 1, 2].map(i => `
                    <tr class="success-claims-row">
                        <td class="row-label"></td>
                        ${dateRange.map(date => {
                            const successData = tableData[date]?.success || { count: 0, claims: [] };
                            const claim = successData.claims[i] || '';
                            return `<td class="success-claim-cell">${claim}</td>`;
                        }).join('')}
                    </tr>
                `).join('')}
            `;
        }

        if (showError) {
            errorRows = `
                <tr class="error-count-row">
                    <td class="row-label">Сбой</td>
                    ${dateRange.map(date => {
                        const errorData = tableData[date]?.error || { count: 0, claims: [] };
                        return `<td class="error-count-cell">${errorData.count}</td>`;
                    }).join('')}
                </tr>
                ${[0, 1, 2].map(i => `
                    <tr class="error-claims-row">
                        <td class="row-label"></td>
                        ${dateRange.map(date => {
                            const errorData = tableData[date]?.error || { count: 0, claims: [] };
                            const claim = errorData.claims[i] || '';
                            return `<td class="error-claim-cell">${claim}</td>`;
                        }).join('')}
                    </tr>
                `).join('')}
            `;
        }

        let tableHTML = `
            <table class="history-table">
                <thead>
                    <tr>
                        <th class="row-header">Дата</th>
                        ${dateRange.map(date => `<th class="date-header">${date}</th>`).join('')}
                    </tr>
                </thead>
                <tbody>
                    ${successRows}
                    ${errorRows}
                </tbody>
            </table>
        `;

        tableContainer.innerHTML = tableHTML;
    }

    function showError(message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: #fee2e2;
            color: #991b1b;
            padding: 12px 16px;
            border-radius: 8px;
            border: 1px solid #fecaca;
            z-index: 1000;
            font-weight: 600;
        `;
        errorDiv.textContent = message;
        
        document.body.appendChild(errorDiv);
        
        setTimeout(() => {
            if (errorDiv.parentNode) {
                errorDiv.parentNode.removeChild(errorDiv);
            }
        }, 5000);
    }
}); 