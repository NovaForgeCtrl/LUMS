import importlib.util
import json
import ssl
import tempfile
from pathlib import Path
from unittest.mock import patch

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

MODULE_PATH = Path(__file__).resolve().parents[1] / "agent" / "telemetry.py"
SPEC = importlib.util.spec_from_file_location("lums_telemetry_agent", MODULE_PATH)
agent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(agent)


class TelemetryAgentTests(unittest.TestCase):
    def test_cpu_percentage(self):
        self.assertEqual(
            agent.calculate_cpu_percent((100, 40), (200, 80)),
            60.0,
        )

    def test_cpu_percentage_rejects_bad_delta(self):
        with self.assertRaises(RuntimeError):
            agent.calculate_cpu_percent((100, 40), (100, 40))

    def test_read_cpu_counters(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            path = Path(directory) / "stat"
            path.write_text("cpu 100 2 30 400 8 1 2 3 4 5\ncpu0 1 2\n")
            self.assertEqual(agent.read_cpu_counters(path), (555, 408))

    def test_memory_values_are_validated(self):
        sample = agent.build_sample(12.5, {
            "memory_percent": 25.0,
            "memory_total_bytes": 1000,
            "memory_available_bytes": 750,
        })
        self.assertEqual(sample["cpu_percent"], 12.5)
        self.assertEqual(sample["memory_total_bytes"], 1000)

    def test_invalid_cpu_is_rejected(self):
        for value in (-1, 101, float("nan"), True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                agent.build_sample(value, {
                    "memory_percent": 25.0,
                    "memory_total_bytes": 1000,
                    "memory_available_bytes": 750,
                })

    def test_invalid_memory_is_rejected(self):
        with self.assertRaises(ValueError):
            agent.build_sample(10, {
                "memory_percent": 20.0,
                "memory_total_bytes": 100,
                "memory_available_bytes": 101,
            })

    def test_unset_ca_file_uses_system_trust(self):
        with patch.object(
            agent.ssl, "create_default_context"
        ) as create_context:
            sentinel = object()
            create_context.return_value = sentinel

            result = agent.make_ssl_context(None)

            self.assertIs(result, sentinel)
            create_context.assert_called_once_with()

    def test_unreadable_configured_ca_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            ca_file = Path(directory) / "ca.crt"
            ca_file.write_text("placeholder", encoding="utf-8")

            with patch.object(
                agent.ssl,
                "create_default_context",
                side_effect=OSError("permission denied"),
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "Unable to load configured LUMS_CA_FILE"
                ):
                    agent.make_ssl_context(str(ca_file))

    def test_configured_ca_file_must_exist(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing-ca.crt"
            with self.assertRaisesRegex(RuntimeError, "does not exist"):
                agent.make_ssl_context(str(missing))

    def test_system_ca_store_is_used_when_no_ca_is_configured(self):
        with patch.object(
            agent.ssl, "create_default_context"
        ) as create_context:
            sentinel = object()
            create_context.return_value = sentinel

            result = agent.make_ssl_context("")

            self.assertIs(result, sentinel)
            create_context.assert_called_once_with()

    def test_configured_ca_file_is_loaded(self):
        with tempfile.TemporaryDirectory() as directory:
            ca_file = Path(directory) / "ca.crt"
            ca_file.write_text("test certificate placeholder", encoding="utf-8")

            with patch.object(
                agent.ssl, "create_default_context"
            ) as create_context:
                sentinel = object()
                create_context.return_value = sentinel

                result = agent.make_ssl_context(str(ca_file))

                self.assertIs(result, sentinel)
                create_context.assert_called_once_with(cafile=str(ca_file))

    def test_token_is_required(self):
        with self.assertRaisesRegex(RuntimeError, "LUMS_TOKEN"):
            agent.send_sample(
                "https://lums.example",
                "",
                {"cpu_percent": 1},
                ssl.create_default_context(),
            )

    def test_non_local_http_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "HTTPS"):
            agent.send_sample(
                "http://lums.example",
                "test-token",
                {"cpu_percent": 1},
                ssl.create_default_context(),
            )

    def test_https_posts_bearer_token_and_json(self):
        response = MagicMock()
        response.status = 200
        response.__enter__.return_value = response
        opener = MagicMock(return_value=response)

        agent.send_sample(
            "https://lums.example/",
            "test-token",
            {"cpu_percent": 10.0},
            ssl.create_default_context(),
            opener=opener,
        )

        request = opener.call_args.args[0]
        self.assertEqual(request.full_url, "https://lums.example/api/telemetry")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-token")
        self.assertEqual(json.loads(request.data), {"cpu_percent": 10.0})
        opener.assert_called_once()

    def test_local_http_is_allowed(self):
        response = MagicMock()
        response.status = 200
        response.__enter__.return_value = response
        opener = MagicMock(return_value=response)

        agent.send_sample(
            "http://127.0.0.1:5000",
            "test-token",
            {"cpu_percent": 10.0},
            ssl.create_default_context(),
            opener=opener,
        )
        opener.assert_called_once()

    def test_network_counters_skip_loopback_and_sum_interfaces(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dev"
            path.write_text(
                "Inter-|   Receive\n face |bytes\n"
                "    lo: 999 1 0 0 0 0 0 0 999 1 0 0 0 0 0 0\n"
                "  eth0: 100 1 0 0 0 0 0 0 40 1 0 0 0 0 0 0\n"
                "  wlan0: 50 1 0 0 0 0 0 0 10 1 0 0 0 0 0 0\n",
                encoding="ascii",
            )
            self.assertEqual(
                agent.read_network_counters(str(path)),
                {"network_rx_bytes": 150, "network_tx_bytes": 50},
            )

    def test_build_sample_includes_valid_network_counters(self):
        memory = {
            "memory_percent": 50.0,
            "memory_total_bytes": 1000,
            "memory_available_bytes": 500,
        }
        sample = agent.build_sample(
            10.0, memory,
            {"network_rx_bytes": 1, "network_tx_bytes": 2},
        )
        self.assertEqual(sample["network_tx_bytes"], 2)
        with self.assertRaises(ValueError):
            agent.build_sample(
                10.0, memory,
                {"network_rx_bytes": -1, "network_tx_bytes": 2},
            )


if __name__ == "__main__":
    unittest.main()
