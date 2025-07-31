"""
Дополнительная защита от DDoS атак
"""
import logging
import re
import time
from typing import Dict, List, Optional, Set

from fastapi import Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# Список подозрительных User-Agent
SUSPICIOUS_USER_AGENTS = {
    "bot", "crawler", "spider", "scraper", "curl", "wget", "python-requests",
    "masscan", "nmap", "sqlmap", "nikto", "dirbuster", "gobuster", "wfuzz",
    "hydra", "medusa", "ncrack", "john", "hashcat", "aircrack", "kismet",
    "metasploit", "beef", "empire", "cobalt", "burp", "zap", "nikto",
    "sqlmap", "xsser", "commix", "weevely", "webshell", "backdoor",
    "malware", "virus", "trojan", "rootkit", "keylogger", "spyware"
}

# Список известных ботов (разрешенные)
ALLOWED_BOTS = {
    "googlebot", "bingbot", "slurp", "duckduckbot", "facebookexternalhit",
    "twitterbot", "linkedinbot", "whatsapp", "telegrambot", "discordbot",
    "slackbot", "applebot", "yandexbot", "baiduspider", "sogou"
}

# Паттерны для определения автоматизированных запросов
AUTOMATION_PATTERNS = [
    r"python-requests/\d+\.\d+\.\d+",
    r"curl/\d+\.\d+\.\d+",
    r"wget/\d+\.\d+\.\d+",
    r"masscan",
    r"nmap",
    r"sqlmap",
    r"nikto",
    r"dirbuster",
    r"gobuster",
    r"wfuzz",
    r"hydra",
    r"medusa",
    r"ncrack",
    r"john",
    r"hashcat",
    r"aircrack",
    r"kismet",
    r"metasploit",
    r"beef",
    r"empire",
    r"cobalt",
    r"burp",
    r"zap",
    r"xsser",
    r"commix",
    r"weevely",
    r"webshell",
    r"backdoor",
    r"malware",
    r"virus",
    r"trojan",
    r"rootkit",
    r"keylogger",
    r"spyware"
]

# Подозрительные заголовки
SUSPICIOUS_HEADERS = {
    "x-forwarded-for": r"^(?!\d+\.\d+\.\d+\.\d+$)",
    "x-real-ip": r"^(?!\d+\.\d+\.\d+\.\d+$)",
    "x-client-ip": r"^(?!\d+\.\d+\.\d+\.\d+$)",
    "cf-connecting-ip": r"^(?!\d+\.\d+\.\d+\.\d+$)",
    "x-forwarded": r"^(?!\d+\.\d+\.\d+\.\d+$)",
    "forwarded-for": r"^(?!\d+\.\d+\.\d+\.\d+$)",
    "forwarded": r"^(?!\d+\.\d+\.\d+\.\d+$)"
}

# Подозрительные параметры запроса
SUSPICIOUS_PARAMS = {
    "union", "select", "insert", "update", "delete", "drop", "create",
    "alter", "exec", "execute", "script", "javascript", "vbscript",
    "onload", "onerror", "onclick", "onmouseover", "onfocus", "onblur",
    "eval", "alert", "confirm", "prompt", "document", "window", "location",
    "cookie", "localstorage", "sessionstorage", "xmlhttprequest", "fetch",
    "websocket", "sse", "postmessage", "iframe", "embed", "object",
    "applet", "base", "link", "meta", "style", "title", "head", "body",
    "html", "xml", "svg", "math", "form", "input", "textarea", "select",
    "option", "button", "label", "fieldset", "legend", "datalist", "output",
    "progress", "meter", "details", "summary", "menu", "menuitem", "command"
}

# Подозрительные пути
SUSPICIOUS_PATHS = {
    "/admin", "/administrator", "/wp-admin", "/wp-login", "/phpmyadmin",
    "/mysql", "/sql", "/database", "/db", "/backup", "/backups", "/bak",
    "/old", "/new", "/test", "/dev", "/development", "/staging", "/prod",
    "/production", "/config", "/configuration", "/settings", "/setup",
    "/install", "/installation", "/uninstall", "/remove", "/delete",
    "/api", "/rest", "/graphql", "/swagger", "/docs", "/documentation",
    "/help", "/support", "/contact", "/about", "/info", "/status",
    "/health", "/ping", "/pong", "/echo", "/test", "/debug", "/log",
    "/logs", "/error", "/errors", "/exception", "/exceptions", "/crash",
    "/crashes", "/dump", "/dumps", "/core", "/cores", "/memory", "/cpu",
    "/disk", "/network", "/net", "/socket", "/sockets", "/port", "/ports",
    "/service", "/services", "/daemon", "/daemons", "/process", "/processes",
    "/thread", "/threads", "/job", "/jobs", "/task", "/tasks", "/cron",
    "/crontab", "/at", "/batch", "/queue", "/queues", "/job", "/jobs",
    "/worker", "/workers", "/celery", "/redis", "/memcached", "/cache",
    "/session", "/sessions", "/auth", "/authentication", "/login",
    "/logout", "/register", "/signup", "/signin", "/signout", "/password",
    "/passwords", "/reset", "/forgot", "/remember", "/token", "/tokens",
    "/key", "/keys", "/secret", "/secrets", "/private", "/public",
    "/internal", "/external", "/local", "/remote", "/proxy", "/proxies",
    "/gateway", "/gateways", "/router", "/routers", "/switch", "/switches",
    "/firewall", "/firewalls", "/loadbalancer", "/loadbalancers", "/lb",
    "/cdn", "/cdn", "/static", "/assets", "/media", "/uploads", "/files",
    "/downloads", "/temp", "/tmp", "/cache", "/caches", "/var", "/etc",
    "/usr", "/bin", "/sbin", "/lib", "/lib64", "/home", "/root", "/opt",
    "/mnt", "/media", "/dev", "/proc", "/sys", "/run", "/var", "/tmp"
}


class DDoSProtection:
    """Класс для защиты от DDoS атак"""
    
    def __init__(self):
        self._suspicious_ips: Set[str] = set()
        self._blocked_ips: Set[str] = set()
        self._request_patterns: Dict[str, List[float]] = {}
    
    def _get_client_ip(self, request: Request) -> str:
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
    
    def _is_suspicious_user_agent(self, user_agent: str) -> bool:
        """Проверка подозрительного User-Agent"""
        if not user_agent:
            return True
        
        user_agent_lower = user_agent.lower()
        
        # Проверяем разрешенных ботов
        for bot in ALLOWED_BOTS:
            if bot in user_agent_lower:
                return False
        
        # Проверяем подозрительные паттерны
        for pattern in AUTOMATION_PATTERNS:
            if re.search(pattern, user_agent_lower):
                return True
        
        # Проверяем подозрительные слова
        for suspicious in SUSPICIOUS_USER_AGENTS:
            if suspicious in user_agent_lower:
                return True
        
        return False
    
    def _check_suspicious_headers(self, request: Request) -> List[str]:
        """Проверка подозрительных заголовков"""
        suspicious_found = []
        
        for header_name, pattern in SUSPICIOUS_HEADERS.items():
            if header_name in request.headers:
                header_value = request.headers[header_name]
                if re.search(pattern, header_value, re.IGNORECASE):
                    suspicious_found.append(f"{header_name}: {header_value}")
        
        return suspicious_found
    
    def _check_suspicious_params(self, request: Request) -> List[str]:
        """Проверка подозрительных параметров запроса"""
        suspicious_found = []
        
        # Проверяем query параметры
        for param_name, param_value in request.query_params.items():
            param_lower = param_name.lower()
            value_lower = str(param_value).lower()
            
            if param_lower in SUSPICIOUS_PARAMS:
                suspicious_found.append(f"query_param: {param_name}={param_value}")
            
            if any(suspicious in value_lower for suspicious in SUSPICIOUS_PARAMS):
                suspicious_found.append(f"query_value: {param_name}={param_value}")
        
        return suspicious_found
    
    def _check_suspicious_path(self, path: str) -> bool:
        """Проверка подозрительного пути"""
        path_lower = path.lower()
        
        for suspicious_path in SUSPICIOUS_PATHS:
            if suspicious_path in path_lower:
                return True
        
        return False
    
    def _analyze_request_pattern(self, request: Request) -> Dict:
        """Анализ паттерна запроса"""
        client_ip = self._get_client_ip(request)
        current_time = time.time()
        
        # Инициализируем паттерн для IP
        if client_ip not in self._request_patterns:
            self._request_patterns[client_ip] = []
        
        # Добавляем текущий запрос
        self._request_patterns[client_ip].append(current_time)
        
        # Очищаем старые запросы (старше 1 минуты)
        self._request_patterns[client_ip] = [
            req_time for req_time in self._request_patterns[client_ip]
            if current_time - req_time < 60
        ]
        
        # Анализируем паттерн
        request_count = len(self._request_patterns[client_ip])
        time_span = max(self._request_patterns[client_ip]) - min(self._request_patterns[client_ip]) if self._request_patterns[client_ip] else 0
        
        return {
            "ip": client_ip,
            "request_count": request_count,
            "time_span": time_span,
            "requests_per_second": request_count / max(time_span, 1),
            "is_suspicious": request_count > 100 or (time_span > 0 and request_count / time_span > 10)
        }
    
    def check_request(self, request: Request) -> Dict:
        """
        Проверка запроса на подозрительную активность
        
        Returns:
            Dict с результатами проверки
        """
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("User-Agent", "")
        path = request.url.path
        
        # Базовые проверки
        checks = {
            "ip": client_ip,
            "user_agent": user_agent,
            "path": path,
            "method": request.method,
            "suspicious_user_agent": self._is_suspicious_user_agent(user_agent),
            "suspicious_headers": self._check_suspicious_headers(request),
            "suspicious_params": self._check_suspicious_params(request),
            "suspicious_path": self._check_suspicious_path(path),
            "pattern_analysis": self._analyze_request_pattern(request),
            "risk_score": 0,
            "is_suspicious": False,
            "should_block": False
        }
        
        # Вычисляем risk score
        risk_score = 0
        
        if checks["suspicious_user_agent"]:
            risk_score += 30
        
        if checks["suspicious_headers"]:
            risk_score += len(checks["suspicious_headers"]) * 10
        
        if checks["suspicious_params"]:
            risk_score += len(checks["suspicious_params"]) * 15
        
        if checks["suspicious_path"]:
            risk_score += 20
        
        if checks["pattern_analysis"]["is_suspicious"]:
            risk_score += 40
        
        checks["risk_score"] = risk_score
        checks["is_suspicious"] = risk_score >= 50
        checks["should_block"] = risk_score >= 80
        
        # Логируем подозрительную активность
        if checks["is_suspicious"]:
            logger.warning(f"⚠️ Подозрительная активность: IP={client_ip}, Risk={risk_score}, UA={user_agent[:100]}")
        
        if checks["should_block"]:
            logger.critical(f"🚨 Блокировка запроса: IP={client_ip}, Risk={risk_score}")
            self._blocked_ips.add(client_ip)
        
        return checks
    
    def is_ip_blocked(self, ip: str) -> bool:
        """Проверка блокировки IP"""
        return ip in self._blocked_ips
    
    def get_statistics(self) -> Dict:
        """Получение статистики защиты"""
        return {
            "blocked_ips_count": len(self._blocked_ips),
            "suspicious_ips_count": len(self._suspicious_ips),
            "monitored_patterns_count": len(self._request_patterns),
            "blocked_ips": list(self._blocked_ips),
            "suspicious_ips": list(self._suspicious_ips)
        }


# Глобальный экземпляр защиты
ddos_protection = DDoSProtection()


async def ddos_protection_middleware(request: Request, call_next):
    """Middleware для защиты от DDoS"""
    try:
        # Пропускаем статические файлы
        if request.url.path.startswith("/static/"):
            return await call_next(request)
        
        # Пропускаем страницу безопасности (но не API эндпоинты)
        if request.url.path == "/security":
            return await call_next(request)
        
        # Проверяем запрос
        protection_result = ddos_protection.check_request(request)
        
        # Блокируем подозрительные запросы
        if protection_result["should_block"]:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": "Access denied",
                    "message": "Request blocked by security system",
                    "risk_score": protection_result["risk_score"]
                }
            )
        
        # Добавляем информацию о защите в заголовки
        response = await call_next(request)
        response.headers["X-Security-Risk"] = str(protection_result["risk_score"])
        response.headers["X-Security-Suspicious"] = str(protection_result["is_suspicious"]).lower()
        
        return response
        
    except Exception as e:
        logger.error(f"Ошибка в DDoS protection middleware: {e}")
        return await call_next(request) 