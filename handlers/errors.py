from aiogram import Router, types
from aiogram.filters import ExceptionTypeFilter
from aiogram.exceptions import TelegramAPIError
import traceback
import logging

router = Router()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot_errors.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@router.errors(ExceptionTypeFilter(Exception))
async def handle_all_errors(error_event, bot):
    """Глобальный обработчик всех необработанных ошибок."""
    exception = error_event.exception
    update = error_event.update

    # Логируем ошибку
    logger.error(f"Необработанная ошибка: {type(exception).__name__}: {exception}")
    logger.error(f"Update: {update}")
    logger.error(traceback.format_exc())

    # Если это ошибка Telegram API — не падаем
    if isinstance(exception, TelegramAPIError):
        logger.warning(f"Telegram API Error: {exception}")
        return True

    # Для остальных ошибок тоже не падаем
    return True