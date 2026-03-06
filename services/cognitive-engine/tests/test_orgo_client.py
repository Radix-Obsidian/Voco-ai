"""Production readiness tests — Orgo VM manager (Body organ).

Validates the OrgoVMManager class: init, lifecycle, error handling,
retry logic, and session cleanup patterns.

Run:
    cd services/cognitive-engine
    uv run pytest tests/test_orgo_client.py -v
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 1. OrgoVMManager init
# ---------------------------------------------------------------------------


class TestOrgoVMManagerInit:
    """Constructor requires ORGO_API_KEY env var."""

    def test_missing_api_key_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("ORGO_API_KEY", None)
            from src.orgo_client import OrgoVMManager, OrgoError
            with pytest.raises(OrgoError, match="ORGO_API_KEY not set"):
                OrgoVMManager()

    def test_init_with_api_key(self):
        with patch.dict(os.environ, {"ORGO_API_KEY": "test-key-123"}):
            from src.orgo_client import OrgoVMManager
            mgr = OrgoVMManager()
            assert mgr.computer_id is None
            assert mgr._api_key == "test-key-123"

    def test_workspace_id_optional(self):
        with patch.dict(os.environ, {"ORGO_API_KEY": "key", "ORGO_WORKSPACE_ID": "ws-42"}):
            from src.orgo_client import OrgoVMManager
            mgr = OrgoVMManager()
            assert mgr._workspace_id == "ws-42"


# ---------------------------------------------------------------------------
# 2. VM lifecycle
# ---------------------------------------------------------------------------


class TestOrgoVMLifecycle:
    """Create, status check, and destroy flows."""

    @pytest.mark.asyncio
    async def test_create_vm_sets_computer_id(self):
        with patch.dict(os.environ, {"ORGO_API_KEY": "key"}):
            from src.orgo_client import OrgoVMManager
            mgr = OrgoVMManager()
            mgr._request = AsyncMock(side_effect=[
                {"id": "vm-abc123"},  # POST /computers
                {},                    # POST /computers/{id}/start
            ])
            result = await mgr.create_vm("test-project")
            assert result["computer_id"] == "vm-abc123"
            assert result["status"] == "running"
            assert mgr.computer_id == "vm-abc123"

    @pytest.mark.asyncio
    async def test_create_vm_destroys_existing_first(self):
        with patch.dict(os.environ, {"ORGO_API_KEY": "key"}):
            from src.orgo_client import OrgoVMManager
            mgr = OrgoVMManager()
            mgr.computer_id = "old-vm"
            mgr._request = AsyncMock(side_effect=[
                {},                    # POST /computers/old-vm/stop (destroy)
                {},                    # DELETE /computers/old-vm (destroy)
                {"id": "new-vm"},      # POST /computers (create)
                {},                    # POST /computers/new-vm/start
            ])
            result = await mgr.create_vm("new-project")
            assert result["computer_id"] == "new-vm"

    @pytest.mark.asyncio
    async def test_destroy_vm_clears_computer_id(self):
        with patch.dict(os.environ, {"ORGO_API_KEY": "key"}):
            from src.orgo_client import OrgoVMManager
            mgr = OrgoVMManager()
            mgr.computer_id = "vm-to-destroy"
            mgr._request = AsyncMock(return_value={})
            await mgr.destroy_vm()
            assert mgr.computer_id is None

    @pytest.mark.asyncio
    async def test_destroy_vm_noop_when_no_vm(self):
        with patch.dict(os.environ, {"ORGO_API_KEY": "key"}):
            from src.orgo_client import OrgoVMManager
            mgr = OrgoVMManager()
            mgr._request = AsyncMock()
            await mgr.destroy_vm()
            mgr._request.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_status_with_no_vm(self):
        with patch.dict(os.environ, {"ORGO_API_KEY": "key"}):
            from src.orgo_client import OrgoVMManager
            mgr = OrgoVMManager()
            result = await mgr.get_status()
            assert result["status"] == "none"
            assert result["computer_id"] is None


# ---------------------------------------------------------------------------
# 3. Execution methods require active VM
# ---------------------------------------------------------------------------


class TestOrgoRequireVM:
    """Methods that need an active VM should raise OrgoError if none."""

    @pytest.mark.asyncio
    async def test_run_bash_requires_vm(self):
        with patch.dict(os.environ, {"ORGO_API_KEY": "key"}):
            from src.orgo_client import OrgoVMManager, OrgoError
            mgr = OrgoVMManager()
            with pytest.raises(OrgoError, match="No active sandbox"):
                await mgr.run_bash("echo hello")

    @pytest.mark.asyncio
    async def test_run_python_requires_vm(self):
        with patch.dict(os.environ, {"ORGO_API_KEY": "key"}):
            from src.orgo_client import OrgoVMManager, OrgoError
            mgr = OrgoVMManager()
            with pytest.raises(OrgoError, match="No active sandbox"):
                await mgr.run_python("print('hi')")

    @pytest.mark.asyncio
    async def test_take_screenshot_requires_vm(self):
        with patch.dict(os.environ, {"ORGO_API_KEY": "key"}):
            from src.orgo_client import OrgoVMManager, OrgoError
            mgr = OrgoVMManager()
            with pytest.raises(OrgoError, match="No active sandbox"):
                await mgr.take_screenshot()

    @pytest.mark.asyncio
    async def test_upload_file_requires_vm(self):
        with patch.dict(os.environ, {"ORGO_API_KEY": "key"}):
            from src.orgo_client import OrgoVMManager, OrgoError
            mgr = OrgoVMManager()
            with pytest.raises(OrgoError, match="No active sandbox"):
                await mgr.upload_file("/tmp/test.txt", "content")

    @pytest.mark.asyncio
    async def test_get_vnc_credentials_requires_vm(self):
        with patch.dict(os.environ, {"ORGO_API_KEY": "key"}):
            from src.orgo_client import OrgoVMManager, OrgoError
            mgr = OrgoVMManager()
            with pytest.raises(OrgoError, match="No active sandbox"):
                await mgr.get_vnc_credentials()


# ---------------------------------------------------------------------------
# 4. Execution with active VM
# ---------------------------------------------------------------------------


class TestOrgoExecution:
    """Methods produce correct API calls when VM is active."""

    @pytest.mark.asyncio
    async def test_run_bash_returns_result(self):
        with patch.dict(os.environ, {"ORGO_API_KEY": "key"}):
            from src.orgo_client import OrgoVMManager
            mgr = OrgoVMManager()
            mgr.computer_id = "vm-123"
            mgr._request = AsyncMock(return_value={"stdout": "hello\n", "stderr": "", "exit_code": 0})
            result = await mgr.run_bash("echo hello")
            assert result["stdout"] == "hello\n"
            assert result["exit_code"] == 0
            mgr._request.assert_called_once_with(
                "POST", "/computers/vm-123/bash",
                json={"command": "echo hello"}, timeout=35.0,
            )

    @pytest.mark.asyncio
    async def test_run_python_returns_result(self):
        with patch.dict(os.environ, {"ORGO_API_KEY": "key"}):
            from src.orgo_client import OrgoVMManager
            mgr = OrgoVMManager()
            mgr.computer_id = "vm-123"
            mgr._request = AsyncMock(return_value={"output": "42"})
            result = await mgr.run_python("print(42)")
            assert result["output"] == "42"

    @pytest.mark.asyncio
    async def test_take_screenshot_returns_base64(self):
        with patch.dict(os.environ, {"ORGO_API_KEY": "key"}):
            from src.orgo_client import OrgoVMManager
            mgr = OrgoVMManager()
            mgr.computer_id = "vm-123"
            mgr._request = AsyncMock(return_value={"image": "iVBORw0KGgo..."})
            result = await mgr.take_screenshot()
            assert result == "iVBORw0KGgo..."

    @pytest.mark.asyncio
    async def test_get_vnc_credentials_returns_url_and_password(self):
        with patch.dict(os.environ, {"ORGO_API_KEY": "key"}):
            from src.orgo_client import OrgoVMManager
            mgr = OrgoVMManager()
            mgr.computer_id = "vm-123"
            mgr._request = AsyncMock(return_value={"password": "secret123"})
            result = await mgr.get_vnc_credentials()
            assert result["vnc_url"] == "wss://vm-123.orgo.dev"
            assert result["vnc_password"] == "secret123"

    @pytest.mark.asyncio
    async def test_upload_file_runs_bash_commands(self):
        with patch.dict(os.environ, {"ORGO_API_KEY": "key"}):
            from src.orgo_client import OrgoVMManager
            mgr = OrgoVMManager()
            mgr.computer_id = "vm-123"
            mgr._request = AsyncMock(return_value={"stdout": "", "exit_code": 0})
            result = await mgr.upload_file("/tmp/test.txt", "hello world")
            assert result["status"] == "uploaded"
            assert result["path"] == "/tmp/test.txt"
            # Should make 2 calls: mkdir + cat
            assert mgr._request.call_count == 2


# ---------------------------------------------------------------------------
# 5. OrgoError attributes
# ---------------------------------------------------------------------------


class TestOrgoError:
    """OrgoError carries message and status_code."""

    def test_error_with_status_code(self):
        from src.orgo_client import OrgoError
        err = OrgoError("API failed", status_code=503)
        assert str(err) == "API failed"
        assert err.status_code == 503

    def test_error_default_status_code(self):
        from src.orgo_client import OrgoError
        err = OrgoError("Network error")
        assert err.status_code == 0


# ---------------------------------------------------------------------------
# 6. Close method
# ---------------------------------------------------------------------------


class TestOrgoClose:
    """close() shuts down the httpx client."""

    @pytest.mark.asyncio
    async def test_close_calls_aclose(self):
        with patch.dict(os.environ, {"ORGO_API_KEY": "key"}):
            from src.orgo_client import OrgoVMManager
            mgr = OrgoVMManager()
            mgr._client = AsyncMock()
            await mgr.close()
            mgr._client.aclose.assert_called_once()
