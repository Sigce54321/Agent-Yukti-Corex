"""Mocked sandbox lifecycle and bounded-output regressions; no Docker runs."""

import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from sandbox import container_runner as runner


class BoundedOutputTests(unittest.TestCase):
    def process(self, stdout=b"", stderr=b"", code=0):
        process = Mock()
        process.stdout = io.BytesIO(stdout)
        process.stderr = io.BytesIO(stderr)
        process.returncode = code
        return process

    def test_preserves_both_streams_and_nonzero_exit(self):
        process = self.process(b"test output\n", b"diagnostic\xff", 1)
        with patch.object(runner.subprocess, "Popen", return_value=process) as popen:
            result = runner._docker(["container", "start", "--attach", "managed"], 120)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "test output\n")
        self.assertEqual(result.stderr, "diagnostic\ufffd")
        process.kill.assert_not_called()
        process.wait.assert_called_once_with(timeout=120)
        self.assertEqual(popen.call_args.args[0][0], "docker")
        self.assertNotIn("shell", popen.call_args.kwargs)
        self.assertNotIn("capture_output", popen.call_args.kwargs)

    def test_exact_combined_limit_is_allowed(self):
        process = self.process(b"a" * 6, b"b" * 4)
        with patch.object(runner, "MAX_OUTPUT_BYTES", 10), patch.object(runner.subprocess, "Popen", return_value=process):
            result = runner._docker(["info"], 30)
        self.assertEqual(len(result.stdout) + len(result.stderr), 10)
        process.kill.assert_not_called()

    def test_either_stream_or_combined_overflow_is_error(self):
        for stdout, stderr in ((b"a" * 11, b""), (b"", b"b" * 11), (b"a" * 6, b"b" * 5)):
            with self.subTest(stdout=len(stdout), stderr=len(stderr)):
                process = self.process(stdout, stderr)
                with patch.object(runner, "MAX_OUTPUT_BYTES", 10), patch.object(runner.subprocess, "Popen", return_value=process):
                    with self.assertRaises(runner._OutputCaptureError):
                        runner._docker(["info"], 30)
                self.assertTrue(process.kill.called)

    def test_timeout_retains_only_bounded_partial_output_and_reaps_client(self):
        process = self.process(b"partial", b"diagnostic")
        process.wait.side_effect = [subprocess.TimeoutExpired("docker", 2), 0]
        with patch.object(runner.subprocess, "Popen", return_value=process):
            with self.assertRaises(subprocess.TimeoutExpired) as raised:
                runner._docker(["info"], 2)
        self.assertEqual(raised.exception.stdout, "partial")
        self.assertEqual(raised.exception.stderr, "diagnostic")
        process.kill.assert_called_once()
        self.assertEqual(process.wait.call_count, 2)

    def test_large_output_is_read_in_chunks_not_all_at_once(self):
        class CountingStream(io.BytesIO):
            def read(self, size=-1):
                self_sizes.append(size)
                return super().read(size)

        self_sizes = []
        process = self.process()
        process.stdout = CountingStream(b"a" * 100000)
        with patch.object(runner, "MAX_OUTPUT_BYTES", 10), patch.object(runner.subprocess, "Popen", return_value=process):
            with self.assertRaises(runner._OutputCaptureError):
                runner._docker(["info"], 30)
        self.assertTrue(self_sizes)
        self.assertTrue(all(0 < size <= runner._READ_CHUNK_BYTES for size in self_sizes))


class LifecycleTests(unittest.TestCase):
    def run_mocked(self, responses, cleaned=True):
        with tempfile.TemporaryDirectory() as directory:
            workspaces = Path(directory).resolve() / "workspaces"
            source = workspaces / "source"
            source.mkdir(parents=True)
            with (
                patch.object(runner.security, "WORKSPACES_ROOT", workspaces),
                patch.object(runner.security, "PROJECT_ROOT", Path(directory).resolve()),
                patch.object(runner, "_docker", side_effect=responses) as docker,
                patch.object(runner.docker_manager, "stop_and_remove_container", return_value=cleaned) as cleanup,
            ):
                result = runner.run_in_container(str(source), "python", ["python", "-m", "pytest"])
        return result, docker, cleanup

    def test_create_timeout_cleans_up_by_unique_managed_name(self):
        result, docker, cleanup = self.run_mocked([
            subprocess.CompletedProcess([], 0, "[]", ""),
            subprocess.TimeoutExpired("docker create", 30, output="partial"),
        ])
        creation_args = docker.call_args_list[1].args[0]
        name = creation_args[creation_args.index("--name") + 1]
        cleanup.assert_called_once_with(name)
        self.assertTrue(name.startswith("yuktic-orex-"))
        self.assertIn(f"{runner.docker_manager.MANAGED_LABEL}=true", creation_args)
        self.assertFalse(result["success"])
        self.assertTrue(result["timed_out"])
        self.assertIsNone(result["container_id"])

    def test_create_timeout_remains_failure_if_cleanup_cannot_confirm_removal(self):
        result, _, cleanup = self.run_mocked([
            subprocess.CompletedProcess([], 0, "[]", ""),
            subprocess.TimeoutExpired("docker create", 30),
        ], cleaned=False)
        cleanup.assert_called_once()
        self.assertFalse(result["success"])
        self.assertTrue(result["timed_out"])

    def test_execution_output_overflow_is_error_and_cleans_up(self):
        result, _, cleanup = self.run_mocked([
            subprocess.CompletedProcess([], 0, "[]", ""),
            subprocess.CompletedProcess([], 0, "a" * 64, ""),
            runner._OutputCaptureError("output capture limit exceeded"),
        ])
        cleanup.assert_called_once()
        self.assertFalse(result["success"])
        self.assertFalse(result["timed_out"])
        self.assertIsNone(result["exit_code"])
        self.assertIn("capture limit", result["logs"])

    def test_no_cleanup_before_creation_was_attempted(self):
        result, _, cleanup = self.run_mocked([subprocess.CompletedProcess([], 1, "", "missing image")])
        cleanup.assert_not_called()
        self.assertFalse(result["success"])
