import asyncio
import logging
import random
from collections.abc import AsyncIterator
from typing import Any

from aiohttp import web
from models_library.api_schemas_webserver.wallets import PaymentID, PaymentMethodID
from pydantic import HttpUrl, parse_obj_as
from servicelib.aiohttp.typing_extension import CleanupContextFunc
from simcore_postgres_database.models.payments_methods import InitPromptAckFlowState
from simcore_postgres_database.models.payments_transactions import (
    PaymentTransactionState,
)
from tenacity import retry
from tenacity.before_sleep import before_sleep_log
from tenacity.wait import wait_exponential

from ._api import complete_payment
from ._db import get_pending_payment_transactions_ids
from ._methods_api import (
    _complete_create_of_wallet_payment_method,  # pylint: disable=protected-access
)
from ._methods_db import get_pending_payment_methods_ids
from .settings import get_plugin_settings

_logger = logging.getLogger(__name__)


_PERIODIC_TASK_NAME = f"{__name__}.fake_payment_completion"
_APP_TASK_KEY = f"{_PERIODIC_TASK_NAME}.task"


def _create_possible_outcomes(accepted, rejected):
    return [*(accepted for _ in range(9)), rejected]


_POSSIBLE_PAYMENTS_OUTCOMES = _create_possible_outcomes(
    accepted={
        "completion_state": PaymentTransactionState.SUCCESS,
        "message": "Succesful payment (fake)",
        "invoice_url": parse_obj_as(
            HttpUrl,
            "https://assets.website-files.com/63206faf68ab2dc3ee3e623b/634ea60a9381021f775e7a28_Placeholder%20PDF.pdf",
        ),
    },
    rejected={
        "completion_state": PaymentTransactionState.FAILED,
        "message": "Payment rejected (fake)",
    },
)


async def _fake_payment_completion(app: web.Application, payment_id: PaymentID):
    # Fakes processing time
    settings = get_plugin_settings(app)
    assert settings.PAYMENTS_FAKE_COMPLETION  # nosec
    await asyncio.sleep(settings.PAYMENTS_FAKE_COMPLETION_DELAY_SEC)

    kwargs: dict[str, Any] = random.choice(  # nosec # noqa: S311 # NOSONAR
        _POSSIBLE_PAYMENTS_OUTCOMES
    )

    _logger.info("Faking payment completion as %s", kwargs)
    await complete_payment(app, payment_id=payment_id, **kwargs)


_POSSIBLE_PAYMENTS_METHODS_OUTCOMES = _create_possible_outcomes(
    accepted={
        "completion_state": InitPromptAckFlowState.SUCCESS,
    },
    rejected={
        "completion_state": InitPromptAckFlowState.FAILED,
        "message": "Payment method rejected",
    },
)


async def _fake_payment_method_completion(
    app: web.Application, payment_method_id: PaymentMethodID
):
    # Fakes processing time
    settings = get_plugin_settings(app)
    assert settings.PAYMENTS_FAKE_COMPLETION  # nosec
    await asyncio.sleep(settings.PAYMENTS_FAKE_COMPLETION_DELAY_SEC)

    kwargs: dict[str, Any] = random.choice(  # nosec # noqa: S311 # NOSONAR
        _POSSIBLE_PAYMENTS_METHODS_OUTCOMES
    )

    _logger.info("Faking payment-method completion as %s", kwargs)
    await _complete_create_of_wallet_payment_method(
        app, payment_method_id=payment_method_id, **kwargs
    )


@retry(
    wait=wait_exponential(min=5, max=30),
    before_sleep=before_sleep_log(_logger, logging.WARNING),
)
async def _run_resilient_task(app: web.Application):
    """NOTE: Resilient task: if fails, it tries foreever"""

    pending = await get_pending_payment_transactions_ids(app)
    _logger.debug("Pending payment transactions: %s", pending)
    if pending:
        asyncio.gather(*[_fake_payment_completion(app, id_) for id_ in pending])

    pending = await get_pending_payment_methods_ids(app)
    _logger.debug("Pending payment-methods: %s", pending)
    if pending:
        asyncio.gather(*[_fake_payment_method_completion(app, id_) for id_ in pending])


async def _run_periodically(app: web.Application, wait_period_s: float):
    while True:
        await _run_resilient_task(app)
        await asyncio.sleep(wait_period_s)


def create_background_task_to_fake_payment_completion(
    wait_period_s: float,
) -> CleanupContextFunc:
    async def _cleanup_ctx_fun(
        app: web.Application,
    ) -> AsyncIterator[None]:
        # setup
        task = asyncio.create_task(
            _run_periodically(app, wait_period_s),
            name=_PERIODIC_TASK_NAME,
        )
        app[_APP_TASK_KEY] = task

        yield

        # tear-down
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            assert task.cancelled()  # nosec

    return _cleanup_ctx_fun
