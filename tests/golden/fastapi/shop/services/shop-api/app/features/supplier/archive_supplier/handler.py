"""The handler of the operation archive_supplier: POST /suppliers/{supplier}/archive.

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

from app.features.supplier.archive_supplier.schemas_gen import ArchiveSupplierInput
from app.shared.auth.cognito_gen import User


# trace: Shop::ArchiveSupplier
async def handle(data: ArchiveSupplierInput, session: AsyncSession, user: User | None) -> None:
    """Do the operation ArchiveSupplier. Replace this body with the logic."""
    raise NotImplementedError("Write the logic of the operation archive_supplier.")
