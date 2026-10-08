from __future__ import annotations

import os
from decimal import Decimal
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr, Field

from invoice_service.infrai_gateway import InfraiError, InfraiGateway
from invoice_service.invoice_issuer import AccountNotBillable, InvoiceIssuer, LineItem
from invoice_service.tenant_ledger import AccountState, Tenant, TenantLedger


class OnboardTenantRequest(BaseModel):
    tenant_id: str
    legal_name: str
    billing_email: EmailStr


class ChangeAccountStateRequest(BaseModel):
    state: Literal["active", "suspended"]


class InvoiceLineRequest(BaseModel):
    description: str
    quantity: int = Field(gt=0)
    unit_price: Decimal = Field(ge=0)


class IssueInvoiceRequest(BaseModel):
    invoice_id: str
    currency: str = Field(min_length=3, max_length=3)
    items: list[InvoiceLineRequest] = Field(min_length=1)


class InvoiceResponse(BaseModel):
    invoice_id: str
    pdf_url: str
    message_id: str


def create_app(gateway: InfraiGateway | None = None) -> FastAPI:
    ledger = TenantLedger()
    resolved_gateway = gateway or InfraiGateway(os.environ["INFRAI_API_KEY"])
    issuer = InvoiceIssuer(ledger, resolved_gateway)
    app = FastAPI(title="SaaS invoice issuer")

    @app.post("/tenants", status_code=201)
    def onboard(request: OnboardTenantRequest) -> dict[str, str]:
        tenant = ledger.onboard(Tenant(**request.model_dump()))
        return {"tenant_id": tenant.tenant_id, "state": tenant.state.value}

    @app.patch("/admin/tenants/{tenant_id}/state")
    def change_state(tenant_id: str, request: ChangeAccountStateRequest) -> dict[str, str]:
        try:
            tenant = ledger.set_state(tenant_id, AccountState(request.state))
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"tenant_id": tenant.tenant_id, "state": tenant.state.value}

    @app.post("/tenants/{tenant_id}/invoices", response_model=InvoiceResponse, status_code=201)
    def issue_invoice(tenant_id: str, request: IssueInvoiceRequest) -> InvoiceResponse:
        try:
            result = issuer.issue(
                tenant_id,
                request.invoice_id,
                request.currency.upper(),
                [LineItem(**item.model_dump()) for item in request.items],
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except AccountNotBillable as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except InfraiError as exc:
            status = exc.status_code if 400 <= exc.status_code < 500 else 502
            raise HTTPException(status_code=status, detail={"code": exc.code, "message": str(exc)}) from exc
        return InvoiceResponse(**result.__dict__)

    return app


app = create_app()

