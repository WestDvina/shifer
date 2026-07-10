TAG_RU_WIN10 = "977/windows-home-windows-10-platform-install-upgrade"
TAG_RU_WIN11 = "977/windows-home-windows-11-platform-install-upgrade"

BASE_URL = "https://learn.microsoft.com/ru-ru/answers/tags"
QUESTIONS_URL = "https://learn.microsoft.com/ru-ru/answers/questions"
LOCALE = "ru-ru"

FILTER_KEYWORDS = [
    "ISO", "ссылка", "образ", "скачать", "download",
    "Russian", "x64", "x86", "22H2", "24H2", "25H2",
    "Win10", "Win11", "Windows 10", "Windows 11",
    "MediaCreationTool",
]

ISO_LINK_PATTERN = r'https?://[a-zA-Z0-9.-]*microsoft\.com[^"\'<\s]+\.iso[^"\'<\s]*'

PAGE_SIZE = 30
MAX_PAGES = 3
