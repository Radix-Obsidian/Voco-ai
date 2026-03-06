"""Deepgram streaming STT client for real-time PCM-16 transcription."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator

logger = logging.getLogger(__name__)


class DeepgramStreamingSession:
    """Manages a persistent Deepgram streaming WS for real-time interim transcripts.

    Opened once per speech turn (on speech onset), closed on turn-end.
    Feeds PCM chunks in real-time and yields interim/final transcripts via queues.
    """

    WS_URL = "wss://api.deepgram.com/v1/listen"

    def __init__(self, api_key: str, sample_rate: int = 16_000) -> None:
        self._api_key = api_key
        self._sample_rate = sample_rate
        self._ws = None
        self._send_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        self.interim_queue: asyncio.Queue[str | None] = asyncio.Queue()
        self._final_parts: list[str] = []
        self._tasks: list[asyncio.Task] = []
        self._closed = False

    async def start(self) -> None:
        """Open Deepgram streaming WS. Call once per turn (on speech onset)."""
        import websockets

        if not self._api_key:
            raise ValueError("DEEPGRAM_API_KEY not set")

        ws_url = (
            f"{self.WS_URL}"
            f"?encoding=linear16&sample_rate={self._sample_rate}"
            f"&channels=1&model=nova-2&interim_results=true&smart_format=true"
        )
        extra_headers = {"Authorization": f"Token {self._api_key}"}
        self._ws = await websockets.connect(ws_url, additional_headers=extra_headers)
        self._tasks = [
            asyncio.create_task(self._send_loop()),
            asyncio.create_task(self._recv_loop()),
        ]
        logger.info("[StreamSTT] Session opened")

    async def feed(self, chunk: bytes) -> None:
        """Queue a PCM chunk to send to Deepgram. Non-blocking."""
        if not self._closed:
            await self._send_queue.put(chunk)

    async def finish(self) -> str:
        """Signal end of audio, collect final transcript, close WS."""
        if self._closed:
            return " ".join(self._final_parts).strip()

        self._closed = True
        # Signal send loop to close
        await self._send_queue.put(None)
        # Wait for tasks to complete (recv loop ends when WS closes)
        for task in self._tasks:
            try:
                await asyncio.wait_for(task, timeout=5.0)
            except (asyncio.TimeoutError, Exception):
                task.cancel()
        # Signal interim consumer to stop
        await self.interim_queue.put(None)
        transcript = " ".join(self._final_parts).strip()
        logger.info("[StreamSTT] Final transcript: %s", transcript)
        return transcript

    async def stop(self) -> None:
        """Cancel tasks, close WS if open."""
        self._closed = True
        for task in self._tasks:
            task.cancel()
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

    async def _send_loop(self) -> None:
        """Send queued PCM chunks to Deepgram WS."""
        try:
            while True:
                chunk = await self._send_queue.get()
                if chunk is None:
                    # Send CloseStream message per Deepgram docs
                    if self._ws:
                        await self._ws.send(json.dumps({"type": "CloseStream"}))
                    break
                if self._ws:
                    await self._ws.send(chunk)
        except Exception as exc:
            logger.warning("[StreamSTT] Send error: %s", exc)

    async def _recv_loop(self) -> None:
        """Receive transcript results from Deepgram, route to interim_queue or _final_parts."""
        import websockets

        try:
            async for raw in self._ws:
                text = raw if isinstance(raw, str) else raw.decode()
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError:
                    continue

                msg_type = payload.get("type", "")
                if msg_type != "Results":
                    continue

                channel = payload.get("channel", {})
                transcript = (
                    channel.get("alternatives", [{}])[0].get("transcript", "")
                )
                is_final = payload.get("is_final", False)

                if is_final:
                    if transcript:
                        self._final_parts.append(transcript)
                        # Also push final segments as interim so UI stays current
                        await self.interim_queue.put(" ".join(self._final_parts))
                else:
                    if transcript:
                        # Interim: show accumulated finals + current interim
                        combined = " ".join(self._final_parts + [transcript])
                        await self.interim_queue.put(combined)
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as exc:
            logger.warning("[StreamSTT] Recv error: %s", exc)


class WhisperLocalSession:
    """Local offline STT using faster-whisper (CTranslate2).

    Same interface as DeepgramStreamingSession so main.py can swap seamlessly.
    Provides interim transcripts by periodically re-transcribing accumulated audio.
    """

    def __init__(self, model_size: str = "base.en", sample_rate: int = 16_000) -> None:
        self._model_size = model_size
        self._sample_rate = sample_rate
        self._audio_buffer = bytearray()
        self._model = None
        self.interim_queue: asyncio.Queue[str | None] = asyncio.Queue()
        self._final_parts: list[str] = []
        self._closed = False
        self._tasks: list[asyncio.Task] = []
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Load the Whisper model (downloads on first use, ~75-150MB)."""
        loop = asyncio.get_event_loop()
        self._model = await loop.run_in_executor(None, self._load_model)
        self._tasks = [asyncio.create_task(self._periodic_transcribe())]
        logger.info("[WhisperLocal] Model '%s' loaded, session started", self._model_size)

    def _load_model(self):
        from faster_whisper import WhisperModel
        return WhisperModel(
            self._model_size,
            device="cpu",
            compute_type="int8",
        )

    async def feed(self, chunk: bytes) -> None:
        """Append PCM chunk to the internal buffer."""
        if not self._closed:
            self._audio_buffer.extend(chunk)

    async def finish(self) -> str:
        """Run final transcription on full accumulated audio, return transcript."""
        self._closed = True
        for task in self._tasks:
            task.cancel()

        if not self._audio_buffer or not self._model:
            await self.interim_queue.put(None)
            return ""

        transcript = await self._transcribe_buffer(bytes(self._audio_buffer))
        self._audio_buffer.clear()
        await self.interim_queue.put(None)
        logger.info("[WhisperLocal] Final transcript: %s", transcript)
        return transcript

    async def stop(self) -> None:
        """Cancel tasks and release resources."""
        self._closed = True
        for task in self._tasks:
            task.cancel()
        self._audio_buffer.clear()

    async def _periodic_transcribe(self) -> None:
        """Re-transcribe accumulated audio every ~600ms for interim results."""
        import numpy as np

        min_bytes = self._sample_rate * 2  # 1 second minimum before first interim
        try:
            while not self._closed:
                await asyncio.sleep(0.6)
                if self._closed or len(self._audio_buffer) < min_bytes:
                    continue
                async with self._lock:
                    snapshot = bytes(self._audio_buffer)
                transcript = await self._transcribe_buffer(snapshot)
                if transcript and not self._closed:
                    await self.interim_queue.put(transcript)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.warning("[WhisperLocal] Periodic transcribe error: %s", exc)

    async def _transcribe_buffer(self, audio_bytes: bytes) -> str:
        """Run Whisper on a PCM-16 byte buffer, return text."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_transcribe, audio_bytes)

    def _sync_transcribe(self, audio_bytes: bytes) -> str:
        """Synchronous Whisper transcription (runs in thread pool)."""
        import numpy as np

        if not self._model or len(audio_bytes) < 3200:
            return ""

        # Convert PCM-16 LE to float32 numpy array
        audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        segments, _ = self._model.transcribe(
            audio_np,
            language="en",
            beam_size=1,
            vad_filter=True,
            without_timestamps=True,
        )
        parts = [seg.text.strip() for seg in segments if seg.text.strip()]
        return " ".join(parts)


class DeepgramSTT:
    """Streams raw PCM-16 audio to Deepgram and yields transcript segments.

    Parameters
    ----------
    api_key : str
        Deepgram API key (from DEEPGRAM_API_KEY env var).
    sample_rate : int
        Sample rate of the incoming PCM stream (default 16 kHz).
    """

    WS_URL = "wss://api.deepgram.com/v1/listen"

    def __init__(self, api_key: str, *, sample_rate: int = 16_000) -> None:
        self._api_key = api_key
        self._sample_rate = sample_rate

    async def transcribe_once(self, audio_bytes: bytes, max_retries: int = 2) -> str:
        """Send a complete audio buffer to Deepgram and return the transcript.

        Uses the pre-recorded endpoint for simplicity when a full turn's
        audio is available after VAD fires ``on_turn_end``.

        Retries up to ``max_retries`` times on transient failures (network
        errors, 5xx responses) with exponential backoff.
        """
        import asyncio
        import httpx

        if not self._api_key:
            raise ValueError("DEEPGRAM_API_KEY not set — microphone input cannot be transcribed. Check your API keys in Settings.")

        url = (
            f"https://api.deepgram.com/v1/listen"
            f"?encoding=linear16&sample_rate={self._sample_rate}"
            f"&channels=1&model=nova-2&smart_format=true"
        )
        headers = {
            "Authorization": f"Token {self._api_key}",
            "Content-Type": "audio/raw",
        }

        last_error: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(url, headers=headers, content=audio_bytes)
                    response.raise_for_status()
                    data = response.json()

                try:
                    transcript: str = (
                        data["results"]["channels"][0]["alternatives"][0]["transcript"]
                    )
                    logger.info("[STT] Transcript: %s", transcript)
                    return transcript.strip()
                except (KeyError, IndexError):
                    logger.warning("[STT] Empty or malformed Deepgram response: %s", data)
                    return ""

            except httpx.HTTPStatusError as exc:
                last_error = exc
                # Don't retry client errors (4xx) — only server errors (5xx)
                if exc.response.status_code < 500:
                    logger.error("[STT] Deepgram client error %d: %s", exc.response.status_code, exc)
                    return ""
                logger.warning("[STT] Deepgram server error %d (attempt %d/%d)", exc.response.status_code, attempt + 1, max_retries + 1)
            except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadError) as exc:
                last_error = exc
                logger.warning("[STT] Deepgram network error (attempt %d/%d): %s", attempt + 1, max_retries + 1, exc)

            if attempt < max_retries:
                await asyncio.sleep(1.0 * (attempt + 1))

        logger.error("[STT] All %d transcription attempts failed: %s", max_retries + 1, last_error)
        return ""

    async def transcribe_stream(
        self, audio_chunks: AsyncGenerator[bytes, None]
    ) -> AsyncGenerator[str, None]:
        """Stream PCM-16 chunks to Deepgram, yielding interim transcripts.

        Uses Deepgram's streaming WebSocket endpoint with ``interim_results``.
        Audio sending and transcript receiving run concurrently per the
        official Deepgram streaming API contract.
        """
        import websockets

        ws_url = (
            f"{self.WS_URL}"
            f"?encoding=linear16&sample_rate={self._sample_rate}"
            f"&channels=1&model=nova-2&interim_results=true"
        )
        extra_headers = {"Authorization": f"Token {self._api_key}"}

        transcript_queue: asyncio.Queue[str | None] = asyncio.Queue()

        async def _send_audio(ws) -> None:
            """Send audio chunks to Deepgram concurrently."""
            try:
                async for chunk in audio_chunks:
                    await ws.send(chunk)
                # Signal end of audio stream per Deepgram docs
                await ws.send(json.dumps({"type": "CloseStream"}))
            except Exception as exc:
                logger.warning("[STT] Audio send error: %s", exc)

        async def _receive_transcripts(ws) -> None:
            """Receive transcript results from Deepgram concurrently."""
            try:
                async for raw in ws:
                    text = raw if isinstance(raw, str) else raw.decode()
                    try:
                        payload = json.loads(text)
                    except json.JSONDecodeError:
                        continue

                    msg_type = payload.get("type", "")
                    if msg_type == "Results":
                        transcript = (
                            payload.get("channel", {})
                            .get("alternatives", [{}])[0]
                            .get("transcript", "")
                        )
                        if transcript:
                            await transcript_queue.put(transcript)
                    elif msg_type == "Metadata":
                        logger.debug("[STT] Deepgram metadata: request_id=%s", payload.get("request_id"))
            except websockets.exceptions.ConnectionClosed:
                pass
            except Exception as exc:
                logger.warning("[STT] Transcript receive error: %s", exc)
            finally:
                await transcript_queue.put(None)  # Signal completion

        async with websockets.connect(ws_url, extra_headers=extra_headers) as ws:
            send_task = asyncio.create_task(_send_audio(ws))
            recv_task = asyncio.create_task(_receive_transcripts(ws))

            try:
                while True:
                    transcript = await transcript_queue.get()
                    if transcript is None:
                        break
                    yield transcript
            finally:
                send_task.cancel()
                recv_task.cancel()
