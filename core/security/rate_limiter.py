"""
Модуль защиты от DDoS атак с rate limiting
"""
import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List

import redis
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# Настройки rate limiting
RATE_LIMIT_CONFIG = {
    "default": {
        "requests_per_minute": 60,
        "burst_limit": 10,
        "window_size": 60,  # секунды
    },
    "auth": {
        "requests_per_minute": 5,
        "burst_limit": 2,
        "window_size": 60,
    },
    "api": {
        "requests_per_minute": 30,
        "burst_limit": 5,
        "window_size": 60,
    },
    "parser": {
        "requests_per_minute": 5,
        "burst_limit": 2,
        "window_size": 60,
    },
}

# Настройки блокировки IP
IP_BAN_CONFIG = {
    "max_violations": 3,  # Уменьшили с 5 до 3
    "ban_duration": 3600,  # 1 час
    "violation_window": 300,  # 5 минут
}

# Настройки мониторинга
MONITORING_CONFIG = {
    "suspicious_threshold": 100,  # запросов в минуту
    "alert_threshold": 500,  # запросов в минуту
    "monitoring_window": 60,  # секунды
}


class RateLimiter:
    """Класс для управления rate limiting"""
    
    def __init__(self, host: str = 'localhost', port: int = 6379, db: int = 1):
        """Инициализация Redis клиента для rate limiting"""
        self.redis_client = redis.Redis(
            host=host,
            port=port,
            db=db,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )
        self._cache: Dict[str, Dict] = {}
        self._ban_list: Dict[str, float] = {}
    
    def _test_connection(self) -> bool:
        """Проверка подключения к Redis"""
        try:
            self.redis_client.ping()
            return True
        except Exception:
            return False
    
    def _get_client_identifier(self, request: Request) -> str:
        """Получение идентификатора клиента"""
        # Приоритет заголовков для определения реального IP
        headers_to_check = [
            "X-Real-IP",
            "X-Client-IP", 
            "X-Forwarded-For",
            "CF-Connecting-IP",  # Cloudflare
            "X-Forwarded",
            "Forwarded-For",
            "Forwarded"
        ]
        
        for header in headers_to_check:
            if header in request.headers:
                ip = request.headers[header].split(",")[0].strip()
                if ip and ip != "unknown":
                    return f"{ip}:{request.headers.get('User-Agent', 'unknown')}"
        
        # Fallback на client.host
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("User-Agent", "unknown")
        return f"{client_ip}:{user_agent}"
    
    def _is_authenticated_user(self, request: Request) -> bool:
        """Проверка авторизации пользователя"""
        try:
            # Проверяем наличие сессионного токена
            session_token = request.cookies.get("session_token")
            if not session_token:
                return False
            
            # Проверяем JWT токен в заголовках
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                return True
            
            # Проверяем, есть ли пользователь в request.state (для декораторов)
            if hasattr(request.state, 'user') and request.state.user:
                return True
            
            return False
        except Exception:
            return False
    
    def _get_rate_limit_config(self, path: str) -> Dict:
        """Получение конфигурации rate limit для пути"""
        # Исключаем статические файлы и страницу безопасности
        if path.startswith("/static/") or path.startswith("/security"):
            return {"requests_per_minute": 1000, "burst_limit": 100, "window_size": 60}
        
        # Исключаем API эндпоинты безопасности для авторизованных пользователей
        if path.startswith("/security/status") or path.startswith("/security/alerts"):
            return {"requests_per_minute": 1000, "burst_limit": 100, "window_size": 60}
        
        if path.startswith("/auth/"):
            return RATE_LIMIT_CONFIG["auth"]
        elif path.startswith("/process_audatex_requests"):
            return RATE_LIMIT_CONFIG["parser"]
        elif path.startswith("/api/"):
            return RATE_LIMIT_CONFIG["api"]
        else:
            return RATE_LIMIT_CONFIG["default"]
    
    def _is_auth_attack(self, request: Request) -> bool:
        """Определение атаки на аутентификацию"""
        path = request.url.path
        
        # Проверяем только auth эндпоинты
        if not path.startswith("/auth/"):
            return False
        
        # Проверяем метод POST (попытки входа)
        if request.method != "POST":
            return False
        
        # Проверяем наличие данных для входа в заголовках
        content_type = request.headers.get("content-type", "")
        
        # Для form data
        if "application/x-www-form-urlencoded" in content_type:
            return True
        
        # Для JSON
        if "application/json" in content_type:
            return True
        
        return False
    
    async def _get_request_count(self, key: str, window: int) -> int:
        """Получение количества запросов из Redis"""
        try:
            if self._test_connection():
                current_time = int(time.time())
                window_start = current_time - window
                
                # Используем Redis для хранения запросов
                redis_key = f"rate_limit:{key}:{window_start}"
                count = self.redis_client.get(redis_key)
                return int(count) if count else 0
            else:
                # Fallback на локальный кеш
                return self._cache.get(key, {}).get("count", 0)
        except Exception as e:
            logger.error(f"Ошибка получения количества запросов: {e}")
            return 0
    
    async def _increment_request_count(self, key: str, window: int) -> int:
        """Увеличение счетчика запросов"""
        try:
            if self._test_connection():
                current_time = int(time.time())
                window_start = current_time - window
                
                redis_key = f"rate_limit:{key}:{window_start}"
                count = self.redis_client.incr(redis_key)
                self.redis_client.expire(redis_key, window + 10)  # TTL
                return count
            else:
                # Fallback на локальный кеш
                if key not in self._cache:
                    self._cache[key] = {"count": 0, "window_start": window}
                
                self._cache[key]["count"] += 1
                return self._cache[key]["count"]
        except Exception as e:
            logger.error(f"Ошибка увеличения счетчика запросов: {e}")
            return 1
    
    async def _check_ip_banned(self, client_id: str) -> bool:
        """Проверка блокировки IP"""
        try:
            ip = client_id.split(":")[0]
            
            if self._test_connection():
                ban_key = f"ip_ban:{ip}"
                banned_until = self.redis_client.get(ban_key)
                if banned_until:
                    ban_time = float(banned_until)
                    if time.time() < ban_time:
                        return True
                    else:
                        # Удаляем истекший бан
                        self.redis_client.delete(ban_key)
            else:
                # Fallback на локальный кеш
                if ip in self._ban_list:
                    if time.time() < self._ban_list[ip]:
                        return True
                    else:
                        del self._ban_list[ip]
            
            return False
        except Exception as e:
            logger.error(f"Ошибка проверки блокировки IP: {e}")
            return False
    
    async def _ban_ip(self, client_id: str, duration: int) -> None:
        """Блокировка IP адреса"""
        try:
            ip = client_id.split(":")[0]
            ban_until = time.time() + duration
            
            if self._test_connection():
                ban_key = f"ip_ban:{ip}"
                self.redis_client.set(ban_key, str(ban_until), ex=duration + 60)
            else:
                self._ban_list[ip] = ban_until
            
            logger.warning(f"IP заблокирован: {ip} до {datetime.fromtimestamp(ban_until)}")
        except Exception as e:
            logger.error(f"Ошибка блокировки IP: {e}")
    
    async def _record_violation(self, client_id: str) -> int:
        """Запись нарушения rate limit"""
        try:
            ip = client_id.split(":")[0]
            current_time = time.time()
            
            if self._test_connection():
                violation_key = f"violations:{ip}"
                violations = self.redis_client.lrange(violation_key, 0, -1)
                
                # Удаляем старые нарушения
                recent_violations = [
                    v for v in violations 
                    if current_time - float(v) < IP_BAN_CONFIG["violation_window"]
                ]
                
                # Добавляем новое нарушение
                recent_violations.append(str(current_time))
                
                # Обновляем список нарушений
                self.redis_client.delete(violation_key)
                if recent_violations:
                    self.redis_client.lpush(violation_key, *recent_violations)
                    self.redis_client.expire(violation_key, IP_BAN_CONFIG["violation_window"] + 60)
                
                violation_count = len(recent_violations)
            else:
                # Fallback на локальный кеш
                violation_count = 1  # Упрощенная логика для локального кеша
            
            return violation_count
        except Exception as e:
            logger.error(f"Ошибка записи нарушения: {e}")
            return 1
    
    async def _monitor_suspicious_activity(self, client_id: str, request_count: int) -> None:
        """Мониторинг подозрительной активности"""
        try:
            ip = client_id.split(":")[0]
            
            if request_count >= MONITORING_CONFIG["alert_threshold"]:
                logger.critical(f"🚨 КРИТИЧЕСКАЯ АКТИВНОСТЬ: IP {ip} - {request_count} запросов в минуту")
                # Здесь можно добавить отправку уведомлений
            elif request_count >= MONITORING_CONFIG["suspicious_threshold"]:
                logger.warning(f"⚠️ ПОДОЗРИТЕЛЬНАЯ АКТИВНОСТЬ: IP {ip} - {request_count} запросов в минуту")
        except Exception as e:
            logger.error(f"Ошибка мониторинга активности: {e}")
    
    async def check_rate_limit(self, request: Request) -> Tuple[bool, Optional[str]]:
        """
        Проверка rate limit для запроса
        
        Returns:
            Tuple[bool, Optional[str]]: (разрешено, сообщение об ошибке)
        """
        try:
            client_id = self._get_client_identifier(request)
            path = request.url.path
            config = self._get_rate_limit_config(path)
            
            # Проверяем авторизацию пользователя
            is_authenticated = self._is_authenticated_user(request)
            
            # Проверяем, является ли это атакой на аутентификацию
            is_auth_attack = self._is_auth_attack(request)
            
            # Если пользователь авторизован, применяем более мягкие лимиты
            if is_authenticated:
                # Для авторизованных пользователей увеличиваем лимиты в 5 раз
                adjusted_config = {
                    "requests_per_minute": config["requests_per_minute"] * 5,
                    "burst_limit": config["burst_limit"] * 3,
                    "window_size": config["window_size"]
                }
                config = adjusted_config
            elif is_auth_attack:
                # Для атак на аутентификацию применяем более строгие лимиты
                adjusted_config = {
                    "requests_per_minute": 3,  # Очень строгий лимит
                    "burst_limit": 1,  # Один запрос за раз
                    "window_size": config["window_size"]
                }
                config = adjusted_config
            
            # Проверяем блокировку IP
            if await self._check_ip_banned(client_id):
                return False, "IP адрес заблокирован за нарушение rate limit"
            
            # Получаем текущее количество запросов
            current_count = await self._get_request_count(client_id, config["window_size"])
            
            # Проверяем burst limit
            if current_count >= config["burst_limit"]:
                # Записываем нарушения только для неавторизованных пользователей
                if not is_authenticated:
                    violations = await self._record_violation(client_id)
                    
                    # Для атак на аутентификацию блокируем быстрее
                    max_violations = 2 if is_auth_attack else IP_BAN_CONFIG["max_violations"]
                    
                    if violations >= max_violations:
                        await self._ban_ip(client_id, IP_BAN_CONFIG["ban_duration"])
                        return False, "IP заблокирован за множественные попытки входа"
                
                return False, f"Превышен лимит запросов. Попробуйте позже."
            
            # Проверяем общий лимит
            if current_count >= config["requests_per_minute"]:
                return False, f"Превышен лимит {config['requests_per_minute']} запросов в минуту"
            
            # Увеличиваем счетчик
            new_count = await self._increment_request_count(client_id, config["window_size"])
            
            # Мониторим подозрительную активность только для неавторизованных
            if not is_authenticated:
                await self._monitor_suspicious_activity(client_id, new_count)
            
            return True, None
            
        except Exception as e:
            logger.error(f"Ошибка проверки rate limit: {e}")
            # В случае ошибки разрешаем запрос
            return True, None
    
    async def get_rate_limit_info(self, request: Request) -> Dict:
        """Получение информации о rate limit для клиента"""
        try:
            client_id = self._get_client_identifier(request)
            path = request.url.path
            config = self._get_rate_limit_config(path)
            
            current_count = await self._get_request_count(client_id, config["window_size"])
            remaining = max(0, config["requests_per_minute"] - current_count)
            
            return {
                "limit": config["requests_per_minute"],
                "remaining": remaining,
                "reset_time": int(time.time()) + config["window_size"],
                "burst_limit": config["burst_limit"]
            }
        except Exception as e:
            logger.error(f"Ошибка получения информации о rate limit: {e}")
            return {}
    
    def get_statistics(self) -> Dict:
        """Получение статистики rate limiting"""
        try:
            return {
                "banned_ips_count": len(self._ban_list),
                "cache_size": len(self._cache),
                "redis_connected": self._test_connection(),
                "banned_ips": list(self._ban_list.keys())
            }
        except Exception as e:
            logger.error(f"Ошибка получения статистики rate limiting: {e}")
            return {}
    
    def unban_ip(self, ip: str) -> bool:
        """Разблокировка IP адреса"""
        try:
            # Удаляем из локального кеша
            if ip in self._ban_list:
                del self._ban_list[ip]
            
            # Удаляем из Redis
            if self._test_connection():
                ban_key = f"ip_ban:{ip}"
                self.redis_client.delete(ban_key)
                
                # Также удаляем нарушения
                violation_key = f"violations:{ip}"
                self.redis_client.delete(violation_key)
                
                # Очищаем rate limit счетчики
                current_time = int(time.time())
                for window in range(0, 3600, 60):  # Очищаем за последний час
                    window_start = current_time - window
                    redis_key = f"rate_limit:{ip}:{window_start}"
                    self.redis_client.delete(redis_key)
            
            logger.info(f"IP {ip} разблокирован")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка разблокировки IP {ip}: {e}")
            return False
    
    def get_banned_ips(self) -> List[str]:
        """Получение списка заблокированных IP"""
        try:
            banned_ips = list(self._ban_list.keys())
            
            # Добавляем из Redis
            if self._test_connection():
                # Ищем все ключи с префиксом ip_ban:
                pattern = "ip_ban:*"
                keys = self.redis_client.keys(pattern)
                for key in keys:
                    ip = key.replace("ip_ban:", "")
                    if ip not in banned_ips:
                        banned_ips.append(ip)
            
            return banned_ips
            
        except Exception as e:
            logger.error(f"Ошибка получения списка заблокированных IP: {e}")
            return list(self._ban_list.keys())


# Глобальный экземпляр rate limiter
rate_limiter = RateLimiter()


async def rate_limit_middleware(request: Request, call_next):
    """Middleware для rate limiting"""
    try:
        # Пропускаем статические файлы
        if request.url.path.startswith("/static/"):
            return await call_next(request)
        
        # Пропускаем страницу безопасности (но не API эндпоинты)
        if request.url.path == "/security":
            return await call_next(request)
        
        # Проверяем rate limit
        allowed, error_message = await rate_limiter.check_rate_limit(request)
        
        if not allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "message": error_message,
                    "retry_after": 60
                },
                headers={
                    "Retry-After": "60",
                    "X-RateLimit-Limit": "60",
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time()) + 60)
                }
            )
        
        # Добавляем информацию о rate limit в заголовки
        response = await call_next(request)
        rate_info = await rate_limiter.get_rate_limit_info(request)
        
        if rate_info:
            response.headers["X-RateLimit-Limit"] = str(rate_info["limit"])
            response.headers["X-RateLimit-Remaining"] = str(rate_info["remaining"])
            response.headers["X-RateLimit-Reset"] = str(rate_info["reset_time"])
        
        return response
        
    except Exception as e:
        logger.error(f"Ошибка в rate limit middleware: {e}")
        # В случае ошибки пропускаем запрос
        return await call_next(request) 