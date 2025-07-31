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
    "alert_threshold": 10,  # количество подозрительных запросов для алерта
    "critical_threshold": 50,  # количество для критического алерта
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
            
            if len(ip_events) >= MONITORING_CONFIG["critical_threshold"]:
                self._create_alert("CRITICAL", event.ip, ip_events, "Критическая активность")
            elif len(ip_events) >= MONITORING_CONFIG["alert_threshold"]:
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
            return self.alerts[-limit:]
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


# Глобальный экземпляр мониторинга
security_monitor = SecurityMonitor()


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
        # Пропускаем статические файлы
        if request.url.path.startswith("/static/"):
            return await call_next(request)
        
        # Пропускаем страницу безопасности (но не API эндпоинты)
        if request.url.path == "/security":
            return await call_next(request)
        
        # Запускаем задачу очистки если не запущена
        if security_monitor._cleanup_task is None or security_monitor._cleanup_task.done():
            await security_monitor.start_cleanup_task()
        
        # Обрабатываем запрос
        response = await call_next(request)
        
        # Логируем подозрительные ответы
        if response.status_code >= 400:
            log_security_event(
                "UNAUTHORIZED_ACCESS",
                request,
                {"status_code": response.status_code},
                risk_score=20
            )
        
        return response
        
    except Exception as e:
        logger.error(f"Ошибка в security monitoring middleware: {e}")
        return await call_next(request) 