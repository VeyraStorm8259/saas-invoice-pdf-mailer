from decimal import Decimal

import pytest

from invoice_service.invoice_issuer import AccountNotBillable, InvoiceIssuer, LineItem
from invoice_service.tenant_ledger import AccountState, Tenant, TenantLedger


class RecordingGateway:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def generate_invoice_pdf(self, html: str, invoice_id: str) -> str:
        self.calls.append(("pdf", invoice_id))
        assert "Total: USD 98.00" in html
        return "https://documents.example/INV-42.pdf"

    def send_invoice_email(self, to: str, invoice_id: str, pdf_url: str) -> str:
        self.calls.append(("email", pdf_url))
        assert to == "billing@northwind.example"
        return "msg_42"


def test_only_active_tenant_is_invoiced_and_pdf_flows_to_email() -> None:
    ledger = TenantLedger()
    tenant = ledger.onboard(Tenant("northwind", "Northwind Labs", "billing@northwind.example"))
    gateway = RecordingGateway()
    issuer = InvoiceIssuer(ledger, gateway)
    item = LineItem("Editor seats", 2, Decimal("49.00"))

    with pytest.raises(AccountNotBillable):
        issuer.issue(tenant.tenant_id, "INV-42", "USD", [item])
    assert gateway.calls == []

    ledger.set_state(tenant.tenant_id, AccountState.ACTIVE)
    result = issuer.issue(tenant.tenant_id, "INV-42", "USD", [item])

    assert result.message_id == "msg_42"
    assert gateway.calls == [
        ("pdf", "INV-42"),
        ("email", "https://documents.example/INV-42.pdf"),
    ]
