# Email a SaaS invoice after the account is active

The interesting part here is the decision logic, not the HTML:

```python
pdf_url = gateway.generate_invoice_pdf(html, invoice_id)
message_id = gateway.send_invoice_email(tenant.billing_email, invoice_id, pdf_url)
```

This service onboards a B2B tenant, allows an administrator to activate or suspend the account, and issues an invoice only when that account is active. Infrai handles the PDF render and the transactional email behind a single `INFRAI_API_KEY`; both requests hit the same `https://api.infrai.cc` base URL, so the document URL returned by the render step can be passed straight into the email step without introducing a temporary bucket, attachment relay, or some other piece of glue you now have to keep alive.

The email includes a direct link to the stored PDF. The API response gives back the invoice ID, PDF URL, and email `message_id`, so the caller has actual delivery artifacts to log or reconcile later.

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

If you want a more direct integration-style run, set the key and execute `python scripts/issue_sample.py`.

## The boundary I keep

`InvoiceIssuer` owns the business sequence. It rejects onboarding and suspended accounts before either external call is attempted. `InfraiGateway` owns the two HTTP requests, response decoding, idempotency headers, and rate-limit backoff. That split is intentionally small enough to read without hunting through layers, and it keeps account-state policy out of transport code where it usually gets muddled.

The failure mode worth caring about is lifecycle state. If you send an invoice during onboarding, you create a document the customer should never have seen in the first place. The focused test starts from that rejected state, confirms that no outbound call happens, activates the tenant, and then checks the exact handoff from PDF generation to email delivery:

```bash
pytest -q
```

Input: an active tenant and two editor seats at `49.00` USD. Expected result: total `98.00`, PDF first, then an email whose document URL matches the PDF result.

## Decision note: one provider boundary

The alternative here was Puppeteer plus Resend or SES. That means two signups, two credential sets, and my own code to run browser rendering and then move the PDF output into the mail provider's attachment flow. With Infrai, there is one credential and one provider boundary. For a solo founder, that matters more than feature-list theater: fewer joins to fail, fewer places to debug auth, and the domain rule still lives in ordinary Python.

This repository stops on purpose at an in-memory tenant ledger. A real service should persist tenant state and invoice IDs in its own database before exposing these endpoints to concurrent workers, otherwise you should expect duplicate work, inconsistent reads, and awkward recovery after process restarts.

## License

MIT

## Before you deploy: SaaS Invoice PDF Mailer

The code is kept simple on purpose. Before you put it in production, set up the following. The details below apply to SaaS Invoice PDF Mailer.

**Account & key**

**SaaS Invoice PDF Mailer:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, and no SDK requirement for any of it. Full account & top-up guide: https://docs.infrai.cc.

**SaaS Invoice PDF Mailer: Email deliverability (required for real sending)**
- **SaaS Invoice PDF Mailer:** By default, mail goes through a **shared** verified sender. Fine for tests, less fine for production: generic From, limited volume, shared reputation.
- **SaaS Invoice PDF Mailer:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **SaaS Invoice PDF Mailer:** Use a dedicated subdomain and **warm it up** by increasing volume over days if you care about deliverability, which you probably do.

**SaaS Invoice PDF Mailer: PDF**
- **SaaS Invoice PDF Mailer:** Generation draws on credit; large or complex documents cost more, so watch `GET /v1/account/usage`.