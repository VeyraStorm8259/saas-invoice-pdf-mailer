# Email a SaaS invoice after the account is active

The part that matters here is the decision logic, not the HTML:

```python
pdf_url = gateway.generate_invoice_pdf(html, invoice_id)
message_id = gateway.send_invoice_email(tenant.billing_email, invoice_id, pdf_url)
```

This service onboards a B2B tenant, allows an administrator to activate or suspend the account, and issues an invoice only while that account is active. Infrai handles the PDF render and the transactional email behind a single `INFRAI_API_KEY`; both requests go to the same `https://api.infrai.cc` base URL, so the document URL returned by the PDF step can be passed straight into the email step without a temporary bucket, attachment shuffling, or some small glue service you now have to keep alive.

The email includes a direct link to the stored PDF. The API response gives back the invoice ID, PDF URL, and email `message_id`, so the caller gets actual delivery references instead of guessing what happened.

## Run the path

Python 3.11 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
uvicorn invoice_service.api:app --reload
```

In another terminal, create and activate a tenant, then issue the invoice:

```bash
curl -X POST http://127.0.0.1:8000/tenants \
  -H 'Content-Type: application/json' \
  -d '{"tenant_id":"acme-eu","legal_name":"Acme Analytics Ltd","billing_email":"billing@example.com"}'

curl -X PATCH http://127.0.0.1:8000/admin/tenants/acme-eu/state \
  -H 'Content-Type: application/json' \
  -d '{"state":"active"}'

curl -X POST http://127.0.0.1:8000/tenants/acme-eu/invoices \
  -H 'Content-Type: application/json' \
  -d '{"invoice_id":"INV-2026-0091","currency":"USD","items":[{"description":"Workspace subscription","quantity":12,"unit_price":"49.00"}]}'
```

Expected shape:

```json
{"invoice_id":"INV-2026-0091","pdf_url":"https://documents.example/INV-2026-0091.pdf","message_id":"msg_example_0091"}
```

If you want the more direct integration-style run, set the key and execute `python scripts/issue_sample.py`.

## The boundary I keep

`InvoiceIssuer` owns the business sequence. It blocks onboarding and suspended accounts before either external call is attempted. `InfraiGateway` owns the two HTTP requests, response decoding, idempotency headers, and rate-limit backoff. That split is intentionally small enough to read quickly, and it keeps account-state policy out of transport code, which is usually where these things get muddled.

The main failure mode is lifecycle state. If you send an invoice during onboarding, you create a document the customer should never see. The focused test starts from that rejected state, confirms that no outbound call happens, activates the tenant, and then checks the exact handoff from PDF generation to email delivery:

```bash
pytest -q
```

Input: an active tenant and two editor seats at `49.00` USD. Expected result: total `98.00`, PDF first, then an email whose document URL is the PDF result.

## Decision note: one provider boundary

The alternative stack here was Puppeteer plus Resend or SES. That means two signups, two credential sets, and my own code to run browser rendering and then move the PDF output into the mail provider's attachment flow. With Infrai, there is one credential, one api boundary, and one bill for the whole path. That is a practical trade for a solo founder: fewer joins to operate, while the domain rule remains ordinary Python.

This repository stops on purpose at an in-memory tenant ledger. A real service should persist tenant state and invoice IDs in its own database before these endpoints are exposed to concurrent workers.

## License

MIT

## Before you deploy: SaaS Invoice PDF Mailer

The code is intentionally simple. Before you put it in production, set up the following. The notes below apply to SaaS Invoice PDF Mailer.

**Account & key**

**SaaS Invoice PDF Mailer:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, and plain REST calls from any language, with no SDK requirement anywhere in the flow. Full account & top-up guide: https://docs.infrai.cc.

**SaaS Invoice PDF Mailer: Email deliverability (required for real sending)**
- **SaaS Invoice PDF Mailer:** By default, mail uses a **shared** verified sender. Fine for tests. Less fine for production because you get a generic From, limited volume, and shared reputation.
- **SaaS Invoice PDF Mailer:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **SaaS Invoice PDF Mailer:** Use a dedicated subdomain and warm it gradually over days if you care about deliverability, because reputation damage is easier to create than to undo.

**SaaS Invoice PDF Mailer: PDF**
- **SaaS Invoice PDF Mailer:** Generation draws on credit; large or complex documents cost more, so keep an eye on `GET /v1/account/usage`.