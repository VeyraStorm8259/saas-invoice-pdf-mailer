from fastapi.testclient import TestClient

from invoice_service.api import app


client = TestClient(app)
tenant_id = "acme-eu"

client.post(
    "/tenants",
    json={"tenant_id": tenant_id, "legal_name": "Acme Analytics Ltd", "billing_email": "billing@example.com"},
).raise_for_status()
client.patch(f"/admin/tenants/{tenant_id}/state", json={"state": "active"}).raise_for_status()
response = client.post(
    f"/tenants/{tenant_id}/invoices",
    json={
        "invoice_id": "INV-2026-0091",
        "currency": "USD",
        "items": [{"description": "Workspace subscription", "quantity": 12, "unit_price": "49.00"}],
    },
)
response.raise_for_status()
print(response.json())

