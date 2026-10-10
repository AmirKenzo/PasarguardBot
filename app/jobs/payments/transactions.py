"""
Payment job orchestration — coordinates payment processors on a schedule.
"""

import time

from app.jobs.payments import (
    ManualCardProcessor,
    POLProcessor,
    StarsExpiryProcessor,
    TonPaysProcessor,
    TONProcessor,
    TRXProcessor,
    USDTNetworksProcessor,
    USDTProcessor,
    ZarinpalProcessor,
    ZibalProcessor,
)
from app.logger import LogTag, get_logger

logger = get_logger(__name__)
# Initialize processors
manual_card_processor = ManualCardProcessor()
trx_processor = TRXProcessor()
usdt_processor = USDTProcessor()
ton_processor = TONProcessor()
stars_expiry_processor = StarsExpiryProcessor()
usdt_networks_processor = USDTNetworksProcessor()
pol_processor = POLProcessor()
tonpays_processor = TonPaysProcessor()
zarinpal_processor = ZarinpalProcessor()
zibal_processor = ZibalProcessor()


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


async def usdt_networks_checking():
    start_time = time.time()
    logger.debug("%s usdt_networks_checking started", LogTag.JOB)
    await usdt_networks_processor.check_payments()
    elapsed = time.time() - start_time
    logger.debug(f"{LogTag.JOB} usdt_networks_checking completed: {elapsed:.2f}s")


async def pol_checking():
    start_time = time.time()
    logger.debug("%s pol_checking started", LogTag.JOB)
    await pol_processor.check_payments()
    elapsed = time.time() - start_time
    logger.debug(f"{LogTag.JOB} pol_checking completed: {elapsed:.2f}s")


async def tonpays_checking():
    start_time = time.time()
    logger.debug("%s tonpays_checking started", LogTag.JOB)
    await tonpays_processor.check_payments()
    elapsed = time.time() - start_time
    logger.debug(f"{LogTag.JOB} tonpays_checking completed: {elapsed:.2f}s")


async def zarinpal_checking():
    start_time = time.time()
    logger.debug("%s zarinpal_checking started", LogTag.JOB)
    await zarinpal_processor.check_payments()
    elapsed = time.time() - start_time
    logger.debug(f"{LogTag.JOB} zarinpal_checking completed: {elapsed:.2f}s")


async def zibal_checking():
    start_time = time.time()
    logger.debug("%s zibal_checking started", LogTag.JOB)
    await zibal_processor.check_payments()
    elapsed = time.time() - start_time
    logger.debug(f"{LogTag.JOB} zibal_checking completed: {elapsed:.2f}s")


async def expire_star_transactions() -> None:
    start_time = time.time()
    logger.debug("%s expire_star_transactions started", LogTag.JOB)
    await stars_expiry_processor.check_payments()
    elapsed = time.time() - start_time
    logger.debug(f"{LogTag.JOB} expire_star_transactions completed: {elapsed:.2f}s")
