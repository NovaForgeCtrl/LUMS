import json
import unittest
from unittest.mock import Mock

from host_updater.agent import build_request, send_heartbeat


class HostUpdaterAgentTests(unittest.TestCase):
    def test_request_targets_only_local_heartbeat_endpoint(self):
        request = build_request(
            "http://127.0.0.1:5050/", "x" * 40,
            "dev", "test-host", "test heartbeat",
        )
        self.assertEqual(
            request.full_url,
            "http://127.0.0.1:5050/api/host-updater/heartbeat",
        )
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(
            request.get_header("Authorization"), "Bearer " + "x" * 40
        )
        payload = json.loads(request.data)
        self.assertEqual(payload["deployment"], "test-host")

    def test_rejects_non_loopback_url(self):
        with self.assertRaises(ValueError):
            build_request(
                "http://example.com:5050", "x" * 40,
                "dev", "test", "test",
            )

    def test_heartbeat_response_is_parsed(self):
        response = Mock()
        response.status = 200
        response.read.return_value = (
            b'{"status":"ok","update_execution_enabled":false}'
        )
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        opener = Mock(return_value=response)

        result = send_heartbeat(
            "http://127.0.0.1:5050", "x" * 40,
            "dev", "test-host", "test heartbeat", opener=opener,
        )

        self.assertEqual(result["status"], "ok")
        self.assertIs(result["update_execution_enabled"], False)
        opener.assert_called_once()

    def test_rejects_url_with_loopback_prefix_but_remote_host(self):
        with self.assertRaises(ValueError):
            build_request(
                "http://127.0.0.1:5050@evil.example",
                "x" * 40, "dev", "test", "test",
            )

    def test_rejects_non_loopback_https_host(self):
        with self.assertRaises(ValueError):
            build_request(
                "https://example.com:5050", "x" * 40,
                "dev", "test", "test",
            )


if __name__ == "__main__":
    unittest.main()
