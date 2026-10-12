"""The contract test of a React client and the OpenAPI document of its API (story #176).

- `typescript.py` reads the expressions of the generated TypeScript files.
- `react_client.py` gives the operations of the React client: the method,
  the path, the parameters, the request body and the response.
- `openapi.py` gives the same data from an OpenAPI document.
- `shapes.py` compares the two sides and gives each difference.

The test is `tests/test_react_contract.py` (PRD-APP-005).
"""
