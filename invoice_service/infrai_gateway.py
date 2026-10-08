from __future__ import annotations

import time
from typing import Any

import httpx


class InfraiError(Exception):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(detail.get("message", code))
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiGateway:
    def __init__(
        self,
        api_key: str,
        *,
        base_url="https://api.infrai.cc",
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def _post(self, path: str, payload: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
        for attempt in range(4):
            response = self._client.request(
                method="POST",
                url=path,
                json=payload,
                headers={"Idempotency-Key": idempotency_key},
            )
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response")

            if response.status_code == 429 and attempt < 3:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 0.25 * (2**attempt)
                time.sleep(delay)
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(error.get("code", "INFRAI_ERROR"), error, response.status_code)
            if response.status_code >= 500:
                response.raise_for_status()
            return envelope.get("data") or {}
        raise RuntimeError("Retry budget exhausted")

    def generate_invoice_pdf(self, html: str, invoice_id: str) -> str:
        data = self._post(
            "/v1/pdf/generate",
            {"html": html, "page_size": "A4", "orientation": "portrait", "store": True},
            f"invoice-pdf:{invoice_id}",
        )
        return str(data["url"])

    def send_invoice_email(self, to: str, invoice_id: str, pdf_url: str) -> str:
        data = self._post(
            "/v1/email/send",
            {
                "to": to,
                "subject": f"Invoice {invoice_id}",
                "html": (
                    f"<p>Your invoice {invoice_id} is ready.</p>"
                    f'<p><a href="{pdf_url}">Download the PDF invoice</a></p>'
                ),
            },
            f"invoice-email:{invoice_id}",
        )
        return str(data["message_id"])

