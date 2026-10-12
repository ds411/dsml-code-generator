"""The handler of the operation find_products: GET /product-search.

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

from app.features.product.find_products.schemas_gen import FindProductsInput, FindProductsOutput
from app.shared.auth.cognito_gen import User


# trace: Shop::FindProducts
async def handle(
    data: FindProductsInput, session: AsyncSession, user: User
) -> list[FindProductsOutput]:
    """Do the operation FindProducts. Replace this body with the logic."""
    raise NotImplementedError("Write the logic of the operation find_products.")
