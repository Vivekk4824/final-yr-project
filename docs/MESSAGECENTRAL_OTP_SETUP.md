# Message Central Verify Now OTP setup

VendorMap supports two server-side OTP providers:

- `console` generates a four-digit OTP locally for development and tests.
- `messagecentral` asks Message Central Verify Now to generate, send, and validate a real four-digit SMS OTP.

Neither provider returns an OTP through VendorMap's API. A real Message Central OTP is never available to VendorMap and is never printed.

## Create the account and obtain credentials

1. Create or sign in to a [Message Central account](https://console.messagecentral.com/).
2. Open Verify Now and locate the Customer ID and the API examples under **Try with Code**.
3. Copy the dashboard **Auth Token** (currently shown with an `MC_` prefix) and store it as `MESSAGECENTRAL_AUTH_TOKEN`; do not store it in frontend code or a `VITE_*` variable.
4. The legacy Base64 password/key flow remains available through `MESSAGECENTRAL_AUTH_KEY` when a dashboard token is not provided.
5. Add credits before production use. Verify Now is pay-as-you-go; Message Central states that sending is charged while validation has no separate fee.

Message Central's generic Indian Verify Now template and sender can be used without registering a separate Sender ID or DLT template. Custom branding/template requirements may require account funding or assistance from Message Central.

## Backend environment

Configure the deployment environment, not source code:

```env
APP_ENV=production
OTP_PROVIDER=messagecentral
OTP_DEBUG=false
MESSAGECENTRAL_CUSTOMER_ID=replace-with-customer-id
MESSAGECENTRAL_AUTH_TOKEN=replace-with-dashboard-auth-token
MESSAGECENTRAL_AUTH_KEY=
MESSAGECENTRAL_EMAIL=account@example.com
OTP_EXPIRY_MINUTES=5
OTP_RESEND_COOLDOWN_SECONDS=60
OTP_MAX_ATTEMPTS=5
```

`MESSAGECENTRAL_AUTH_TOKEN` is preferred. `MESSAGECENTRAL_AUTH_KEY` and `MESSAGECENTRAL_EMAIL` are needed only for the legacy token-generation flow.

The backend fails closed when `messagecentral` is selected without the Customer ID and either supported authentication credential. It never falls back to console mode.

## API flow used by VendorMap

VendorMap follows the official [Verify Now API guide](https://www.messagecentral.com/en-in/product/verify-now/api):

1. Use the dashboard `MESSAGECENTRAL_AUTH_TOKEN` directly. When only a legacy Base64 key is configured, generate an `authToken` with `GET /auth/v1/authentication/token`.
2. Send with `POST /verification/v3/send`, `countryCode=91`, `flowType=SMS`, and `otpLength=4`.
3. Store only the returned `verificationId` in the existing short-lived OTP challenge.
4. Validate the entered code with `GET /verification/v3/validateOtp` using the same auth token.
5. Create the existing VendorMap session only after Message Central reports `VERIFICATION_COMPLETED`.

Message Central supports OTP lengths from four to eight digits and documents four as the default. VendorMap explicitly requests four digits so the provider, backend validation, console provider, and frontend boxes agree.

VendorMap enforces a five-minute expiry locally before calling validation. It also enforces a 60-second resend cooldown, five local verification attempts, single use, and hourly phone/IP request limits. In the Message Central dashboard, keep the Verify Now resend/validity interval at 60 seconds so provider behavior matches the UI.

## Local console mode

```env
APP_ENV=development
OTP_PROVIDER=console
OTP_DEBUG=true
```

The four-digit code is printed only in the backend development terminal. Console mode is rejected in production. In the isolated test environment it is allowed but not printed.

## Real-number test

1. Add credits and verify that the Customer ID/key work with the account's **Try with Code** example.
2. Start VendorMap with `OTP_PROVIDER=messagecentral`.
3. Request an OTP for a valid Indian mobile number.
4. Enter the four-digit SMS code within five minutes.
5. Confirm that the vendor dashboard or registration flow opens and that the same challenge cannot be used again.
6. Wait 60 seconds before testing resend. Each successful send may consume credits.

Automated tests use mocked HTTP responses and never send a real SMS.

## Common errors

- **401/403 or token generation failure:** verify the Customer ID, Base64 authentication key, optional email, and that the credential belongs to the same Message Central account.
- **501 INVALID_CUSTOMER_ID:** copy the Customer ID again from the dashboard.
- **505 INVALID_VERIFICATION_ID:** request a new OTP; the stored provider reference is no longer valid.
- **702 WRONG_OTP_PROVIDED:** enter the latest four-digit code.
- **703 ALREADY_VERIFIED:** request a new OTP; provider-managed codes are single-use.
- **705 VERIFICATION_EXPIRED:** request a new code.
- **800 MAXIMUM_LIMIT_REACHED:** wait or contact Message Central if the account/provider limit persists.
- **Delivery failure:** check credits, the Indian number, Verify Now reports, and account activation. VendorMap intentionally returns only a safe delivery error to the browser.

Official references: [Verify Now API](https://www.messagecentral.com/en-in/product/verify-now/api) and [Verify Now FAQ](https://www.messagecentral.com/product/verify-now/faqs).
