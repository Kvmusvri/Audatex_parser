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