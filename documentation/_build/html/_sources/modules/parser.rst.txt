Модуль парсера (parser)
=======================

Обзор
-----

Модуль парсера обеспечивает автоматический сбор данных автомобилей с сайта Audatex с использованием Selenium WebDriver.

Основные компоненты:

* **parser.py** - Основной модуль парсинга
* **browser.py** - Управление браузером и WebDriver
* **actions.py** - Действия с веб-элементами
* **auth.py** - Аутентификация на сайте Audatex
* **constants.py** - Константы и настройки
* **folder_manager.py** - Управление файлами и папками
* **option_processor.py** - Обработка опций автомобиля
* **output_manager.py** - Управление выходными данными
* **stealth.py** - Скрытие автоматизации от обнаружения
* **visual_processor.py** - Обработка визуальных данных (SVG, скриншоты)

Модули
-------

core.parser.parser
------------------

Основной модуль парсинга данных автомобилей.

.. automodule:: core.parser.parser
   :members:
   :undoc-members:
   :show-inheritance:

core.parser.browser
-------------------

Управление браузером Chrome и WebDriver.

.. automodule:: core.parser.browser
   :members:
   :undoc-members:
   :show-inheritance:

core.parser.actions
-------------------

Действия с веб-элементами и навигация по сайту.

.. automodule:: core.parser.actions
   :members:
   :undoc-members:
   :show-inheritance:

core.parser.auth
----------------

Аутентификация на сайте Audatex.

.. automodule:: core.parser.auth
   :members:
   :undoc-members:
   :show-inheritance:

core.parser.constants
---------------------

Константы и настройки парсера.

.. automodule:: core.parser.constants
   :members:
   :undoc-members:
   :show-inheritance:

core.parser.folder_manager
--------------------------

Управление файлами и папками для сохранения данных.

.. automodule:: core.parser.folder_manager
   :members:
   :undoc-members:
   :show-inheritance:

core.parser.option_processor
----------------------------

Обработка опций и комплектации автомобиля.

.. automodule:: core.parser.option_processor
   :members:
   :undoc-members:
   :show-inheritance:

core.parser.output_manager
--------------------------

Управление выходными данными и их сохранение.

.. automodule:: core.parser.output_manager
   :members:
   :undoc-members:
   :show-inheritance:

core.parser.stealth
-------------------

Скрытие автоматизации от обнаружения сайтом.

.. automodule:: core.parser.stealth
   :members:
   :undoc-members:
   :show-inheritance:

core.parser.visual_processor
----------------------------

Обработка визуальных данных: SVG схемы и скриншоты.

.. automodule:: core.parser.visual_processor
   :members:
   :undoc-members:
   :show-inheritance: 