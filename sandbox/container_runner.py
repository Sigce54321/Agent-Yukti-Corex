"""Run task commands in managed Docker containers without building images."""

import json
from pathlib import Path
import subprocess
import threading
import uuid

from . import docker_manager, security


MAX_OUTPUT_BYTES = 1024 * 1024
_READ_CHUNK_BYTES = 8192


class _OutputCaptureError(subprocess.SubprocessError):
    """Output was truncated or could not be captured reliably."""


def _docker(arguments, timeout):
    """Capture at most MAX_OUTPUT_BYTES across both pipes, without disk spooling."""
    command = ["docker", *arguments]
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    buffers = [bytearray(), bytearray()]
    lock = threading.Lock()
    capture_failed = threading.Event()

    def read_pipe(stream, index):
        try:
            while True:
                chunk = stream.read(_READ_CHUNK_BYTES)
                if not chunk:
                    break
                with lock:
                    remaining = MAX_OUTPUT_BYTES - sum(map(len, buffers))
                    buffers[index].extend(chunk[:remaining])
                    exceeded = len(chunk) > remaining
                if exceeded:
                    capture_failed.set()
                    process.kill()
                    break
        except OSError:
            capture_failed.set()
            try:
                process.kill()
            except OSError:
                pass
        finally:
            stream.close()

    readers = [
        threading.Thread(target=read_pipe, args=(stream, index), daemon=True)
        for index, stream in enumerate((process.stdout, process.stderr))
    ]
    for reader in readers:
        reader.start()
    expired = None
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired as error:
        expired = error
        process.kill()
        process.wait()
    finally:
        # A killed Docker client normally closes both pipes immediately. Do
        # not wait indefinitely if an inherited pipe unexpectedly remains open.
        for reader in readers:
            reader.join(timeout=1)
    with lock:
        stdout, stderr = (bytes(value).decode("utf-8", errors="replace") for value in buffers)
    if expired is not None:
        raise subprocess.TimeoutExpired(command, timeout, output=stdout, stderr=stderr)
    if capture_failed.is_set() or any(reader.is_alive() for reader in readers):
        raise _OutputCaptureError(
            f"Docker output exceeded the {MAX_OUTPUT_BYTES}-byte capture limit "
            "or could not be captured reliably; output is incomplete."
        )
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def _output(stdout, stderr):
    parts = []
    for value in (stdout, stderr):
        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="replace")
        if value:
            parts.append(value.rstrip())
    return "\n".join(parts)


def run_in_container(
    workspace_path: str,
    language: str,
    execution_command: list[str],
    timeout_seconds: int = 120,
) -> dict:
    """Execute an argument list in Docker and always attempt managed cleanup.

    success means Docker completed execution and reported a reliable exit code;
    callers must use exit_code to determine whether tests passed. The security
    policy caps execution at 120 seconds. Workspace contents must not be changed
    by other host processes during validation and execution.
    """
    result = {
        "success": False,
        "exit_code": None,
        "logs": "",
        "timed_out": False,
        "container_id": None,
    }

    def log(message):
        if message:
            result["logs"] = "\n".join(filter(None, (result["logs"], message)))

    image_type = (
        docker_manager.LANGUAGE_IMAGES.get(language.strip().lower())
        if isinstance(language, str) else None
    )
    if image_type is None:
        log("Unsupported language. Expected python, java, javascript, html, or css.")
        return result
    if (
        not isinstance(execution_command, list)
        or not execution_command
        or any(not isinstance(arg, str) or "\x00" in arg for arg in execution_command)
        or not execution_command[0].strip()
        or execution_command[0].startswith("-")
    ):
        log("execution_command must be a nonempty list of strings with a valid executable.")
        return result
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int) or timeout_seconds <= 0:
        log("timeout_seconds must be a positive integer.")
        return result
    if not security.validate_workspace_path(workspace_path):
        log("Workspace must be a safe existing task directory inside project workspaces/.")
        return result

    cleanup_name = None
    created = False
    try:
        supplied = Path(workspace_path)
        workspace = (supplied if supplied.is_absolute() else security.PROJECT_ROOT / supplied).resolve(strict=True)
        # Docker --mount uses commas as field separators even with shell=False.
        if "," in str(workspace) or not security.validate_workspace_path(str(workspace)):
            log("Workspace path cannot safely be used as a Docker bind mount.")
            return result
        options = security.get_container_security_options()
        execution_timeout = min(timeout_seconds, options["timeout_seconds"])
        image_name = f"yuktic-orex-{image_type}:latest"
        image = _docker(["image", "inspect", image_name], docker_manager.CLI_TIMEOUT)
        if image.returncode != 0:
            log(f"Local image {image_name} is missing or Docker cannot inspect it. No image was built or pulled.")
            log(_output(image.stdout, image.stderr))
            return result

        # A unique name permits cleanup even if create times out before returning
        # the ID. The shared cleanup helper verifies ownership before removal.
        cleanup_name = f"yuktic-orex-{uuid.uuid4().hex}"
        creation = _docker(
            [
                "container", "create", "--pull=never",
                "--name", cleanup_name,
                "--label", f"{docker_manager.MANAGED_LABEL}=true",
                *options["docker_args"],
                "--mount", f"type=bind,source={workspace},target=/workspace",
                "--workdir", "/workspace",
                "--entrypoint", execution_command[0],
                image_name, *execution_command[1:],
            ],
            docker_manager.CLI_TIMEOUT,
        )
        if creation.returncode != 0:
            log("Docker container creation failed.")
            log(_output(creation.stdout, creation.stderr))
            return result
        created = True
        container_id = creation.stdout.strip()
        if len(container_id) != 64 or any(c not in "0123456789abcdef" for c in container_id):
            log("Docker returned an invalid container ID.")
            return result
        result["container_id"] = container_id

        execution = _docker(
            ["container", "start", "--attach", container_id], execution_timeout
        )
        log(_output(execution.stdout, execution.stderr))
        inspection = _docker(
            ["container", "inspect", "--format", "{{json .State}}", container_id],
            docker_manager.CLI_TIMEOUT,
        )
        if inspection.returncode != 0:
            log("Docker could not verify the container exit state.")
            log(_output(inspection.stdout, inspection.stderr))
            return result
        state = json.loads(inspection.stdout)
        exit_code = state.get("ExitCode")
        if (
            state.get("Status") != "exited"
            or state.get("Error")
            or not state.get("StartedAt")
            or state["StartedAt"].startswith("0001-")
            or type(exit_code) is not int
            or execution.returncode != exit_code
        ):
            log(f"Docker execution failed or did not finish reliably: {state.get('Error') or state.get('Status')}.")
            return result
        result["exit_code"] = exit_code
        result["success"] = True
    except subprocess.TimeoutExpired as error:
        result["timed_out"] = True
        log(_output(error.stdout, error.stderr))
        log(f"Docker command timed out after {error.timeout} seconds.")
    except FileNotFoundError:
        log("Docker CLI or workspace was not found.")
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, AttributeError) as error:
        log(f"Docker execution error: {error}")
    finally:
        if cleanup_name is not None:
            cleaned = docker_manager.stop_and_remove_container(cleanup_name)
            if not cleaned and created:
                result["success"] = False
                log("Managed container cleanup failed; manual cleanup may be required.")
    return result
