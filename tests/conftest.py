import pytest
from firefly_mcp.client import FireflyClient


@pytest.fixture
def client():
    return FireflyClient(
        firefly_url="http://firefly.test",
        token="test-token",
        importer_url="http://importer.test",
        importer_secret="test-secret-16chars",
    )


SAMPLE_TRANSACTION = {
    "id": "1",
    "attributes": {
        "transactions": [
            {
                "transaction_journal_id": "1",
                "type": "withdrawal",
                "date": "2026-03-01T00:00:00+00:00",
                "amount": "25.50",
                "description": "GRAB FOOD",
                "source_name": "HSBC Checking",
                "destination_name": "Grab Food",
                "category_name": None,
                "budget_name": None,
                "tags": [],
                "notes": None,
            }
        ]
    },
}
