Модуль аутентификации (auth)
============================

Обзор
-----

Модуль аутентификации обеспечивает управление пользователями, сессиями и авторизацией в системе.

Основные компоненты:

* **routes.py** - HTTP эндпоинты для аутентификации
* **users.py** - Управление пользователями и сессиями
* **decorators.py** - Декораторы для проверки авторизации
* **db_routes.py** - API эндпоинты для работы с пользователями
* **db_auth.py** - Функции аутентификации для базы данных
* **db_decorators.py** - Декораторы для API аутентификации

Модули
-------

core.auth.routes
----------------

HTTP эндпоинты для веб-интерфейса аутентификации.

.. automodule:: core.auth.routes
   :members:
   :show-inheritance:
   :undoc-members:

core.auth.users
---------------

Управление пользователями, сессиями и аутентификацией.

.. automodule:: core.auth.users
   :members:
   :show-inheritance:
   :undoc-members:

core.auth.decorators
--------------------

Декораторы для проверки авторизации пользователей.

.. automodule:: core.auth.decorators
   :members:
   :show-inheritance:
   :undoc-members:

core.auth.db_routes
-------------------

API эндпоинты для работы с пользователями через REST API.

.. automodule:: core.auth.db_routes
   :members:
   :show-inheritance:
   :undoc-members:

core.auth.db_auth
-----------------

Функции аутентификации для работы с базой данных.

.. automodule:: core.auth.db_auth
   :members:
   :show-inheritance:
   :undoc-members:

core.auth.db_decorators
-----------------------

Декораторы для API аутентификации и авторизации.

.. automodule:: core.auth.db_decorators
   :members:
   :show-inheritance:
   :undoc-members:
