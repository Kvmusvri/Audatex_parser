/**
 * JavaScript для мониторинга безопасности
 */

class SecurityMonitor {
    constructor() {
        this.updateInterval = 60000; // 1 минута вместо 30 секунд
        this.lastUpdate = 0;
        this.isUpdating = false;
        this.init();
    }

    init() {
        this.loadSecurityStatus();
        this.setupEventListeners();
        this.startAutoUpdate();
    }

    setupEventListeners() {
        // Кнопки управления IP
        document.getElementById('ban-ip-btn').addEventListener('click', () => this.banIP());
        document.getElementById('unban-ip-btn').addEventListener('click', () => this.unbanIP());
        
        // Кнопка экспорта
        document.getElementById('export-btn').addEventListener('click', () => this.exportData());
    }

    async loadSecurityStatus() {
        if (this.isUpdating) return;
        
        try {
            this.isUpdating = true;
            const response = await fetch('/security/status');
            
            if (response.status === 401) {
                // Пользователь не аутентифицирован, перенаправляем на страницу входа
                window.location.href = '/auth/login';
                return;
            }
            
            if (!response.ok) throw new Error('Ошибка загрузки статуса');
            
            const data = await response.json();
            this.updateStatusCards(data);
            this.updateStatistics(data);
            this.lastUpdate = Date.now();
        } catch (error) {
            console.error('Ошибка загрузки статуса безопасности:', error);
        } finally {
            this.isUpdating = false;
        }
    }

    updateStatusCards(data) {
        // Общий статус
        const overallStatus = document.getElementById('overall-status');
        const riskLevel = data.overall_risk_level || 'UNKNOWN';
        overallStatus.textContent = `Уровень риска: ${this.getRiskLevelText(riskLevel)}`;
        overallStatus.className = `status-value ${this.getRiskClass(riskLevel)}`;

        // Rate Limiting
        const rateLimitStatus = document.getElementById('rate-limit-status');
        const rateLimitStats = data.rate_limiting?.statistics || {};
        rateLimitStatus.textContent = `Активно | ${rateLimitStats.blocked_ips_count || 0} заблокированных IP`;

        // DDoS Защита
        const ddosStatus = document.getElementById('ddos-status');
        const ddosStats = data.ddos_protection?.statistics || {};
        ddosStatus.textContent = `Активно | ${ddosStats.blocked_ips_count || 0} заблокированных IP`;

        // Мониторинг
        const monitoringStatus = document.getElementById('monitoring-status');
        const monitoringStats = data.security_monitoring?.statistics || {};
        monitoringStatus.textContent = `Активно | ${monitoringStats.total_events || 0} событий`;
    }

    updateStatistics(data) {
        const stats = data.security_monitoring?.statistics || {};
        
        // Обновляем статистику
        document.getElementById('total-events').textContent = stats.total_events || 0;
        document.getElementById('blocked-ips').textContent = stats.blocked_ips || 0;
        document.getElementById('high-risk-events').textContent = stats.high_risk_events || 0;
        document.getElementById('critical-events').textContent = stats.critical_events || 0;
    }

    getRiskLevelText(level) {
        const levels = {
            'SAFE': 'Безопасно',
            'LOW': 'Низкий',
            'MEDIUM': 'Средний',
            'HIGH': 'Высокий',
            'CRITICAL': 'Критический'
        };
        return levels[level] || 'Неизвестно';
    }

    getRiskClass(level) {
        const classes = {
            'SAFE': 'safe',
            'LOW': 'safe',
            'MEDIUM': 'warning',
            'HIGH': 'warning',
            'CRITICAL': 'danger'
        };
        return classes[level] || '';
    }

    async loadAlerts() {
        try {
            const response = await fetch('/security/alerts?limit=5'); // Уменьшил лимит
            
            if (response.status === 401) {
                // Пользователь не аутентифицирован, перенаправляем на страницу входа
                window.location.href = '/auth/login';
                return;
            }
            
            if (!response.ok) throw new Error('Ошибка загрузки алертов');
            
            const data = await response.json();
            this.updateAlerts(data.alerts || []);
        } catch (error) {
            console.error('Ошибка загрузки алертов:', error);
            document.getElementById('alerts-container').innerHTML = 
                '<div class="empty-message">Ошибка загрузки алертов</div>';
        }
    }

    updateAlerts(alerts) {
        const container = document.getElementById('alerts-container');
        
        if (alerts.length === 0) {
            container.innerHTML = '<div class="empty-message">Нет активных алертов</div>';
            return;
        }

        const alertsHTML = alerts.map(alert => `
            <div class="alert-item">
                <div class="alert-header">
                    <span class="alert-level ${alert.level.toLowerCase()}">${alert.level}</span>
                    <span class="alert-time">${this.formatTime(alert.timestamp)}</span>
                </div>
                <div class="alert-message">${alert.message}</div>
                <div class="alert-details">
                    IP: ${alert.ip} | Событий: ${alert.events_count}
                </div>
            </div>
        `).join('');

        container.innerHTML = alertsHTML;
    }

    formatTime(timestamp) {
        const date = new Date(timestamp);
        return date.toLocaleString('ru-RU', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    async banIP() {
        const ip = document.getElementById('ip-input').value.trim();
        const duration = parseInt(document.getElementById('ban-duration').value) || 3600;
        
        if (!ip) {
            this.showIPResult('Введите IP адрес', 'error');
            return;
        }

        try {
            const response = await fetch(`/security/ban/${ip}?duration=${duration}`, {
                method: 'POST'
            });
            
            if (response.status === 401) {
                window.location.href = '/auth/login';
                return;
            }
            
            const data = await response.json();
            
            if (response.ok) {
                this.showIPResult(data.message, 'success');
                document.getElementById('ip-input').value = '';
                this.loadSecurityStatus();
            } else {
                this.showIPResult(data.detail || 'Ошибка блокировки', 'error');
            }
        } catch (error) {
            console.error('Ошибка блокировки IP:', error);
            this.showIPResult('Ошибка сети', 'error');
        }
    }

    async unbanIP() {
        const ip = document.getElementById('ip-input').value.trim();
        
        if (!ip) {
            this.showIPResult('Введите IP адрес', 'error');
            return;
        }

        try {
            const response = await fetch(`/security/unban/${ip}`, {
                method: 'POST'
            });
            
            if (response.status === 401) {
                window.location.href = '/auth/login';
                return;
            }
            
            const data = await response.json();
            
            if (response.ok) {
                this.showIPResult(data.message, 'success');
                document.getElementById('ip-input').value = '';
                this.loadSecurityStatus();
            } else {
                this.showIPResult(data.detail || 'Ошибка разблокировки', 'error');
            }
        } catch (error) {
            console.error('Ошибка разблокировки IP:', error);
            this.showIPResult('Ошибка сети', 'error');
        }
    }

    showIPResult(message, type) {
        const resultDiv = document.getElementById('ip-result');
        resultDiv.textContent = message;
        resultDiv.className = `ip-result ${type}`;
        
        // Автоматически скрываем через 5 секунд
        setTimeout(() => {
            resultDiv.textContent = '';
            resultDiv.className = 'ip-result';
        }, 5000);
    }

    async exportData() {
        try {
            const response = await fetch('/security/export?format_type=json');
            
            if (response.status === 401) {
                window.location.href = '/auth/login';
                return;
            }
            
            if (!response.ok) throw new Error('Ошибка экспорта');
            
            const data = await response.json();
            const exportResult = document.getElementById('export-result');
            
            // Форматируем JSON для отображения
            const formattedData = JSON.stringify(JSON.parse(data.export_data), null, 2);
            exportResult.textContent = formattedData;
            
            // Добавляем кнопку скачивания
            const downloadBtn = document.createElement('button');
            downloadBtn.textContent = 'Скачать JSON';
            downloadBtn.className = 'control-btn refresh';
            downloadBtn.style.marginTop = '10px';
            downloadBtn.onclick = () => this.downloadJSON(formattedData);
            
            exportResult.appendChild(downloadBtn);
            
        } catch (error) {
            console.error('Ошибка экспорта:', error);
            document.getElementById('export-result').textContent = 'Ошибка экспорта данных';
        }
    }



    downloadJSON(data) {
        const blob = new Blob([data], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `security_export_${new Date().toISOString().split('T')[0]}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    startAutoUpdate() {
        setInterval(() => {
            // Обновляем только если прошло достаточно времени
            if (Date.now() - this.lastUpdate > this.updateInterval) {
                this.loadSecurityStatus();
                this.loadAlerts();
            }
        }, this.updateInterval);
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    new SecurityMonitor();
}); 