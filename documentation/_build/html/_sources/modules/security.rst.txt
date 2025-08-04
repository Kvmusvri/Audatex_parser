Модуль безопасности (security)
==============================

Обзор
-----

Модуль безопасности обеспечивает защиту системы от DDoS атак, мониторинг безопасности и управление доступом.

Основные компоненты:

* **security_monitor.py** - Мониторинг безопасности и событий
* **rate_limiter.py** - Ограничение частоты запросов
* **ddos_protection.py** - Защита от DDoS атак
* **api_endpoints.py** - API эндпоинты для мониторинга безопасности
* **auth_utils.py** - Утилиты для аутентификации
* **auth_middleware.py** - Middleware для проверки аутентификации
* **session_middleware.py** - Middleware для управления сессиями

Модули
-------

core.security.security_monitor
------------------------------

Мониторинг безопасности и обработка событий безопасности.

.. automodule:: core.security.security_monitor
   :members:
   :show-inheritance:
   :undoc-members:

core.security.rate_limiter
---------------------------

Ограничение частоты запросов для защиты от перегрузки.

.. automodule:: core.security.rate_limiter
   :members:
   :show-inheritance:
   :undoc-members:

core.security.ddos_protection
-----------------------------

Защита от DDoS атак и подозрительной активности.

.. automodule:: core.security.ddos_protection
   :members:
   :show-inheritance:
   :undoc-members:

core.security.api_endpoints
---------------------------

API эндпоинты для мониторинга и управления безопасностью.

.. automodule:: core.security.api_endpoints
   :members:
   :show-inheritance:
   :undoc-members:

core.security.auth_utils
------------------------

Утилиты для работы с JWT токенами и аутентификацией.

.. automodule:: core.security.auth_utils
   :members:
   :show-inheritance:
   :undoc-members:

core.security.auth_middleware
-----------------------------

Middleware для проверки аутентификации пользователей.

.. automodule:: core.security.auth_middleware
   :members:
   :show-inheritance:
   :undoc-members:

core.security.session_middleware
--------------------------------

Middleware для управления сессиями пользователей.

.. automodule:: core.security.session_middleware
   :members:
   :show-inheritance:
   :undoc-members:
