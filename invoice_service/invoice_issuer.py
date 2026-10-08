from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from html import escape
from typing import Protocol

from invoice_service.tenant_ledger import AccountState, TenantLedger


class InvoiceGateway(Protocol):
    def generate_invoice_pdf(self, html: str, invoice_id: str) -> str:
        return ""

    def send_invoice_email(self, to: str, invoice_id: str, pdf_url: str) -> str:
        return ""


@dataclass(frozen=True)
class LineItem:
    description: str
    quantity: int
    unit_price: Decimal


@dataclass(frozen=True)
class IssuedInvoice:
    invoice_id: str
    pdf_url: str
    message_id: str


class AccountNotBillable(ValueError):
    pass


class InvoiceIssuer:
    def __init__(self, ledger: TenantLedger, gateway: InvoiceGateway) -> None:
        self._ledger = ledger
        self._gateway = gateway

    def issue(self, tenant_id: str, invoice_id: str, currency: str, items: list[LineItem]) -> IssuedInvoice:
        tenant = self._ledger.get(tenant_id)
        if tenant.state is not AccountState.ACTIVE:
            raise AccountNotBillable(f"Tenant {tenant_id} must be active before invoicing")

        total = sum((item.unit_price * item.quantity for item in items), Decimal("0"))
        rows = "".join(
            f"<tr><td>{escape(item.description)}</td><td>{item.quantity}</td>"
            f"<td>{item.unit_price:.2f}</td></tr>"
            for item in items
        )
        html = (
            f"<h1>Invoice {escape(invoice_id)}</h1>"
            f"<p>Bill to: {escape(tenant.legal_name)}</p>"
            f"<table><tr><th>Item</th><th>Qty</th><th>Unit price</th></tr>{rows}</table>"
            f"<p>Total: {escape(currency)} {total:.2f}</p>"
        )
        pdf_url = self._gateway.generate_invoice_pdf(html, invoice_id)
        message_id = self._gateway.send_invoice_email(tenant.billing_email, invoice_id, pdf_url)
        return IssuedInvoice(invoice_id=invoice_id, pdf_url=pdf_url, message_id=message_id)
