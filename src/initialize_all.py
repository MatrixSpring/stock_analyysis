# -*- coding: utf-8 -*-
"""
DSA project global init entry
Usage: python src/initialize_all.py
FastAPI: app.add_event_handler("startup", init_all_core_services)
"""
import asyncio
import logging
from typing import Any, Dict

logger = logging.getLogger("dsa.init")

INIT_STATUS: Dict[str, Any] = {
    "is_all_ready": False,
    "init_modules": [],
    "fail_modules": [],
}


async def get_system_init_status() -> Dict[str, Any]:
    return dict(INIT_STATUS)


# ============================================================
# Individual module initializers
# ============================================================

async def _init_trading_calendar() -> bool:
    try:
        from src.services.trading_calendar_utils import is_trading_day
        is_trading_day("a")
        logger.info("[OK] trading_calendar")
        return True
    except Exception as e:
        logger.warning(f"[WARN] trading_calendar: {e}")
        return True


async def _init_task_queue() -> bool:
    try:
        from src.task_queue.priority_queue import PriorityTaskQueue
        logger.info("[OK] task_queue")
        return True
    except Exception as e:
        logger.warning(f"[WARN] task_queue: {e}")
        return True


async def _init_quality_checker() -> bool:
    try:
        from src.services.data_quality_checker import create_quality_checker
        create_quality_checker("equity")
        logger.info("[OK] quality_checker")
        return True
    except Exception as e:
        logger.error(f"[FAIL] quality_checker: {e}")
        return False


async def _init_dag_controller() -> bool:
    try:
        from src.flow.dag_controller import dag_controller
        logger.info(f"[OK] dag_controller ({len(dag_controller.get_rules())} rules)")
        return True
    except Exception as e:
        logger.warning(f"[WARN] dag_controller: {e}")
        return True


async def _init_prompt_loader() -> bool:
    try:
        from src.prompt_loader import prompt_loader
        templates = prompt_loader.list_templates()
        logger.info(f"[OK] prompt_loader ({len(templates)} templates)")
        return True
    except Exception as e:
        logger.error(f"[FAIL] prompt_loader: {e}")
        return False


async def _init_llm_validator() -> bool:
    try:
        from src.llm.structured_output_validator import output_validator
        logger.info("[OK] llm_validator")
        return True
    except Exception as e:
        logger.warning(f"[WARN] llm_validator: {e}")
        return True


async def _init_source_monitor() -> bool:
    try:
        from src.services.data_source_monitor import data_source_monitor
        logger.info("[OK] source_monitor")
        return True
    except Exception as e:
        logger.warning(f"[WARN] source_monitor: {e}")
        return True


async def _init_sentiment_agg() -> bool:
    try:
        from src.services.sentiment_agg_service import sentiment_agg_service
        await sentiment_agg_service.init()
        logger.info("[OK] sentiment_agg (P0)")
        return True
    except Exception as e:
        logger.error(f"[FAIL] sentiment_agg: {e}")
        return False


async def _init_macro_geo() -> bool:
    try:
        from src.macro.macro_liquidity_monitor import macro_monitor
        result = macro_monitor.get_macro_overall()
        logger.info(f"[OK] macro+geo (trend={result.market_trend}, geo={result.geo_risk:.2f})")
        return True
    except Exception as e:
        logger.warning(f"[WARN] macro/geo degraded (default neutral): {e}")
        return True


async def _init_strategy_engine() -> bool:
    try:
        from src.services.sentiment_strategy import sentiment_strategy_engine
        from src.macro.macro_sentiment_strategy import macro_sent_strategy
        logger.info("[OK] strategy_engine (3-factor + macro)")
        return True
    except Exception as e:
        logger.error(f"[FAIL] strategy_engine: {e}")
        return False


# ============================================================
# Unified entry
# ============================================================

INIT_TASKS = [
    ("trading_calendar", _init_trading_calendar),
    ("task_queue",       _init_task_queue),
    ("quality_checker",  _init_quality_checker),
    ("dag_controller",   _init_dag_controller),
    ("prompt_loader",    _init_prompt_loader),
    ("llm_validator",    _init_llm_validator),
    ("source_monitor",   _init_source_monitor),
    ("sentiment_agg",    _init_sentiment_agg),
    ("macro_geo",        _init_macro_geo),
    ("strategy_engine",  _init_strategy_engine),
]


async def init_all_core_services() -> Dict[str, Any]:
    logger.info("DSA starting (10 modules)...")

    tasks = [fn() for _, fn in INIT_TASKS]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for (name, _), ok in zip(INIT_TASKS, results):
        if ok is True:
            INIT_STATUS["init_modules"].append(name)
        else:
            INIT_STATUS["fail_modules"].append(name)
            if isinstance(ok, Exception):
                logger.error(f"  {name}: {ok}")

    INIT_STATUS["is_all_ready"] = len(INIT_STATUS["fail_modules"]) == 0
    ok = len(INIT_STATUS["init_modules"])
    total = len(INIT_TASKS)

    if INIT_STATUS["is_all_ready"]:
        logger.info(f"DSA ready: {ok}/{total}")
    else:
        logger.warning(f"DSA partial: {ok}/{total}, failed={INIT_STATUS['fail_modules']}")

    return dict(INIT_STATUS)


async def init_all_service() -> Dict[str, Any]:
    return await init_all_core_services()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    status = asyncio.run(init_all_core_services())
    ok_count = len(status["init_modules"])
    fail_count = len(status["fail_modules"])
    print(f"\nDSA: {ok_count}/{ok_count+fail_count} OK" + (f", failed={status['fail_modules']}" if fail_count else ""))
