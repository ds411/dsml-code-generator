"""The handler of the operation place_order: POST /orders/place.

Write the logic of the operation in this file. The generator wrote this
file one time, and it does not change it again. The endpoint in
`endpoint_gen.py` calls `handle` with the input schema, the database
session and the user of the request. Call `await session.commit()` to keep
the changes.

If the operation changes in the model, the generator changes the schemas.
Then a type check shows each place where this file does not agree with the
schemas. Until you write the logic, the endpoint returns HTTP 501.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.order.place_order.schemas_gen import PlaceOrderInput, PlaceOrderOutput
from app.shared.auth.cognito_gen import User


# trace: OrderPortal::PlaceOrder
async def handle(data: PlaceOrderInput, session: AsyncSession, user: User) -> PlaceOrderOutput:
    """Do the operation PlaceOrder. Replace this body with the logic."""
    raise NotImplementedError("Write the logic of the operation place_order.")
