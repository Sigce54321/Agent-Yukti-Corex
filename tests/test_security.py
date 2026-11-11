"""Disposable workspace isolation tests; Docker execution is always mocked."""

import json
from pathlib import Path
import stat
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from sandbox import security, container_runner as runner


class WorkspaceIsolationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name).resolve()
        self.workspaces = self.project / "workspaces"
        self.source = self.workspaces / "original"
        self.source.mkdir(parents=True)
        for name, value in (("PROJECT_ROOT", self.project), ("WORKSPACES_ROOT", self.workspaces)):
            patcher = patch.object(security, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        (self.source / "main.py").write_text("original", encoding="utf-8")

    def test_secrets_and_git_are_excluded_without_touching_originals(self):
        secrets = [".env", ".env.local", ".ENV.PRODUCTION", ".npmrc", ".netrc", "credentials.json", "id_rsa", "server.pem", "private.key"]
        for name in secrets:
            (self.source / name).write_text("secret", encoding="utf-8")
        for name in (".git", ".ssh", ".aws"):
            (self.source / name).mkdir()
            (self.source / name / "config").write_text("credential", encoding="utf-8")
        with security.sanitized_workspace(str(self.source)) as task:
            self.assertEqual(task.parent, self.workspaces)
            self.assertNotEqual(task, self.source)
            self.assertTrue(security.validate_workspace_path(str(task)))
            self.assertEqual([entry.name for entry in task.iterdir()], ["main.py"])
            (task / "main.py").write_text("changed by tests", encoding="utf-8")
            (task / "new-output").write_text("result", encoding="utf-8")
        self.assertFalse(task.exists())
        self.assertEqual((self.source / "main.py").read_text(encoding="utf-8"), "original")
        self.assertFalse((self.source / "new-output").exists())
        for name in secrets:
            self.assertEqual((self.source / name).read_text(encoding="utf-8"), "secret")
        self.assertTrue((self.source / ".git/config").exists())

    def test_cleanup_runs_on_copy_failure_and_execution_exception(self):
        for fail_copy in (True, False):
            with self.subTest(fail_copy=fail_copy):
                if fail_copy:
                    with patch.object(security, "_copy_sanitized", side_effect=ValueError("unsafe")):
                        with self.assertRaises(ValueError):
                            with security.sanitized_workspace(str(self.source)):
                                self.fail("Copy failure must not yield a task")
                else:
                    with self.assertRaises(RuntimeError):
                        with security.sanitized_workspace(str(self.source)):
                            raise RuntimeError("execution failed")
                self.assertEqual(list(self.workspaces.iterdir()), [self.source])

    def test_validation_rejects_secrets_and_unsafe_entries(self):
        (self.source / ".env.local").write_text("secret", encoding="utf-8")
        self.assertFalse(security.validate_workspace_path(str(self.source)))
        for mode, attributes, links in (
            (stat.S_IFLNK, 0, 1),
            (stat.S_IFDIR, 0x400, 1),  # Windows junction/reparse point
            (stat.S_IFSOCK, 0, 1),
            (stat.S_IFIFO, 0, 1),
            (stat.S_IFREG, 0, 2),  # Hard links must not share original data.
        ):
            with self.subTest(mode=mode, attributes=attributes):
                entry = Mock()
                entry.name = "unsafe"
                entry.lstat.return_value = SimpleNamespace(st_mode=mode, st_file_attributes=attributes, st_nlink=links)
                with self.assertRaises(ValueError):
                    security._plain_info(entry)

    def test_copied_tree_is_validated_before_yield(self):
        with patch.object(security, "validate_workspace_path", return_value=False) as validate:
            with self.assertRaises(ValueError):
                with security.sanitized_workspace(str(self.source)):
                    self.fail("Invalid copy must never be yielded")
        validate.assert_called_once()
        self.assertNotEqual(validate.call_args.args[0], str(self.source))
        self.assertEqual(list(self.workspaces.iterdir()), [self.source])

    def test_cleanup_refuses_a_replaced_generated_directory(self):
        context = security.sanitized_workspace(str(self.source))
        task = context.__enter__()
        allocated = task.stat()
        replacement = SimpleNamespace(st_dev=allocated.st_dev, st_ino=allocated.st_ino + 1)
        with patch.object(security, "_plain_info", return_value=replacement), patch.object(security.shutil, "rmtree") as remove:
            with self.assertRaises(ValueError):
                context.__exit__(None, None, None)
            remove.assert_not_called()
        self.assertTrue(self.source.exists())
        self.assertEqual((self.source / "main.py").read_text(encoding="utf-8"), "original")

    def test_original_root_and_external_paths_are_rejected(self):
        for path in (str(self.workspaces), str(self.project), str(self.source / ".."), str(self.workspaces / "missing")):
            with self.subTest(path=path), self.assertRaises((ValueError, OSError)):
                with security.sanitized_workspace(path):
                    self.fail("Unsafe path must not yield")

    def test_runner_mounts_only_copy_and_cleans_it_on_success_and_timeout(self):
        for language in ("python", "java", "javascript", "html", "css"):
            for timeout in (False, True):
                with self.subTest(language=language, timeout=timeout):
                    mounted = []

                    def docker(arguments, timeout_seconds):
                        if arguments[:2] == ["image", "inspect"]:
                            return subprocess.CompletedProcess(arguments, 0, "[]", "")
                        if arguments[:2] == ["container", "create"]:
                            mount = arguments[arguments.index("--mount") + 1]
                            self.assertTrue(mount.endswith(",target=/workspace"))
                            task = Path(mount[len("type=bind,source="):].split(",target=")[0])
                            mounted.append(task)
                            self.assertNotEqual(task, self.source)
                            self.assertTrue(security.validate_workspace_path(str(task)))
                            (task / "main.py").write_text("container mutation", encoding="utf-8")
                            if timeout:
                                raise subprocess.TimeoutExpired(arguments, timeout_seconds)
                            return subprocess.CompletedProcess(arguments, 0, "a" * 64, "")
                        if arguments[:2] == ["container", "start"]:
                            return subprocess.CompletedProcess(arguments, 0, "1 passed", "")
                        state = {"Status": "exited", "Error": "", "StartedAt": "2026-11-11", "ExitCode": 0}
                        return subprocess.CompletedProcess(arguments, 0, json.dumps(state), "")

                    with patch.object(runner, "_docker", side_effect=docker), patch.object(runner.docker_manager, "stop_and_remove_container", return_value=True) as cleanup:
                        result = runner.run_in_container(str(self.source), language, ["test-command"])
                    self.assertEqual(result["success"], not timeout)
                    self.assertEqual(result["timed_out"], timeout)
                    cleanup.assert_called_once()
                    self.assertEqual(len(mounted), 1)
                    self.assertFalse(mounted[0].exists())
                    self.assertEqual((self.source / "main.py").read_text(encoding="utf-8"), "original")

    def test_invalid_copy_never_reaches_docker(self):
        with patch.object(security, "validate_workspace_path", return_value=False), patch.object(runner, "_docker") as docker:
            result = runner.run_in_container(str(self.source), "python", ["python"])
        self.assertFalse(result["success"])
        docker.assert_not_called()
        self.assertTrue(self.source.exists())
