"""
API эндпоинты для мониторинга безопасности
"""
import logging
import time
from typing import Dict, List

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse


from core.security.rate_limiter import rate_limiter
from core.security.ddos_protection import ddos_protection
from core.security.security_monitor import security_monitor, log_security_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/security", tags=["security"])


@router.get("/status")
async def get_security_status(request: Request):
    """Получение статуса безопасности системы"""
    try:
        # Проверяем пользователя из middleware
        user = getattr(request.state, 'user', None)
        if not user:
            # Если пользователь не найден, проверяем сессию напрямую
            token = request.cookies.get("session_token")
            if not token:
                raise HTTPException(status_code=401, detail="Не авторизован")
            
            from core.auth.users import UserManager
            user = await UserManager.validate_session(token)
            if not user:
                raise HTTPException(status_code=401, detail="Недействительная сессия")
        
        # Проверяем права доступа
        if user.role not in ["admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для доступа к информации о безопасности"
            )
        
        # Получаем статистику
        rate_limit_stats = rate_limiter.get_statistics()
        ddos_stats = ddos_protection.get_statistics()
        security_stats = security_monitor.get_statistics()
        
        return JSONResponse({
            "status": "active",
            "rate_limiting": {
                "enabled": True,
                "statistics": rate_limit_stats
            },
            "ddos_protection": {
                "enabled": True,
                "statistics": ddos_stats
            },
            "security_monitoring": {
                "enabled": True,
                "statistics": security_stats
            },
            "overall_risk_level": _calculate_overall_risk(security_stats)
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения статуса безопасности: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера"
        )


@router.get("/events")
async def get_security_events(
    request: Request,
    limit: int = 100
):
    """Получение событий безопасности"""
    try:
        # Пользователь уже проверен в middleware
        user = getattr(request.state, 'user', None)
        if not user:
            raise HTTPException(status_code=401, detail="Не авторизован")
        
        # Проверяем права доступа
        if user.role not in ["admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для доступа к событиям безопасности"
            )
        
        # Ограничиваем лимит
        limit = min(limit, 1000)
        
        # Получаем события
        events = security_monitor.get_recent_alerts(limit)
        
        return JSONResponse({
            "events": events,
            "total_count": len(events),
            "limit": limit
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения событий безопасности: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера"
        )


@router.get("/events/{ip}")
async def get_events_for_ip(
    ip: str,
    request: Request,
    limit: int = 100
):
    """Получение событий безопасности для конкретного IP"""
    try:
        # Пользователь уже проверен в middleware
        user = getattr(request.state, 'user', None)
        if not user:
            raise HTTPException(status_code=401, detail="Не авторизован")
        
        # Проверяем права доступа
        if user.role not in ["admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для доступа к событиям безопасности"
            )
        
        # Ограничиваем лимит
        limit = min(limit, 500)
        
        # Получаем события для IP
        events = security_monitor.get_events_for_ip(ip, limit)
        
        return JSONResponse({
            "ip": ip,
            "events": events,
            "total_count": len(events),
            "limit": limit
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения событий для IP {ip}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера"
        )





@router.post("/ban/{ip}")
async def ban_ip(
    ip: str,
    request: Request,
    duration: int = 3600  # 1 час по умолчанию
):
    """Блокировка IP адреса"""
    try:
        # Пользователь уже проверен в middleware
        user = getattr(request.state, 'user', None)
        if not user:
            raise HTTPException(status_code=401, detail="Не авторизован")
        
        # Проверяем права доступа
        if user.role not in ["admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для блокировки IP"
            )
        
        # Ограничиваем длительность блокировки
        duration = min(duration, 86400)  # максимум 24 часа
        
        # Блокируем IP
        await _ban_ip(ip, duration)
        
        # Логируем событие
        log_security_event(
            "IP_MANUALLY_BANNED",
            request,
            {"banned_ip": ip, "duration": duration, "admin_user": user.username},
            risk_score=0
        )
        
        logger.info(f"IP {ip} заблокирован администратором {user.username} на {duration} секунд")
        
        return JSONResponse({
            "success": True,
            "message": f"IP {ip} заблокирован на {duration} секунд"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка блокировки IP {ip}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера"
        )


@router.get("/rate-limit-info")
async def get_rate_limit_info(request: Request):
    """Получение информации о rate limit для текущего клиента"""
    try:
        # Получаем информацию о rate limit
        rate_info = await rate_limiter.get_rate_limit_info(request)
        
        return JSONResponse({
            "rate_limit_info": rate_info,
            "client_ip": _get_client_ip(request)
        })
        
    except Exception as e:
        logger.error(f"Ошибка получения информации о rate limit: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера"
        )


@router.get("/export")
async def export_security_data(
    request: Request,
    format_type: str = "json"
):
    """Экспорт данных безопасности"""
    try:
        # Пользователь уже проверен в middleware
        user = getattr(request.state, 'user', None)
        if not user:
            raise HTTPException(status_code=401, detail="Не авторизован")
        
        # Проверяем права доступа
        if user.role not in ["admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для экспорта данных безопасности"
            )
        
        # Экспортируем данные
        export_data = security_monitor.export_events(format_type)
        
        if format_type == "json":
            return JSONResponse({
                "export_data": export_data,
                "format": format_type,
                "exported_by": user.username
            })
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Неподдерживаемый формат: {format_type}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка экспорта данных безопасности: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера"
        )


@router.get("/alerts")
async def get_security_alerts(
    request: Request,
    limit: int = 50
):
    """Получение алертов безопасности"""
    try:
        # Пользователь уже проверен в middleware
        user = getattr(request.state, 'user', None)
        if not user:
            raise HTTPException(status_code=401, detail="Не авторизован")
        
        # Проверяем права доступа
        if user.role not in ["admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для доступа к алертам безопасности"
            )
        
        # Ограничиваем лимит
        limit = min(limit, 200)
        
        # Получаем алерты
        alerts = security_monitor.get_recent_alerts(limit)
        
        return JSONResponse({
            "alerts": alerts,
            "total_count": len(alerts),
            "limit": limit
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения алертов безопасности: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера"
        )


def _calculate_overall_risk(security_stats: Dict) -> str:
    """Вычисление общего уровня риска"""
    try:
        critical_events = security_stats.get("critical_events", 0)
        high_risk_events = security_stats.get("high_risk_events", 0)
        recent_events = security_stats.get("recent_events_count", 0)
        
        if critical_events > 10 or recent_events > 1000:
            return "CRITICAL"
        elif critical_events > 5 or high_risk_events > 50 or recent_events > 500:
            return "HIGH"
        elif critical_events > 0 or high_risk_events > 20 or recent_events > 200:
            return "MEDIUM"
        elif high_risk_events > 0 or recent_events > 50:
            return "LOW"
        else:
            return "SAFE"
    except Exception:
        return "UNKNOWN"


async def _ban_ip(ip: str, duration: int) -> None:
    """Блокировка IP адреса"""
    try:
        # Добавляем в DDoS protection
        ddos_protection._blocked_ips.add(ip)
        
        # Добавляем в rate limiter
        if hasattr(rate_limiter, '_ban_list'):
            rate_limiter._ban_list[ip] = time.time() + duration
        
        # Добавляем в Redis если доступен
        if rate_limiter._test_connection():
            ban_key = f"ip_ban:{ip}"
            rate_limiter.redis_client.set(ban_key, str(time.time() + duration), ex=duration + 60)
    except Exception as e:
        logger.error(f"Ошибка блокировки IP {ip}: {e}")


def _get_client_ip(request: Request) -> str:
    """Получение IP адреса клиента"""
    headers_to_check = [
        "X-Real-IP",
        "X-Client-IP", 
        "X-Forwarded-For",
        "CF-Connecting-IP",
        "X-Forwarded",
        "Forwarded-For",
        "Forwarded"
    ]
    
    for header in headers_to_check:
        if header in request.headers:
            ip = request.headers[header].split(",")[0].strip()
            if ip and ip != "unknown":
                return ip
    
    return request.client.host if request.client else "unknown" 