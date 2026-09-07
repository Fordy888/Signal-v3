from __future__ import annotations

import unittest
from unittest.mock import patch

from resend.exceptions import ValidationError

from src.delivery import DeliveryRejectedError, DeliveryUncertainError, send_brief


class RegistryDeliveryBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.env = {
            "RESEND_API_KEY": "test-key",
            "RESEND_FROM_EMAIL": "signal@signal.dtlc.ai",
        }

    @patch("src.delivery.resend.Emails.send", return_value={"id": "provider-1"})
    def test_confirmed_provider_id_is_returned(self, _mock_send) -> None:
        with patch.dict("os.environ", self.env, clear=True):
            result = send_brief(
                "<!DOCTYPE html><html><body>Signal</body></html>",
                recipient_email="reader@example.com",
                idempotency_key="registry-key",
                require_message_id=True,
                raise_on_failure=True,
            )
        self.assertEqual("provider-1", result)

    def test_missing_configuration_is_known_rejection(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(DeliveryRejectedError):
                send_brief(
                    "<!DOCTYPE html><html><body>Signal</body></html>",
                    recipient_email="reader@example.com",
                    require_message_id=True,
                    raise_on_failure=True,
                )

    @patch("src.delivery.resend.Emails.send")
    def test_provider_validation_error_is_known_rejection(self, mock_send) -> None:
        mock_send.side_effect = ValidationError(
            message="invalid recipient",
            error_type="validation_error",
            code=422,
        )
        with patch.dict("os.environ", self.env, clear=True):
            with self.assertRaises(DeliveryRejectedError):
                send_brief(
                    "<!DOCTYPE html><html><body>Signal</body></html>",
                    recipient_email="reader@example.com",
                    require_message_id=True,
                    raise_on_failure=True,
                )

    @patch("src.delivery.resend.Emails.send", side_effect=RuntimeError("timeout"))
    def test_transport_exception_is_uncertain(self, _mock_send) -> None:
        with patch.dict("os.environ", self.env, clear=True):
            with self.assertRaises(DeliveryUncertainError):
                send_brief(
                    "<!DOCTYPE html><html><body>Signal</body></html>",
                    recipient_email="reader@example.com",
                    require_message_id=True,
                    raise_on_failure=True,
                )

    @patch("src.delivery.resend.Emails.send", return_value={})
    def test_missing_provider_message_id_is_uncertain(self, _mock_send) -> None:
        with patch.dict("os.environ", self.env, clear=True):
            with self.assertRaises(DeliveryUncertainError):
                send_brief(
                    "<!DOCTYPE html><html><body>Signal</body></html>",
                    recipient_email="reader@example.com",
                    require_message_id=True,
                    raise_on_failure=True,
                )


if __name__ == "__main__":
    unittest.main()
