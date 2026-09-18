"""
Payment job orchestration — coordinates payment processors on a schedule.
"""

import time

from app.jobs.payments import (
    ManualCardProcessor,
    StarsExpiryProcessor,
    TONProcessor,
    TRXProcessor,
    USDTProcessor,
)
from app.logger import LogTag, get_logger

logger = get_logger(__name__)
# Initialize processors
manual_card_processor = ManualCardProcessor()
trx_processor = TRXProcessor()
usdt_processor = USDTProcessor()
ton_processor = TONProcessor()
stars_expiry_processor = StarsExpiryProcessor()


async def auto_confirm_job():
    start_time = time.time()
    logger.debug("%s auto_confirm_job started", LogTag.JOB)
    await manual_card_processor.check_payments()
    elapsed = time.time() - start_time
    logger.debug(f"{LogTag.JOB} auto_confirm_job completed: {elapsed:.2f}s")


async def trx_checking():
    start_time = time.time()
    logger.debug("%s trx_checking started", LogTag.JOB)
    await trx_processor.check_payments()
    elapsed = time.time() - start_time
    logger.debug(f"{LogTag.JOB} trx_checking completed: {elapsed:.2f}s")


async def usdt_checking():
    start_time = time.time()
    logger.debug("%s usdt_checking started", LogTag.JOB)
    await usdt_processor.check_payments()
    elapsed = time.time() - start_time
    logger.debug(f"{LogTag.JOB} usdt_checking completed: {elapsed:.2f}s")


async def ton_checking():
    start_time = time.time()
    logger.debug("%s ton_checking started", LogTag.JOB)
    await ton_processor.check_payments()
    elapsed = time.time() - start_time
    logger.debug(f"{LogTag.JOB} ton_checking completed: {elapsed:.2f}s")


async def expire_star_transactions() -> None:
    start_time = time.time()
    logger.debug("%s expire_star_transactions started", LogTag.JOB)
    await stars_expiry_processor.check_payments()
    elapsed = time.time() - start_time
    logger.debug(f"{LogTag.JOB} expire_star_transactions completed: {elapsed:.2f}s")
