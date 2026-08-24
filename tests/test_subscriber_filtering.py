import unittest

from src.subscribers import DELIVERY_EXCLUSIONS, filter_delivery_recipients


class SubscriberFilteringTests(unittest.TestCase):
    def test_excludes_only_known_test_and_bounced_addresses(self):
        genuine = {
            "email": "genuine.executive@example.org",
            "firstName": None,
        }
        subscribers = [
            genuine,
            *[
                {"email": email, "firstName": "Test"}
                for email in sorted(DELIVERY_EXCLUSIONS)
            ],
        ]

        filtered = filter_delivery_recipients(subscribers)

        self.assertEqual(filtered, [genuine])

    def test_email_matching_is_case_insensitive_and_whitespace_safe(self):
        filtered = filter_delivery_recipients(
            [
                {"email": "  TEST-OUTREACH-CHECK@EXAMPLE.COM  "},
                {"email": "real@dtlc.ai"},
            ]
        )

        self.assertEqual(filtered, [{"email": "real@dtlc.ai"}])


if __name__ == "__main__":
    unittest.main()

