"""
Модуль мониторинга безопасности
"""
import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import Request

logger = logging.getLogger(__name__)

# Настройки мониторинга
MONITORING_CONFIG = {
    "alert_threshold": 5,  # количество подозрительных запросов для алерта (уменьшил)
    "critical_threshold": 20,  # количество для критического алерта (уменьшил)
    "time_window": 300,  # 5 минут
    "cleanup_interval": 3600,  # 1 час
    "max_log_entries": 10000,  # максимальное количество записей в логе
}

# Типы событий безопасности
SECURITY_EVENTS = {
    "RATE_LIMIT_EXCEEDED": "Превышен лимит запросов",
    "IP_BANNED": "IP адрес заблокирован",
    "SUSPICIOUS_USER_AGENT": "Подозрительный User-Agent",
    "SUSPICIOUS_HEADERS": "Подозрительные заголовки",
    "SUSPICIOUS_PARAMS": "Подозрительные параметры",
    "SUSPICIOUS_PATH": "Подозрительный путь",
    "HIGH_RISK_REQUEST": "Высокий риск запроса",
    "BRUTE_FORCE_ATTEMPT": "Попытка брутфорса",
    "SQL_INJECTION_ATTEMPT": "Попытка SQL инъекции",
    "XSS_ATTEMPT": "Попытка XSS атаки",
    "PATH_TRAVERSAL_ATTEMPT": "Попытка path traversal",
    "COMMAND_INJECTION_ATTEMPT": "Попытка command injection",
    "FILE_UPLOAD_ATTEMPT": "Попытка загрузки файла",
    "UNAUTHORIZED_ACCESS": "Неавторизованный доступ",
    "PRIVILEGE_ESCALATION": "Попытка повышения привилегий",
}


class SecurityEvent:
    """Класс для представления события безопасности"""
    
    def __init__(self, event_type: str, ip: str, details: Dict, risk_score: int = 0):
        self.event_type = event_type
        self.ip = ip
        self.details = details
        self.risk_score = risk_score
        self.timestamp = datetime.utcnow()
        self.id = f"{int(time.time())}_{ip}_{event_type}"
    
    def to_dict(self) -> Dict:
        """Преобразование в словарь"""
        return {
            "id": self.id,
            "event_type": self.event_type,
            "ip": self.ip,
            "details": self.details,
            "risk_score": self.risk_score,
            "timestamp": self.timestamp.isoformat(),
            "description": SECURITY_EVENTS.get(self.event_type, "Неизвестное событие")
        }
    
    def __str__(self) -> str:
        return f"[{self.timestamp}] {self.event_type} - IP: {self.ip}, Risk: {self.risk_score}"


class SecurityMonitor:
    """Класс для мониторинга безопасности"""
    
    def __init__(self):
        self.events: List[SecurityEvent] = []
        self.ip_activity: Dict[str, List[SecurityEvent]] = {}
        self.alerts: List[Dict] = []
        self.statistics: Dict = {
            "total_events": 0,
            "blocked_ips": 0,
            "high_risk_events": 0,
            "critical_events": 0,
            "last_cleanup": datetime.utcnow()
        }
        self._cleanup_task: Optional[asyncio.Task] = None
    
    def add_event(self, event: SecurityEvent) -> None:
        """Добавление события безопасности"""
        try:
            # Добавляем событие в общий список
            self.events.append(event)
            self.statistics["total_events"] += 1
            
            # Добавляем в активность по IP
            if event.ip not in self.ip_activity:
                self.ip_activity[event.ip] = []
            self.ip_activity[event.ip].append(event)
            
            # Обновляем статистику
            if event.risk_score >= 80:
                self.statistics["critical_events"] += 1
            elif event.risk_score >= 50:
                self.statistics["high_risk_events"] += 1
            
            # Проверяем необходимость алерта
            self._check_alerts(event)
            
            # Логируем событие
            logger.warning(f"🔒 Событие безопасности: {event}")
            
            # Ограничиваем размер лога
            if len(self.events) > MONITORING_CONFIG["max_log_entries"]:
                self._cleanup_old_events()
                
        except Exception as e:
            logger.error(f"Ошибка добавления события безопасности: {e}")
    
    def _check_alerts(self, event: SecurityEvent) -> None:
        """Проверка необходимости создания алерта"""
        try:
            current_time = datetime.utcnow()
            time_window = current_time - timedelta(seconds=MONITORING_CONFIG["time_window"])
            
            # Подсчитываем события для IP в окне времени
            ip_events = [
                e for e in self.ip_activity.get(event.ip, [])
                if e.timestamp >= time_window
            ]
            
            logger.info(f"🔍 Проверка алертов для IP {event.ip}: событий={len(ip_events)}, порог={MONITORING_CONFIG['alert_threshold']}, критический={MONITORING_CONFIG['critical_threshold']}")
            
            if len(ip_events) >= MONITORING_CONFIG["critical_threshold"]:
                logger.info(f"🚨 Создаем КРИТИЧЕСКИЙ алерт для IP {event.ip}")
                self._create_alert("CRITICAL", event.ip, ip_events, "Критическая активность")
            elif len(ip_events) >= MONITORING_CONFIG["alert_threshold"]:
                logger.info(f"⚠️ Создаем WARNING алерт для IP {event.ip}")
                self._create_alert("WARNING", event.ip, ip_events, "Подозрительная активность")
                
        except Exception as e:
            logger.error(f"Ошибка проверки алертов: {e}")
    
    def _create_alert(self, level: str, ip: str, events: List[SecurityEvent], message: str) -> None:
        """Создание алерта"""
        try:
            alert = {
                "id": f"alert_{int(time.time())}_{ip}",
                "level": level,
                "ip": ip,
                "message": message,
                "events_count": len(events),
                "timestamp": datetime.utcnow().isoformat(),
                "events": [event.to_dict() for event in events[-10:]]  # Последние 10 событий
            }
            
            self.alerts.append(alert)
            logger.info(f"✅ Алерт создан: {level} для IP {ip}, всего алертов: {len(self.alerts)}")
            
            # Логируем алерт
            if level == "CRITICAL":
                logger.critical(f"🚨 КРИТИЧЕСКИЙ АЛЕРТ: {message} - IP: {ip}, Событий: {len(events)}")
            else:
                logger.warning(f"⚠️ АЛЕРТ: {message} - IP: {ip}, Событий: {len(events)}")
                
        except Exception as e:
            logger.error(f"Ошибка создания алерта: {e}")
    
    def _cleanup_old_events(self) -> None:
        """Очистка старых событий"""
        try:
            current_time = datetime.utcnow()
            cutoff_time = current_time - timedelta(seconds=MONITORING_CONFIG["time_window"])
            
            # Очищаем общий список событий
            self.events = [
                event for event in self.events
                if event.timestamp >= cutoff_time
            ]
            
            # Очищаем активность по IP
            for ip in list(self.ip_activity.keys()):
                self.ip_activity[ip] = [
                    event for event in self.ip_activity[ip]
                    if event.timestamp >= cutoff_time
                ]
                
                # Удаляем пустые записи
                if not self.ip_activity[ip]:
                    del self.ip_activity[ip]
            
            # Очищаем старые алерты
            alert_cutoff = current_time - timedelta(hours=24)
            self.alerts = [
                alert for alert in self.alerts
                if datetime.fromisoformat(alert["timestamp"]) >= alert_cutoff
            ]
            
            self.statistics["last_cleanup"] = current_time
            logger.info(f"🧹 Очистка завершена. Осталось событий: {len(self.events)}")
            
        except Exception as e:
            logger.error(f"Ошибка очистки старых событий: {e}")
    
    async def start_cleanup_task(self) -> None:
        """Запуск задачи периодической очистки"""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def _cleanup_loop(self) -> None:
        """Цикл периодической очистки"""
        while True:
            try:
                await asyncio.sleep(MONITORING_CONFIG["cleanup_interval"])
                self._cleanup_old_events()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка в цикле очистки: {e}")
    
    def get_statistics(self) -> Dict:
        """Получение статистики мониторинга"""
        try:
            current_time = datetime.utcnow()
            time_window = current_time - timedelta(seconds=MONITORING_CONFIG["time_window"])
            
            # События за последнее время
            recent_events = [
                event for event in self.events
                if event.timestamp >= time_window
            ]
            
            # Активные IP
            active_ips = len(self.ip_activity)
            
            # Топ подозрительных IP
            ip_risk_scores = {}
            for ip, events in self.ip_activity.items():
                recent_ip_events = [
                    event for event in events
                    if event.timestamp >= time_window
                ]
                if recent_ip_events:
                    ip_risk_scores[ip] = sum(event.risk_score for event in recent_ip_events)
            
            top_suspicious_ips = sorted(
                ip_risk_scores.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
            
            return {
                "total_events": self.statistics["total_events"],
                "recent_events_count": len(recent_events),
                "active_ips": active_ips,
                "high_risk_events": self.statistics["high_risk_events"],
                "critical_events": self.statistics["critical_events"],
                "alerts_count": len(self.alerts),
                "top_suspicious_ips": top_suspicious_ips,
                "last_cleanup": self.statistics["last_cleanup"].isoformat(),
                "monitoring_window": MONITORING_CONFIG["time_window"]
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return {}
    
    def get_events_for_ip(self, ip: str, limit: int = 100) -> List[Dict]:
        """Получение событий для конкретного IP"""
        try:
            events = self.ip_activity.get(ip, [])
            return [event.to_dict() for event in events[-limit:]]
        except Exception as e:
            logger.error(f"Ошибка получения событий для IP {ip}: {e}")
            return []
    
    def get_recent_alerts(self, limit: int = 50) -> List[Dict]:
        """Получение последних алертов"""
        try:
            logger.info(f"🔍 Запрос алертов: всего алертов={len(self.alerts)}, запрошено={limit}")
            alerts = self.alerts[-limit:]
            logger.info(f"🔍 Возвращаем {len(alerts)} алертов")
            
            # Убеждаемся, что возвращаем правильный формат
            formatted_alerts = []
            for alert in alerts:
                formatted_alert = {
                    "id": alert.get("id", "unknown"),
                    "level": alert.get("level", "INFO"),
                    "ip": alert.get("ip", "unknown"),
                    "message": alert.get("message", "Событие безопасности"),
                    "events_count": alert.get("events_count", 0),
                    "timestamp": alert.get("timestamp", datetime.utcnow().isoformat()),
                    "events": alert.get("events", [])
                }
                formatted_alerts.append(formatted_alert)
            
            logger.info(f"🔍 Отформатировано {len(formatted_alerts)} алертов")
            return formatted_alerts
        except Exception as e:
            logger.error(f"Ошибка получения алертов: {e}")
            return []
    
    def export_events(self, format_type: str = "json") -> str:
        """Экспорт событий"""
        try:
            if format_type == "json":
                return json.dumps({
                    "events": [event.to_dict() for event in self.events],
                    "alerts": self.alerts,
                    "statistics": self.get_statistics(),
                    "export_time": datetime.utcnow().isoformat()
                }, indent=2, ensure_ascii=False)
            else:
                raise ValueError(f"Неподдерживаемый формат: {format_type}")
        except Exception as e:
            logger.error(f"Ошибка экспорта событий: {e}")
            return ""
    
    def clear_all_events(self) -> None:
        """Очистка всех событий безопасности"""
        try:
            old_count = len(self.events)
            self.events.clear()
            self.alerts.clear()
            logger.info(f"✅ Очищено {old_count} событий безопасности")
        except Exception as e:
            logger.error(f"Ошибка очистки событий: {e}")
    
    def clear_all_alerts(self) -> None:
        """Очистка всех алертов"""
        try:
            old_count = len(self.alerts)
            self.alerts.clear()
            logger.info(f"✅ Очищено {old_count} алертов")
        except Exception as e:
            logger.error(f"Ошибка очистки алертов: {e}")
    
    def create_demo_alerts(self) -> None:
        """Создание демонстрационных алертов"""
        try:
            # Создаем тестовые алерты для демонстрации
            demo_alerts = [
                {
                    "id": f"demo_alert_{int(time.time())}_1",
                    "level": "CRITICAL",
                    "ip": "192.168.1.100",
                    "message": "Критическая активность - множественные попытки брутфорса",
                    "events_count": 10,
                    "timestamp": datetime.utcnow().isoformat(),
                    "events": [
                        {
                            "event_type": "BRUTEFORCE_ATTEMPT",
                            "ip": "192.168.1.100",
                            "risk_score": 50,
                            "timestamp": datetime.utcnow().isoformat(),
                            "details": {"attempts": 15}
                        }
                    ]
                },
                {
                    "id": f"demo_alert_{int(time.time())}_2",
                    "level": "WARNING",
                    "ip": "10.0.0.50",
                    "message": "Подозрительная активность - попытка SQL инъекции",
                    "events_count": 3,
                    "timestamp": datetime.utcnow().isoformat(),
                    "events": [
                        {
                            "event_type": "SQL_INJECTION",
                            "ip": "10.0.0.50",
                            "risk_score": 60,
                            "timestamp": datetime.utcnow().isoformat(),
                            "details": {"query": "SELECT * FROM users"}
                        }
                    ]
                },
                {
                    "id": f"demo_alert_{int(time.time())}_3",
                    "level": "WARNING",
                    "ip": "172.16.0.25",
                    "message": "Подозрительная активность - попытка XSS атаки",
                    "events_count": 2,
                    "timestamp": datetime.utcnow().isoformat(),
                    "events": [
                        {
                            "event_type": "XSS_ATTEMPT",
                            "ip": "172.16.0.25",
                            "risk_score": 45,
                            "timestamp": datetime.utcnow().isoformat(),
                            "details": {"payload": "<script>"}
                        }
                    ]
                }
            ]
            
            self.alerts.extend(demo_alerts)
            logger.info(f"✅ Создано {len(demo_alerts)} демонстрационных алертов")
        except Exception as e:
            logger.error(f"Ошибка создания демонстрационных алертов: {e}")


# Глобальный экземпляр мониторинга
security_monitor = SecurityMonitor()

# Создаем несколько тестовых алертов для демонстрации
def create_test_alerts():
    """Создание тестовых алертов для демонстрации"""
    try:
        # Создаем тестовые события только если их нет
        if len(security_monitor.events) == 0:
            # Создаем события для одного IP, чтобы сгенерировать алерт
            malicious_ip = "192.168.1.100"
            test_events = [
                SecurityEvent("BRUTEFORCE_ATTEMPT", malicious_ip, {"attempts": 15}, 50),
                SecurityEvent("BRUTEFORCE_ATTEMPT", malicious_ip, {"attempts": 16}, 50),
                SecurityEvent("BRUTEFORCE_ATTEMPT", malicious_ip, {"attempts": 17}, 50),
                SecurityEvent("BRUTEFORCE_ATTEMPT", malicious_ip, {"attempts": 18}, 50),
                SecurityEvent("BRUTEFORCE_ATTEMPT", malicious_ip, {"attempts": 19}, 50),
                SecurityEvent("BRUTEFORCE_ATTEMPT", malicious_ip, {"attempts": 20}, 50),
                SecurityEvent("BRUTEFORCE_ATTEMPT", malicious_ip, {"attempts": 21}, 50),
                SecurityEvent("BRUTEFORCE_ATTEMPT", malicious_ip, {"attempts": 22}, 50),
                SecurityEvent("BRUTEFORCE_ATTEMPT", malicious_ip, {"attempts": 23}, 50),
                SecurityEvent("BRUTEFORCE_ATTEMPT", malicious_ip, {"attempts": 24}, 50),
                # Дополнительные события от других IP
                SecurityEvent("SQL_INJECTION", "10.0.0.50", {"query": "SELECT * FROM users"}, 60),
                SecurityEvent("XSS_ATTEMPT", "172.16.0.25", {"payload": "<script>"}, 45),
                SecurityEvent("UNAUTHORIZED_ACCESS", "203.0.113.10", {"path": "/admin"}, 30),
                SecurityEvent("RATE_LIMIT_EXCEEDED", "198.51.100.5", {"requests": 100}, 35)
            ]
            
            for event in test_events:
                security_monitor.add_event(event)
            
            logger.info(f"✅ Создано {len(test_events)} тестовых событий безопасности")
        else:
            logger.info(f"Тестовые события уже существуют: {len(security_monitor.events)} событий")
    except Exception as e:
        logger.error(f"Ошибка создания тестовых алертов: {e}")


def log_security_event(event_type: str, request: Request, details: Dict, risk_score: int = 0) -> None:
    """Логирование события безопасности"""
    try:
        # Получаем IP адреса
        client_ip = request.client.host if request.client else "unknown"
        
        # Проверяем заголовки для реального IP
        for header in ["X-Real-IP", "X-Client-IP", "X-Forwarded-For"]:
            if header in request.headers:
                ip = request.headers[header].split(",")[0].strip()
                if ip and ip != "unknown":
                    client_ip = ip
                    break
        
        # Создаем событие
        event = SecurityEvent(
            event_type=event_type,
            ip=client_ip,
            details={
                "path": request.url.path,
                "method": request.method,
                "user_agent": request.headers.get("User-Agent", ""),
                "referer": request.headers.get("Referer", ""),
                "query_params": dict(request.query_params),
                **details
            },
            risk_score=risk_score
        )
        
        # Добавляем в мониторинг
        security_monitor.add_event(event)
        
    except Exception as e:
        logger.error(f"Ошибка логирования события безопасности: {e}")


async def security_monitoring_middleware(request: Request, call_next):
    """Middleware для мониторинга безопасности"""
    try:
        # Пропускаем статические файлы и ресурсы браузера
        if (request.url.path.startswith("/static/") or 
            request.url.path.startswith("/.well-known/") or
            request.url.path == "/favicon.ico" or
            request.url.path == "/robots.txt"):
            return await call_next(request)
        
        # Пропускаем страницу безопасности (но не API эндпоинты)
        if request.url.path == "/security":
            return await call_next(request)
        
        # Запускаем задачу очистки если не запущена
        if security_monitor._cleanup_task is None or security_monitor._cleanup_task.done():
            await security_monitor.start_cleanup_task()
        
        # Обрабатываем запрос
        response = await call_next(request)
        
        # Логируем только реальные проблемы безопасности
        if response.status_code == 401:  # Неавторизованный доступ
            log_security_event(
                "UNAUTHORIZED_ACCESS",
                request,
                {"status_code": response.status_code, "path": request.url.path},
                risk_score=30
            )
        elif response.status_code == 403:  # Запрещенный доступ
            log_security_event(
                "FORBIDDEN_ACCESS",
                request,
                {"status_code": response.status_code, "path": request.url.path},
                risk_score=40
            )
        elif response.status_code == 429:  # Rate limit exceeded
            log_security_event(
                "RATE_LIMIT_EXCEEDED",
                request,
                {"status_code": response.status_code, "path": request.url.path},
                risk_score=25
            )
        # НЕ логируем 404, 500 и другие ошибки как события безопасности
        
        return response
        
    except Exception as e:
        logger.error(f"Ошибка в security monitoring middleware: {e}")
        return await call_next(request) 