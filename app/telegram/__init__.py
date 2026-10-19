import asyncio

from app import Kenzo
from app.db.crud.keyboards import KeyboardButtonCRUD
from app.db.crud.settings import SettingsManager
from app.jobs.scheduler import start_scheduler
from app.logger import LogTag, get_logger
from app.logger.telethon import register_telethon_client, unregister_telethon_client
from app.services.send_queue import start_send_queue_worker, stop_send_queue_worker
from app.telegram.middlewares import register_global_middlewares
from app.telegram.plugins import plugin_manager
from app.version import log_runtime_versions
from config import BOT_TOKEN

logger = get_logger(__name__)


async def run_telethon(stop_event: asyncio.Event | None = None):
    await SettingsManager().add_default_settings()
    await KeyboardButtonCRUD().initialize_default_buttons()
    await Kenzo.start(bot_token=BOT_TOKEN)
    register_telethon_client(Kenzo)
    logger.info("%s Bot connected", LogTag.TELEGRAM)
    log_runtime_versions()

    register_global_middlewares()

    await plugin_manager.load_all()

    start_scheduler()
    start_send_queue_worker()

    # Resume any running broadcast from its persisted cursor after restart.
    # Local import: avoids a circular import with app.services.broadcast.manager.
    from app.services.broadcast.manager import broadcast_manager

    await broadcast_manager.resume_running_broadcasts()

    # Local import: avoids a circular import with app.telegram.admin.send2all.callbacks.
    from app.telegram.admin.send2all.callbacks import resume_broadcast_monitors

    await resume_broadcast_monitors()

    async def _stopper():
        if stop_event is None:
            return
        await stop_event.wait()
        await stop_send_queue_worker()
        unregister_telethon_client(Kenzo)
        await Kenzo.disconnect()
        logger.info("%s Bot disconnected", LogTag.TELEGRAM)

    stopper = asyncio.create_task(_stopper())
    try:
        await Kenzo.run_until_disconnected()
    finally:
        stopper.cancel()
        await stop_send_queue_worker()
        unregister_telethon_client(Kenzo)
