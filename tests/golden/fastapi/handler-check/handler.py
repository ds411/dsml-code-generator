"""A hand-written handler of the operation cancel_order of the example model.

The CI job "FastAPI golden project" puts this file in the golden project
order-api in place of the stub. The type check must then pass. Then the job
puts the generated files of a changed model from this folder into the
project: the `in` parameter `orderId` has the new name `orderKey`. The type
check must then fail on this file (PRD-CORE-045).
"""

from http import HTTPStatus

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.order.cancel_order.schemas_gen import CancelOrderInput, CancelOrderOutput
from app.shared.auth.cognito_gen import User
from app.shared.db.models.order_gen import Order
from app.shared.errors_gen import ProblemError


# trace: OrderService::CancelOrder
async def handle(data: CancelOrderInput, session: AsyncSession, user: User) -> CancelOrderOutput:
    """Cancel the order. Return HTTP 404 if there is no order with the key."""
    row = await session.get(Order, data.order_id)
    if row is None:
        raise ProblemError(HTTPStatus.NOT_FOUND, "No order has this key.")
    row.status = "cancelled"
    await session.commit()
    return CancelOrderOutput.model_validate(row)
