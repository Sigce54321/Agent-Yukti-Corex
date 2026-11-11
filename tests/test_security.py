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
                            user_args = [arg for arg in arguments if arg.startswith("--user=")]
                            self.assertEqual(len(user_args), 1)
                            uid, gid = map(int, user_args[0].split("=", 1)[1].split(":"))
                            self.assertGreater(uid, 0)
                            self.assertGreater(gid, 0)
                            image_index = arguments.index(f"yuktic-orex-{'browser' if language in ('html', 'css') else language}:latest")
                            self.assertLess(arguments.index(user_args[0]), image_index)
                            for option in security.get_container_security_options()["docker_args"]:
                                self.assertIn(option, arguments[:image_index])
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

    def test_non_root_security_options_keep_restrictions_and_writable_caches(self):
        with patch.object(security, "_container_identity", return_value=(1234, 5678)):
            options = security.get_container_security_options()
        args = options["docker_args"]
        self.assertIn("--user=1234:5678", args)
        for flag in (
            "--network=none", "--privileged=false", "--cap-drop=ALL",
            "--security-opt=no-new-privileges:true", "--read-only",
            "--cpus=1", "--memory=512m", "--memory-swap=512m", "--pids-limit=128",
            "--tmpfs=/tmp:rw,noexec,nosuid,nodev,size=64m,mode=1777",
            "--env=HOME=/tmp", "--env=TMPDIR=/tmp",
            "--env=XDG_CACHE_HOME=/tmp/.cache", "--env=npm_config_cache=/tmp/npm-cache",
            "--env=MAVEN_CONFIG=/tmp/.m2",
        ):
            self.assertIn(flag, args)
        self.assertTrue(any(arg.startswith("--env=JAVA_TOOL_OPTIONS=") and "-Duser.home=/tmp" in arg for arg in args))
        self.assertEqual(options["timeout_seconds"], 120)

    def test_root_host_identity_falls_back_to_nonzero_ids(self):
        with patch.object(security.os, "getuid", return_value=0, create=True), patch.object(security.os, "getgid", return_value=0, create=True):
            self.assertEqual(security._container_identity(), (1000, 1000))

    def test_unprivileged_host_identity_is_preserved(self):
        with patch.object(security.os, "getuid", return_value=1234, create=True), patch.object(security.os, "getgid", return_value=5678, create=True):
            self.assertEqual(security._container_identity(), (1234, 5678))

    def test_root_host_chowns_only_the_generated_copy(self):
        with patch.object(security.os, "getuid", return_value=0, create=True), patch.object(security.os, "getgid", return_value=0, create=True), patch.object(security.os, "chown", create=True) as chown:
            with security.sanitized_workspace(str(self.source)) as task:
                calls = list(chown.call_args_list)
                self.assertTrue(calls)
                for call in calls:
                    path, uid, gid = call.args
                    self.assertTrue(path == task or path.is_relative_to(task))
                    self.assertFalse(path == self.source or path.is_relative_to(self.source))
                    self.assertEqual((uid, gid), (1000, 1000))
                    self.assertFalse(call.kwargs["follow_symlinks"])
