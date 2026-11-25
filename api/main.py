"""Voices: a thin FastAPI layer over Ollama's `phonon` text-to-speech model.

Run from this directory with:  uv run uvicorn main:app --reload
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODEL = os.getenv("PHONON_MODEL", "phonon")
SAMPLE_RATE = 24_000  # phonon emits 16-bit signed little-endian mono PCM at 24 kHz
DIST = Path(__file__).resolve().parent.parent / "ui" / "dist"


def make_client() -> httpx.AsyncClient:
    # No read timeout: audio generation for long text can take a while.
    return httpx.AsyncClient(base_url=OLLAMA_URL, timeout=httpx.Timeout(10.0, read=None))


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http = make_client()
    yield
    await app.state.http.aclose()


app = FastAPI(title="Voices", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Sample-Rate"],
)


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    voice: str = Field(default="default", min_length=1, max_length=100)

    @field_validator("text")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("text must not be blank")
        return v


def _ver(v: str) -> tuple[int, ...]:
    """'0.40.18-rc1' -> (0, 40, 18)"""
    return tuple(int(x) for x in v.split("-")[0].split(".") if x.isdigit())


@app.get("/api/health")
async def health():
    """Say what is missing (Ollama, model, version) so the UI can disable itself with a reason."""
    out: dict = {
        "ollama_url": OLLAMA_URL,
        "model": MODEL,
        "ok": False,
        "problem": None,
        "hint": None,
    }
    try:
        version = (await app.state.http.get("/api/version")).json().get("version", "")
    except httpx.HTTPError, ValueError:
        out.update(
            problem="Ollama is not reachable.",
            hint="Start Ollama (open the app or run `ollama serve`), or set OLLAMA_URL.",
        )
        return out
    out["ollama_version"] = version

    try:
        r = await app.state.http.post("/api/show", json={"model": MODEL})
    except httpx.HTTPError:
        out.update(
            problem="Ollama stopped responding.",
            hint="Check that Ollama is running, then try again.",
        )
        return out
    if r.status_code == 404:
        out.update(
            problem=f"The {MODEL} model is not installed.", hint=f"Run `ollama pull {MODEL}`."
        )
        return out
    if r.status_code != 200:
        out.update(problem=f"Ollama could not load {MODEL}.", hint=r.text[:200])
        return out
    info = r.json()
    if "speech" not in info.get("capabilities", []):
        out.update(
            problem=f"{MODEL} is not a speech model.",
            hint="Set PHONON_MODEL to a model with the speech capability.",
        )
        return out
    need = info.get("requires")
    if need and version and _ver(version) < _ver(need):
        out.update(
            problem=f"Ollama {version} is too old for {MODEL}.",
            hint=f"Update Ollama to {need} or newer.",
        )
        return out
    out["ok"] = True
    return out


@app.get("/api/voices")
async def voices():
    """Voices the phonon model advertises, straight from Ollama."""
    try:
        r = await app.state.http.post("/api/show", json={"model": MODEL})
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Cannot reach Ollama at {OLLAMA_URL}: {e}") from e
    if r.status_code != 200:
        raise HTTPException(502, f"Ollama: {r.text}")
    return {"model": MODEL, "sample_rate": SAMPLE_RATE, "voices": r.json().get("voices", [])}


@app.post("/api/speak")
async def speak(req: SpeakRequest):
    """Receive text, stream back raw PCM (s16le, mono, 24 kHz) as phonon generates it."""
    upstream = app.state.http.build_request(
        "POST",
        "/v1/audio/speech",
        json={"model": MODEL, "input": req.text, "voice": req.voice, "response_format": "pcm"},
    )
    try:
        resp = await app.state.http.send(upstream, stream=True)
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Cannot reach Ollama at {OLLAMA_URL}: {e}") from e

    if resp.status_code != 200:
        raw = await resp.aread()
        await resp.aclose()
        try:
            detail = resp.json()["error"]["message"]
        except Exception:
            detail = raw.decode(errors="replace")
        raise HTTPException(resp.status_code if resp.status_code < 500 else 502, detail)

    async def body():
        try:
            async for chunk in resp.aiter_raw():
                yield chunk
        finally:
            await resp.aclose()

    return StreamingResponse(
        body(),
        media_type="audio/L16",
        headers={
            "X-Sample-Rate": str(SAMPLE_RATE),
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",  # stop nginx-style proxies from buffering the stream
        },
    )


# Serve the built frontend when present (`npm run build` in ../ui).
if DIST.is_dir():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="web")
