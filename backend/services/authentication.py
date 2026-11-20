"""Authentication primitives for vendor OTP and NMC officer sessions.

Phone numbers, OTPs, passwords, and session tokens are never persisted in
plaintext. This module intentionally does not depend on recommendation logic.
"""
from __future__ import annotations
from backend.core.data_paths import dataset_path

import csv
import hashlib
import hmac
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

import httpx

from sqlalchemy import text

from backend.core.config import get_auth_settings
from backend.repositories.database import DATABASE_PATH, connect, transaction, utc_now


ROOT = Path(__file__).resolve().parents[2]
HISTORICAL_VENDOR_SOURCE = dataset_path("historical_vendors")
SESSION_COOKIE_NAME = "nmc_session"
SESSION_EXPIRY_HOURS = 12
OTP_RATE_WINDOW_MINUTES = 60
OTP_REQUESTS_PER_MOBILE = 5
OTP_REQUESTS_PER_IP = 20
MESSAGECENTRAL_BASE_URL = "https://cpaas.messagecentral.com"
MESSAGECENTRAL_TOKEN_URL = f"{MESSAGECENTRAL_BASE_URL}/auth/v1/authentication/token"
MESSAGECENTRAL_SEND_URL = f"{MESSAGECENTRAL_BASE_URL}/verification/v3/send"
MESSAGECENTRAL_VERIFY_URL = f"{MESSAGECENTRAL_BASE_URL}/verification/v3/validateOtp"
OTP_LENGTH = 4


class AuthError(ValueError):
    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message)
        self.status_code = status_code


def _secret() -> bytes:
    return get_auth_settings().auth_hmac_secret.encode("utf-8")


def normalize_indian_mobile(value: str) -> str:
    """Normalize conservative Indian mobile formats to ten digits."""
    raw = (value or "").strip()
    if not raw:
        raise AuthError("Enter a valid Indian mobile number.", 422)
    if re.search(r"[A-Za-z]", raw):
        raise AuthError("Enter a valid Indian mobile number.", 422)
    digits = re.sub(r"[^0-9]", "", raw)
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if not re.fullmatch(r"[6-9][0-9]{9}", digits):
        raise AuthError("Enter a valid Indian mobile number.", 422)
    return digits


def phone_hmac(normalized_mobile: str) -> str:
    return hmac.new(_secret(), f"phone:{normalized_mobile}".encode(), hashlib.sha256).hexdigest()


def _ip_hmac(request_ip: str) -> str:
    return hmac.new(_secret(), f"ip:{request_ip}".encode(), hashlib.sha256).hexdigest()


def _otp_hash(challenge_id: str, otp: str) -> str:
    return hmac.new(_secret(), f"otp:{challenge_id}:{otp}".encode(), hashlib.sha256).hexdigest()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def seed_historical_vendor_identities(
    database_path: str | Path = DATABASE_PATH,
    source_path: str | Path = HISTORICAL_VENDOR_SOURCE,
) -> dict[str, int | str | bool]:
    """Idempotently seed only unambiguous HMAC-to-vendor mappings."""
    source_path = Path(source_path)
    if not source_path.is_file():
        connection = connect(database_path)
        try:
            identity_rows = connection.execute(
                "SELECT COUNT(*) AS identity_count FROM vendor_auth_identities"
            ).fetchone()["identity_count"]
        finally:
            connection.close()
        return {
            "source": str(source_path),
            "source_available": False,
            "rows": 0,
            "valid_rows": 0,
            "missing_rows": 0,
            "invalid_nonempty_values": 0,
            "distinct_valid_numbers": 0,
            "ambiguous_numbers": 0,
            "ambiguous_vendor_ids": 0,
            "seedable_numbers": 0,
            "inserted": 0,
            "already_existing": 0,
            "identity_rows": identity_rows,
        }
    with source_path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        required = {"vendor_id", "phone_number", "alternate_phone"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"Historical vendor source must contain {sorted(required)}")
        rows = list(reader)

    number_to_vendors: dict[str, set[str]] = {}
    valid_rows = 0
    missing_rows = 0
    invalid_nonempty = 0
    for row in rows:
        row_numbers: set[str] = set()
        for column in ("phone_number", "alternate_phone"):
            raw = (row.get(column) or "").strip()
            if not raw:
                continue
            try:
                row_numbers.add(normalize_indian_mobile(raw))
            except AuthError:
                invalid_nonempty += 1
        if row_numbers:
            valid_rows += 1
            for number in row_numbers:
                number_to_vendors.setdefault(number, set()).add(row["vendor_id"])
        else:
            missing_rows += 1

    ambiguous = {number for number, vendors in number_to_vendors.items() if len(vendors) > 1}
    now = utc_now()
    seedable_numbers = len(number_to_vendors) - len(ambiguous)
    with transaction(database_path, immediate=True) as connection:
        existing_hashes = {
            row["phone_hash"]
            for row in connection.execute(
                "SELECT phone_hash FROM vendor_auth_identities"
            ).fetchall()
        }
        pending_rows = []
        for number, vendors in number_to_vendors.items():
            if number in ambiguous:
                continue
            vendor_id = next(iter(vendors))
            hashed_phone = phone_hmac(number)
            if hashed_phone not in existing_hashes:
                pending_rows.append({
                    "identity_id": f"VID_{uuid.uuid4().hex}",
                    "vendor_id": vendor_id,
                    "phone_hash": hashed_phone,
                    "created_at": now,
                    "updated_at": now,
                })
        inserted = 0
        if pending_rows:
            cursor = connection.execute(
                text(
                    """INSERT INTO vendor_auth_identities
                       (identity_id, vendor_id, phone_hash, vendor_source, is_verified, created_at, updated_at)
                       VALUES (:identity_id, :vendor_id, :phone_hash, 'HISTORICAL', 0,
                               :created_at, :updated_at)
                       ON CONFLICT DO NOTHING"""
                ),
                pending_rows,
            )
            inserted = max(cursor.rowcount, 0)
        already_existing = seedable_numbers - inserted
        identity_rows = connection.execute(
            "SELECT COUNT(*) AS identity_count FROM vendor_auth_identities"
        ).fetchone()["identity_count"]
    return {
        "source": str(source_path),
        "source_available": True,
        "rows": len(rows),
        "valid_rows": valid_rows,
        "missing_rows": missing_rows,
        "invalid_nonempty_values": invalid_nonempty,
        "distinct_valid_numbers": len(number_to_vendors),
        "ambiguous_numbers": len(ambiguous),
        "ambiguous_vendor_ids": sum(len(number_to_vendors[number]) for number in ambiguous),
        "seedable_numbers": seedable_numbers,
        "inserted": inserted,
        "already_existing": already_existing,
        "identity_rows": identity_rows,
    }


class OtpProviderError(RuntimeError):
    """Safe provider failure; never contains credentials, mobile numbers, or OTPs."""


class InvalidProviderOtp(AuthError):
    pass


class OtpProvider(Protocol):
    name: str

    def issue_otp(self, normalized_mobile: str, challenge_id: str) -> str: ...

    def verify_otp(
        self, normalized_mobile: str, challenge_id: str, otp_code: str, otp_hash: str
    ) -> None: ...


class ConsoleOtpProvider:
    """Development-only provider; never includes the OTP in API responses."""

    name = "console"

    def issue_otp(self, normalized_mobile: str, challenge_id: str) -> str:
        settings = get_auth_settings()
        if settings.app_env not in {"development", "test"}:
            raise OtpProviderError("Console OTP is disabled in this environment")
        otp_code = generate_otp()
        if settings.app_env == "development" and settings.otp_debug:
            print(f"DEVELOPMENT OTP: {otp_code}")
        return _otp_hash(challenge_id, otp_code)

    def verify_otp(
        self, normalized_mobile: str, challenge_id: str, otp_code: str, otp_hash: str
    ) -> None:
        if not hmac.compare_digest(otp_hash, _otp_hash(challenge_id, otp_code)):
            raise InvalidProviderOtp("Incorrect OTP.")


class MessageCentralOtpProvider:
    """Message Central Verify Now provider-generated and verified OTPs."""

    name = "messagecentral"

    def __init__(self, client: httpx.Client | None = None):
        settings = get_auth_settings()
        if not settings.messagecentral_customer_id or not (
            settings.messagecentral_auth_token or settings.messagecentral_auth_key
        ):
            raise OtpProviderError("Message Central OTP is not configured")
        self._customer_id = settings.messagecentral_customer_id
        # Current dashboards issue an MC_... token directly. Accept it from the
        # explicit token variable and recognize it in the former key variable
        # so existing local configuration keeps working during migration.
        legacy_value = settings.messagecentral_auth_key
        self._static_auth_token = settings.messagecentral_auth_token or (
            legacy_value if legacy_value and legacy_value.startswith("MC_") else None
        )
        self._auth_key = None if self._static_auth_token else legacy_value
        self._email = settings.messagecentral_email
        self._client = client

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, str | int],
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        try:
            if self._client is not None:
                response = self._client.request(method, url, params=params, headers=headers)
            else:
                response = httpx.request(
                    method,
                    url,
                    params=params,
                    headers=headers,
                    timeout=10.0,
                )
        except httpx.HTTPError as exc:
            raise OtpProviderError("OTP provider is temporarily unavailable") from exc
        return response

    @staticmethod
    def _json_body(response: httpx.Response) -> dict:
        try:
            body = response.json()
        except ValueError:
            raise OtpProviderError("OTP provider returned an invalid response")
        if not isinstance(body, dict):
            raise OtpProviderError("OTP provider returned an invalid response")
        return body

    @staticmethod
    def _response_code(body: dict) -> str:
        data = body.get("data") if isinstance(body.get("data"), dict) else {}
        return str(data.get("responseCode") or body.get("responseCode") or "")

    def _auth_token(self) -> str:
        if self._static_auth_token:
            return self._static_auth_token
        if not self._auth_key:
            raise OtpProviderError("Message Central OTP is not configured")
        params: dict[str, str] = {
            "customerId": self._customer_id,
            "key": self._auth_key,
            "scope": "NEW",
            "country": "91",
        }
        if self._email:
            params["email"] = self._email
        response = self._request("GET", MESSAGECENTRAL_TOKEN_URL, params=params)
        if not 200 <= response.status_code < 300:
            raise OtpProviderError("OTP provider authentication failed")
        body = self._json_body(response)
        data = body.get("data") if isinstance(body.get("data"), dict) else {}
        token = body.get("token") or data.get("token")
        if not isinstance(token, str) or not token.strip():
            raise OtpProviderError("OTP provider authentication failed")
        return token

    def issue_otp(self, normalized_mobile: str, challenge_id: str) -> str:
        response = self._request(
            "POST",
            MESSAGECENTRAL_SEND_URL,
            params={
                "countryCode": "91",
                "customerId": self._customer_id,
                "otpLength": OTP_LENGTH,
                "mobileNumber": normalized_mobile,
                "flowType": "SMS",
            },
            headers={"authToken": self._auth_token()},
        )
        if not 200 <= response.status_code < 300:
            raise OtpProviderError("OTP provider rejected the send request")
        body = self._json_body(response)
        data = body.get("data") if isinstance(body.get("data"), dict) else {}
        verification_id = data.get("verificationId")
        if self._response_code(body) != "200" or verification_id in {None, ""}:
            raise OtpProviderError("OTP provider rejected the send request")
        # This opaque ID is required for validation; the OTP itself never enters VendorMap.
        return str(verification_id)

    def verify_otp(
        self, normalized_mobile: str, challenge_id: str, otp_code: str, otp_hash: str
    ) -> None:
        response = self._request(
            "GET",
            MESSAGECENTRAL_VERIFY_URL,
            params={"verificationId": otp_hash, "code": otp_code},
            headers={"authToken": self._auth_token()},
        )
        if not 200 <= response.status_code < 300:
            if response.status_code in {400, 404, 409}:
                raise InvalidProviderOtp("Invalid or expired OTP.")
            raise OtpProviderError("OTP provider is temporarily unavailable")
        body = self._json_body(response)
        data = body.get("data") if isinstance(body.get("data"), dict) else {}
        code = self._response_code(body)
        if code == "200" and data.get("verificationStatus") == "VERIFICATION_COMPLETED":
            return
        if code in {"505", "700", "702", "703", "705", "800"}:
            raise InvalidProviderOtp("Invalid or expired OTP.")
        raise OtpProviderError("OTP provider is temporarily unavailable")


def get_otp_provider(provider_name: str | None = None) -> OtpProvider:
    provider = provider_name or get_auth_settings().otp_provider
    if provider == "console":
        return ConsoleOtpProvider()
    if provider == "messagecentral":
        return MessageCentralOtpProvider()
    raise OtpProviderError("Unsupported OTP provider")


def generate_otp() -> str:
    return f"{secrets.randbelow(10 ** OTP_LENGTH):0{OTP_LENGTH}d}"


def create_otp_challenge(
    mobile: str,
    database_path: str | Path = DATABASE_PATH,
    provider: OtpProvider | None = None,
    request_ip: str = "unknown",
) -> dict[str, str]:
    normalized = normalize_indian_mobile(mobile)
    delivery = provider or get_otp_provider()
    hashed_phone = phone_hmac(normalized)
    hashed_ip = _ip_hmac(request_ip or "unknown")
    selected_provider = provider or get_otp_provider()
    settings = get_auth_settings()
    now_dt = datetime.now(timezone.utc)
    now = _timestamp(now_dt)
    with transaction(database_path, immediate=True) as connection:
        recent = connection.execute(
            """SELECT created_at FROM auth_otp_challenges
               WHERE phone_hash = ? AND provider = ? AND consumed_at IS NULL
               ORDER BY created_at DESC LIMIT 1""",
            (hashed_phone, selected_provider.name),
        ).fetchone()
        if recent and datetime.fromisoformat(recent["created_at"]) > now_dt - timedelta(seconds=settings.otp_resend_cooldown_seconds):
            raise AuthError("Please wait before requesting another OTP.", 429)
        window_start = _timestamp(now_dt - timedelta(minutes=OTP_RATE_WINDOW_MINUTES))
        mobile_requests = connection.execute(
            "SELECT COUNT(*) AS total FROM auth_otp_challenges "
            "WHERE phone_hash = ? AND provider = ? AND created_at >= ?",
            (hashed_phone, selected_provider.name, window_start),
        ).fetchone()["total"]
        ip_requests = connection.execute(
            "SELECT COUNT(*) AS total FROM auth_otp_challenges "
            "WHERE request_ip_hash = ? AND provider = ? AND created_at >= ?",
            (hashed_ip, selected_provider.name, window_start),
        ).fetchone()["total"]
        if mobile_requests >= OTP_REQUESTS_PER_MOBILE or ip_requests >= OTP_REQUESTS_PER_IP:
            raise AuthError("Too many OTP requests. Please try again later.", 429)
        identity = connection.execute(
            "SELECT vendor_id FROM vendor_auth_identities WHERE phone_hash = ?",
            (hashed_phone,),
        ).fetchone()
        purpose = "VENDOR_LOGIN" if identity else "NEW_VENDOR_REGISTRATION"
        challenge_id = f"OTP_{uuid.uuid4().hex}"
        # Reserve the challenge before delivery. Provider failures remove it so
        # they neither trigger cooldown nor leave a verifiable orphan record.
        connection.execute(
            """INSERT INTO auth_otp_challenges
               (challenge_id, phone_hash, request_ip_hash, mobile_last4, provider,
                purpose, otp_hash, expires_at,
                attempt_count, max_attempts, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)""",
            (
                challenge_id,
                hashed_phone,
                hashed_ip,
                normalized[-4:],
                selected_provider.name,
                purpose,
                _otp_hash(challenge_id, secrets.token_urlsafe(32)),
                _timestamp(now_dt + timedelta(minutes=settings.otp_expiry_minutes)),
                settings.otp_max_attempts,
                now,
            ),
        )
    try:
        issued_hash = selected_provider.issue_otp(normalized, challenge_id)
    except Exception:
        with transaction(database_path, immediate=True) as connection:
            connection.execute(
                "DELETE FROM auth_otp_challenges WHERE challenge_id = ? AND consumed_at IS NULL",
                (challenge_id,),
            )
        raise
    with transaction(database_path, immediate=True) as connection:
        connection.execute(
            "UPDATE auth_otp_challenges SET otp_hash = ? WHERE challenge_id = ?",
            (issued_hash, challenge_id),
        )
    return {"challenge_id": challenge_id, "next_step": "VERIFY_OTP"}


def _create_session(
    connection,
    role: str,
    *,
    vendor_id: str | None = None,
    admin_id: str | None = None,
    new_vendor_phone_hash: str | None = None,
    mobile_last4: str | None = None,
) -> tuple[str, dict]:
    token = secrets.token_urlsafe(32)
    session_id = f"SES_{uuid.uuid4().hex}"
    now_dt = datetime.now(timezone.utc)
    connection.execute(
        """INSERT INTO auth_sessions
           (session_id, session_token_hash, role, vendor_id, admin_id,
            new_vendor_phone_hash, mobile_last4, created_at, expires_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            session_id,
            _token_hash(token),
            role,
            vendor_id,
            admin_id,
            new_vendor_phone_hash,
            mobile_last4,
            _timestamp(now_dt),
            _timestamp(now_dt + timedelta(hours=SESSION_EXPIRY_HOURS)),
        ),
    )
    row = connection.execute("SELECT * FROM auth_sessions WHERE session_id = ?", (session_id,)).fetchone()
    return token, dict(row)


def verify_otp_challenge(
    challenge_id: str,
    otp: str,
    mobile: str | None = None,
    database_path: str | Path = DATABASE_PATH,
) -> tuple[str, dict]:
    if not re.fullmatch(rf"[0-9]{{{OTP_LENGTH}}}", (otp or "").strip()):
        raise AuthError(f"Enter the {OTP_LENGTH}-digit OTP.", 422)
    now_dt = datetime.now(timezone.utc)
    now = _timestamp(now_dt)
    with transaction(database_path, immediate=True) as connection:
        challenge = connection.execute(
            "SELECT * FROM auth_otp_challenges WHERE challenge_id = ?", (challenge_id,)
        ).fetchone()
        if challenge is None:
            raise AuthError("Invalid or expired OTP challenge.")
        if challenge["consumed_at"] is not None:
            raise AuthError("This OTP has already been used.")
        if datetime.fromisoformat(challenge["expires_at"]) <= now_dt:
            raise AuthError("This OTP has expired.")
        if challenge["attempt_count"] >= challenge["max_attempts"]:
            raise AuthError("Maximum OTP attempts exceeded.", 429)
        provider_name = challenge.get("provider") or "console"
        if mobile is None and provider_name == "messagecentral":
            raise AuthError("Mobile number is required to verify this OTP.", 422)
        normalized = normalize_indian_mobile(mobile) if mobile is not None else ""
        if normalized and not hmac.compare_digest(phone_hmac(normalized), challenge["phone_hash"]):
            raise AuthError("Invalid or expired OTP challenge.")
        provider = get_otp_provider(provider_name)
        try:
            provider.verify_otp(
                normalized, challenge_id, otp.strip(), challenge["otp_hash"]
            )
        except InvalidProviderOtp:
            connection.execute(
                "UPDATE auth_otp_challenges SET attempt_count = attempt_count + 1 WHERE challenge_id = ?",
                (challenge_id,),
            )
            # Failed attempts are security state and must survive the raised error.
            connection.commit()
            if challenge["attempt_count"] + 1 >= challenge["max_attempts"]:
                raise AuthError("Maximum OTP attempts exceeded.", 429)
            raise AuthError("Invalid or expired OTP.")
        connection.execute(
            "UPDATE auth_otp_challenges SET consumed_at = ? WHERE challenge_id = ?", (now, challenge_id)
        )
        identity = connection.execute(
            "SELECT * FROM vendor_auth_identities WHERE phone_hash = ?", (challenge["phone_hash"],)
        ).fetchone()
        if identity:
            connection.execute(
                """UPDATE vendor_auth_identities
                   SET is_verified = 1, mobile_last4 = ?, updated_at = ?
                   WHERE identity_id = ?""",
                (challenge["mobile_last4"], now, identity["identity_id"]),
            )
            return _create_session(connection, "VENDOR", vendor_id=identity["vendor_id"],
                                   mobile_last4=challenge["mobile_last4"])
        return _create_session(
            connection,
            "NEW_VENDOR_ONBOARDING",
            new_vendor_phone_hash=challenge["phone_hash"],
            mobile_last4=challenge["mobile_last4"],
        )


def create_admin_session(
    username: str,
    password: str,
    database_path: str | Path = DATABASE_PATH,
) -> tuple[str, dict]:
    settings = get_auth_settings()
    expected_user = settings.nmc_admin_username
    expected_password = settings.nmc_admin_password
    valid = hmac.compare_digest(username, expected_user) and hmac.compare_digest(password, expected_password)
    if not valid:
        raise AuthError("Invalid officer credentials.")
    with transaction(database_path, immediate=True) as connection:
        return _create_session(connection, "ADMIN", admin_id=username)


def get_session(token: str | None, database_path: str | Path = DATABASE_PATH) -> dict | None:
    if not token:
        return None
    connection = connect(database_path)
    try:
        row = connection.execute(
            """SELECT * FROM auth_sessions
               WHERE session_token_hash = ? AND revoked_at IS NULL""",
            (_token_hash(token),),
        ).fetchone()
        if row is None or datetime.fromisoformat(row["expires_at"]) <= datetime.now(timezone.utc):
            return None
        return dict(row)
    finally:
        connection.close()


def revoke_session(token: str | None, database_path: str | Path = DATABASE_PATH) -> None:
    if not token:
        return
    with transaction(database_path, immediate=True) as connection:
        connection.execute(
            "UPDATE auth_sessions SET revoked_at = ? WHERE session_token_hash = ? AND revoked_at IS NULL",
            (utc_now(), _token_hash(token)),
        )


def bind_onboarding_session(
    session_id: str,
    vendor_id: str,
    database_path: str | Path = DATABASE_PATH,
) -> None:
    now = utc_now()
    with transaction(database_path, immediate=True) as connection:
        session = connection.execute(
            "SELECT * FROM auth_sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if session is None or session["role"] != "NEW_VENDOR_ONBOARDING":
            raise AuthError("A verified onboarding session is required.", 403)
        connection.execute(
            """INSERT INTO vendor_auth_identities
               (identity_id, vendor_id, phone_hash, mobile_last4, vendor_source, is_verified, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'OPERATIONAL', 1, ?, ?)""",
            (f"VID_{uuid.uuid4().hex}", vendor_id, session["new_vendor_phone_hash"],
             session.get("mobile_last4"), now, now),
        )
        connection.execute(
            """UPDATE auth_sessions
               SET role = 'VENDOR', vendor_id = ?, new_vendor_phone_hash = NULL
               WHERE session_id = ?""",
            (vendor_id, session_id),
        )


def cookie_secure() -> bool:
    return get_auth_settings().session_cookie_secure


def find_vendor_by_phone_hash(
    hashed_phone: str,
    database_path: str | Path = DATABASE_PATH,
) -> str | None:
    connection = connect(database_path)
    try:
        row = connection.execute(
            "SELECT vendor_id FROM vendor_auth_identities WHERE phone_hash = ?",
            (hashed_phone,),
        ).fetchone()
        return row["vendor_id"] if row is not None else None
    finally:
        connection.close()


def bind_verified_phone_hash(
    hashed_phone: str,
    vendor_id: str,
    database_path: str | Path = DATABASE_PATH,
) -> None:
    """Bind a WhatsApp-verified sender without ever persisting the plaintext phone."""
    now = utc_now()
    with transaction(database_path, immediate=True) as connection:
        existing = connection.execute(
            "SELECT vendor_id FROM vendor_auth_identities WHERE phone_hash = ?",
            (hashed_phone,),
        ).fetchone()
        if existing is not None:
            if existing["vendor_id"] != vendor_id:
                raise AuthError("This verified mobile identity is already linked.", 409)
            return
        connection.execute(
            """INSERT INTO vendor_auth_identities
               (identity_id, vendor_id, phone_hash, vendor_source, is_verified, created_at, updated_at)
               VALUES (?, ?, ?, 'OPERATIONAL', 1, ?, ?)""",
            (f"VID_{uuid.uuid4().hex}", vendor_id, hashed_phone, now, now),
        )
