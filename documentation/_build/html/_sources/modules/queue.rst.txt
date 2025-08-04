Модуль очереди (queue)
======================

Обзор
-----

Модуль очереди обеспечивает обработку заявок на парсинг данных через Redis и управление очередью задач.

Основные компоненты:

* **queue_processor.py** - Процессор для обработки очереди заявок
* **redis_manager.py** - Управление Redis и очередью задач
* **api_endpoints.py** - API эндпоинты для работы с очередью

Модули
-------

core.queue.queue_processor
--------------------------

Процессор для обработки очереди заявок на парсинг.

.. automodule:: core.queue.queue_processor
   :members:
   :show-inheritance:
   :undoc-members:

core.queue.redis_manager
------------------------

Управление Redis базой данных и очередью задач.

.. automodule:: core.queue.redis_manager
   :members:
   :show-inheritance:
   :undoc-members:

core.queue.api_endpoints
------------------------

API эндпоинты для управления очередью заявок.

.. automodule:: core.queue.api_endpoints
   :members:
   :show-inheritance:
   :undoc-members:
