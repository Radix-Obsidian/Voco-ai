"""Orgo.ai VM manager — cloud compute sandbox for the Voco Body organ.

Voco provisions VMs on behalf of users using its own Orgo account.
Users never see an API key. Access is tier-gated (free=0, pro=2h/day, founder=unlimited).
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from .constants import ORGO_BOOT_TIMEOUT, ORGO_DEFAULT_RAM, ORGO_DEFAULT_CPU

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.orgo.ai/api"


class OrgoError(Exception):
    """Raised when an Orgo API call fails."""

    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message)
        self.status_code = status_code


class OrgoVMManager:
    """Manages a single Orgo cloud VM per Voco session.

    Lifecycle: create → start → use → destroy.
    One active VM at a time per session (matches the single-sandbox UX pattern).
    """

    def __init__(self) -> None:
        self._api_key = os.environ.get("ORGO_API_KEY", "")
        if not self._api_key:
            raise OrgoError("ORGO_API_KEY not set in server environment")

        self._workspace_id = os.environ.get("ORGO_WORKSPACE_ID", "")
        self._client = httpx.AsyncClient(
            base_url=_BASE_URL,
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=httpx.Timeout(ORGO_BOOT_TIMEOUT, connect=10.0),
        )
        self.computer_id: str | None = None

    async def close(self) -> None:
        """Clean up HTTP client."""
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Make an authenticated request to the Orgo API with retry on 5xx."""
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                kwargs: dict[str, Any] = {}
                if json is not None:
                    kwargs["json"] = json
                if timeout is not None:
                    kwargs["timeout"] = timeout

                resp = await self._client.request(method, path, **kwargs)

                if resp.status_code >= 500:
                    last_exc = OrgoError(
                        f"Orgo API {resp.status_code}: {resp.text[:200]}",
                        status_code=resp.status_code,
                    )
                    if attempt < 2:
                        import asyncio
                        await asyncio.sleep(1.0 * (attempt + 1))
                        continue
                    raise last_exc

                if resp.status_code >= 400:
                    raise OrgoError(
                        f"Orgo API {resp.status_code}: {resp.text[:200]}",
                        status_code=resp.status_code,
                    )

                if resp.status_code == 204 or not resp.content:
                    return {}
                return resp.json()

            except httpx.HTTPError as exc:
                last_exc = OrgoError(f"Network error: {exc}")
                if attempt < 2:
                    import asyncio
                    await asyncio.sleep(1.0 * (attempt + 1))
                    continue

        raise last_exc or OrgoError("Request failed after retries")

    # ------------------------------------------------------------------
    # VM lifecycle
    # ------------------------------------------------------------------

    async def create_vm(
        self,
        name: str,
        ram: int = ORGO_DEFAULT_RAM,
        cpu: int = ORGO_DEFAULT_CPU,
    ) -> dict[str, Any]:
        """Create and start a new Orgo VM. Returns {computer_id, status}."""
        if self.computer_id:
            logger.warning("[Orgo] Destroying existing VM %s before creating new one", self.computer_id)
            await self.destroy_vm()

        body: dict[str, Any] = {"name": name, "os": "linux", "ram": ram, "cpu": cpu}
        if self._workspace_id:
            body["workspace_id"] = self._workspace_id

        result = await self._request("POST", "/computers", json=body)
        self.computer_id = result.get("id") or result.get("computer_id")
        if not self.computer_id:
            raise OrgoError(f"No computer_id in create response: {result}")

        logger.info("[Orgo] Created VM %s (ram=%dGB, cpu=%d)", self.computer_id, ram, cpu)

        # Start the VM
        await self._request("POST", f"/computers/{self.computer_id}/start")
        logger.info("[Orgo] VM %s started", self.computer_id)

        return {"computer_id": self.computer_id, "status": "running"}

    async def destroy_vm(self) -> None:
        """Stop and delete the active VM. Safe to call if no VM is active."""
        if not self.computer_id:
            return
        cid = self.computer_id
        self.computer_id = None
        try:
            await self._request("POST", f"/computers/{cid}/stop")
        except OrgoError:
            pass  # VM may already be stopped
        try:
            await self._request("DELETE", f"/computers/{cid}")
        except OrgoError as exc:
            logger.warning("[Orgo] Failed to delete VM %s: %s", cid, exc)
        logger.info("[Orgo] VM %s destroyed", cid)

    async def get_status(self) -> dict[str, Any]:
        """Get status of the active VM."""
        if not self.computer_id:
            return {"status": "none", "computer_id": None}
        return await self._request("GET", f"/computers/{self.computer_id}")

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def run_bash(self, command: str, timeout: float = 30.0) -> dict[str, Any]:
        """Execute a shell command in the VM."""
        self._require_vm()
        result = await self._request(
            "POST",
            f"/computers/{self.computer_id}/bash",
            json={"command": command},
            timeout=timeout + 5.0,
        )
        return result

    async def run_python(self, code: str, timeout: float = 10.0) -> dict[str, Any]:
        """Execute Python code in the VM."""
        self._require_vm()
        result = await self._request(
            "POST",
            f"/computers/{self.computer_id}/exec",
            json={"code": code, "timeout": timeout},
            timeout=timeout + 5.0,
        )
        return result

    # ------------------------------------------------------------------
    # Screen / GUI
    # ------------------------------------------------------------------

    async def take_screenshot(self) -> str:
        """Capture the VM desktop. Returns base64-encoded PNG."""
        self._require_vm()
        result = await self._request("GET", f"/computers/{self.computer_id}/screenshot")
        return result.get("image", result.get("screenshot", ""))

    async def get_vnc_credentials(self) -> dict[str, str]:
        """Get VNC password for live desktop streaming.

        Returns {vnc_url, vnc_password} for the frontend noVNC client.
        """
        self._require_vm()
        result = await self._request("GET", f"/computers/{self.computer_id}/vnc-password")
        password = result.get("password", result.get("vnc_password", ""))
        vnc_url = f"wss://{self.computer_id}.orgo.dev"
        return {"vnc_url": vnc_url, "vnc_password": password}

    # ------------------------------------------------------------------
    # File management
    # ------------------------------------------------------------------

    async def upload_file(self, file_path: str, content: str) -> dict[str, Any]:
        """Upload a file to the VM by writing it via bash."""
        self._require_vm()
        # Use bash to write file — simpler than multipart upload for text files
        import shlex
        escaped_content = content.replace("'", "'\\''")
        mkdir_cmd = f"mkdir -p $(dirname {shlex.quote(file_path)})"
        write_cmd = f"cat > {shlex.quote(file_path)} << 'VOCO_EOF'\n{escaped_content}\nVOCO_EOF"
        await self.run_bash(mkdir_cmd, timeout=5.0)
        result = await self.run_bash(write_cmd, timeout=10.0)
        return {"status": "uploaded", "path": file_path, **result}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _require_vm(self) -> None:
        """Raise if no VM is active."""
        if not self.computer_id:
            raise OrgoError("No active sandbox VM. Call orgo_create_sandbox first.")
