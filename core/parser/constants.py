"""
Константы и настройки парсера Audatex

Основные константы:
    * BASE_URL: str - Базовый URL сайта Audatex
    * COOKIES_FILE: str - Файл для сохранения cookies
    * SCREENSHOT_DIR: str - Директория для скриншотов
    * SVG_DIR: str - Директория для SVG файлов
    * DATA_DIR: str - Директория для данных
    * TIMEOUT: int - Таймаут в секундах (30)

CSS селекторы:
    * MODAL_BUTTON_SELECTOR: str - Селектор кнопки модального окна
    * MORE_ICON_SELECTOR: str - Селектор иконки "больше"
    * VIN_SELECTOR: str - Селектор поля VIN
    * CLAIM_NUMBER_SELECTOR: str - Селектор номера заявки
    * OUTGOING_TABLE_SELECTOR: str - Селектор таблицы исходящих заявок
    * OPEN_TABLE_SELECTOR: str - Селектор таблицы открытых заявок
    * ROW_SELECTOR: str - Селектор строки таблицы
    * IFRAME_ID: str - ID iframe для веб-пада
    * EMPTY_TABLE_TEXT_SELECTOR: str - Селектор текста пустой таблицы

Текстовые константы:
    * EMPTY_TABLE_TEXT: str - Текст пустой таблицы
"""
# Константы для парсера Audatex
import urllib3

# Настройка пула соединений
urllib3.util.connection.CONNECTION_POOL_MAXSIZE = 20

# URLs и пути
BASE_URL = "https://www.audatex.ru/breclient/ui?process=NO_PROCESS&step=WorkListGrid#"
COOKIES_FILE = "cookies.pkl"

# Директории для сохранения файлов
SCREENSHOT_DIR = "static/screenshots"
SVG_DIR = "static/svgs"
DATA_DIR = "static/data"

# Таймауты
TIMEOUT = 30  # Увеличенный таймаут для надежной работы

# CSS селекторы
MODAL_BUTTON_SELECTOR = "#btn-confirm"
MORE_ICON_SELECTOR = "#BREForm > div > div > div.gdc-contentBlock-body > div > div.list-grid-container.worklistgrid_custom_sent > div.worklist-grid-component > div.react-datagrid.z-cell-ellipsis.z-style-alternate.z-with-column-menu > div.z-inner > div.z-scroller > div.z-content-wrapper > div.z-content-wrapper-fix > div > div:nth-child(1) > div.z-last.z-cell > div"
VIN_SELECTOR = "#root\\.task\\.basicClaimData\\.vehicle\\.vehicleIdentification\\.VINQuery-VIN"
CLAIM_NUMBER_SELECTOR = "#root\\.task\\.claimNumber"
OUTGOING_TABLE_SELECTOR = "#BREForm > div > div > div.gdc-contentBlock-body > div > div.list-grid-container.worklistgrid_custom_sent > div.worklist-grid-component > div.react-datagrid.z-cell-ellipsis.z-style-alternate.z-with-column-menu > div.z-inner > div.z-scroller > div.z-content-wrapper > div.z-content-wrapper-fix > div"
OPEN_TABLE_SELECTOR = "#BREForm > div > div > div.gdc-contentBlock-body > div > div.list-grid-container.worklistgrid_custom_open > div.worklist-grid-component > div.react-datagrid.z-cell-ellipsis.z-style-alternate.z-with-column-menu > div.z-inner > div.z-scroller > div.z-content-wrapper > div.z-content-wrapper-fix > div"
ROW_SELECTOR = "#BREForm .react-datagrid .z-row"
IFRAME_ID = "iframe_root.task.damageCapture.inlineWebPad"
EMPTY_TABLE_TEXT_SELECTOR = (
    "#BREForm > div > div > div.gdc-contentBlock-body > div > "
    "div.list-grid-container div.noHeaderDataGrid > div > "
    "div.z-inner > div.z-scroller > div.z-content-wrapper > "
    "div.z-empty-text > div > div.no-items-title"
)

# Текстовые константы
EMPTY_TABLE_TEXT = "Похоже у вас нет ни одного дела" 