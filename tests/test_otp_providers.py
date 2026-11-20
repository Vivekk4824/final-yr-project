import os
import unittest
from unittest.mock import patch

import httpx

from backend.core.config import ConfigurationError, get_auth_settings
from backend.services.authentication import (
    MESSAGECENTRAL_SEND_URL,
    MESSAGECENTRAL_TOKEN_URL,
    MESSAGECENTRAL_VERIFY_URL,
    InvalidProviderOtp,
    MessageCentralOtpProvider,
    OtpProviderError,
    generate_otp,
)


class MessageCentralOtpProviderTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {
            "APP_ENV": "test",
            "AUTH_HMAC_SECRET": "provider-test-secret",
            "SESSION_COOKIE_SECURE": "false",
            "OTP_PROVIDER": "messagecentral",
            "OTP_DEBUG": "false",
            "MESSAGECENTRAL_CUSTOMER_ID": "C-TEST123",
            "MESSAGECENTRAL_AUTH_TOKEN": "",
            "MESSAGECENTRAL_AUTH_KEY": "base64-test-key",
            "MESSAGECENTRAL_EMAIL": "otp@example.test",
            "OTP_EXPIRY_MINUTES": "5",
            "OTP_RESEND_COOLDOWN_SECONDS": "60",
            "OTP_MAX_ATTEMPTS": "5",
            "NMC_ADMIN_USERNAME": "officer",
            "NMC_ADMIN_PASSWORD": "password",
        }, clear=False)
        self.environment.start()

    def tearDown(self):
        self.environment.stop()

    @staticmethod
    def client(handler):
        return httpx.Client(transport=httpx.MockTransport(handler))

    @staticmethod
    def token_response():
        return httpx.Response(200, json={"status": 200, "token": "test-auth-token"})

    def test_send_requests_provider_generated_four_digit_otp(self):
        requests = []

        def handler(request):
            requests.append(request)
            if str(request.url).startswith(MESSAGECENTRAL_TOKEN_URL):
                return self.token_response()
            return httpx.Response(200, json={
                "responseCode": 200,
                "message": "SUCCESS",
                "data": {"verificationId": 2949, "responseCode": "200"},
            })

        with self.client(handler) as client:
            reference = MessageCentralOtpProvider(client).issue_otp(
                "9876543210", "OTP_challenge"
            )
        self.assertEqual(reference, "2949")
        self.assertEqual(requests[0].method, "GET")
        self.assertTrue(str(requests[0].url).startswith(MESSAGECENTRAL_TOKEN_URL))
        self.assertEqual(requests[0].url.params["customerId"], "C-TEST123")
        self.assertEqual(requests[0].url.params["key"], "base64-test-key")
        self.assertEqual(requests[0].url.params["email"], "otp@example.test")
        self.assertEqual(requests[1].method, "POST")
        self.assertTrue(str(requests[1].url).startswith(MESSAGECENTRAL_SEND_URL))
        self.assertEqual(requests[1].headers["authToken"], "test-auth-token")
        self.assertEqual(requests[1].url.params["countryCode"], "91")
        self.assertEqual(requests[1].url.params["customerId"], "C-TEST123")
        self.assertEqual(requests[1].url.params["otpLength"], "4")
        self.assertEqual(requests[1].url.params["mobileNumber"], "9876543210")
        self.assertNotIn("code", requests[1].url.params)

    def test_dashboard_auth_token_is_used_directly_without_token_generation(self):
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(200, json={
                "responseCode": 200,
                "message": "SUCCESS",
                "data": {"verificationId": 2949, "responseCode": "200"},
            })

        with patch.dict(os.environ, {
            "MESSAGECENTRAL_AUTH_TOKEN": "MC_dashboard-token",
            "MESSAGECENTRAL_AUTH_KEY": "",
        }):
            with self.client(handler) as client:
                reference = MessageCentralOtpProvider(client).issue_otp(
                    "9876543210", "OTP_challenge"
                )
        self.assertEqual(reference, "2949")
        self.assertEqual(len(requests), 1)
        self.assertTrue(str(requests[0].url).startswith(MESSAGECENTRAL_SEND_URL))
        self.assertEqual(requests[0].headers["authToken"], "MC_dashboard-token")

    def test_dashboard_token_in_legacy_key_variable_is_recognized(self):
        def handler(request):
            self.assertTrue(str(request.url).startswith(MESSAGECENTRAL_SEND_URL))
            self.assertEqual(request.headers["authToken"], "MC_legacy-token")
            return httpx.Response(200, json={
                "responseCode": 200,
                "data": {"verificationId": 2949, "responseCode": "200"},
            })

        with patch.dict(os.environ, {
            "MESSAGECENTRAL_AUTH_TOKEN": "",
            "MESSAGECENTRAL_AUTH_KEY": "MC_legacy-token",
        }):
            with self.client(handler) as client:
                MessageCentralOtpProvider(client).issue_otp(
                    "9876543210", "OTP_challenge"
                )

    def test_verify_success_and_incorrect_otp(self):
        def handler(request):
            if str(request.url).startswith(MESSAGECENTRAL_TOKEN_URL):
                return self.token_response()
            self.assertTrue(str(request.url).startswith(MESSAGECENTRAL_VERIFY_URL))
            self.assertEqual(request.url.params["verificationId"], "2949")
            if request.url.params["code"] == "1234":
                return httpx.Response(200, json={
                    "responseCode": 200,
                    "data": {
                        "responseCode": "200",
                        "verificationStatus": "VERIFICATION_COMPLETED",
                    },
                })
            return httpx.Response(200, json={
                "responseCode": 702,
                "data": {"responseCode": "702", "verificationStatus": "FAILED"},
            })

        with self.client(handler) as client:
            provider = MessageCentralOtpProvider(client)
            provider.verify_otp("9876543210", "OTP_a", "1234", "2949")
            with self.assertRaises(InvalidProviderOtp):
                provider.verify_otp("9876543210", "OTP_a", "0000", "2949")

    def test_provider_authentication_and_send_failures_are_safe(self):
        with self.client(lambda request: httpx.Response(401)) as client:
            with self.assertRaisesRegex(OtpProviderError, "authentication"):
                MessageCentralOtpProvider(client).issue_otp("9876543210", "OTP_a")

        def send_failure(request):
            if str(request.url).startswith(MESSAGECENTRAL_TOKEN_URL):
                return self.token_response()
            return httpx.Response(503)

        with self.client(send_failure) as client:
            with self.assertRaises(OtpProviderError):
                MessageCentralOtpProvider(client).issue_otp("9876543210", "OTP_b")

    def test_missing_credentials_fail_without_console_fallback(self):
        with patch.dict(os.environ, {
            "OTP_PROVIDER": "messagecentral",
            "MESSAGECENTRAL_CUSTOMER_ID": "",
            "MESSAGECENTRAL_AUTH_TOKEN": "",
            "MESSAGECENTRAL_AUTH_KEY": "",
        }):
            with self.assertRaises(ConfigurationError):
                get_auth_settings()

    def test_console_generator_is_always_four_digits(self):
        for _ in range(100):
            self.assertRegex(generate_otp(), r"^[0-9]{4}$")


if __name__ == "__main__":
    unittest.main()
