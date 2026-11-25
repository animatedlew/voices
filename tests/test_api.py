"""Backend tests. Ollama is replaced with an in-memory fake via httpx.MockTransport."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

import main

PCM = b"\x01\x00" * 4800  # 0.2 s of audio


class Chunks(httpx.AsyncByteStream):
    """Delivers PCM in several pieces, like a real streaming upstream."""

    async def __aiter__(self):
        for i in range(0, len(PCM), 3000):
            yield PCM[i : i + 3000]


def fake_ollama(
    *, version="0.40.18", show=None, show_status=200, speech_status=200, speech_body=None
):
    show = show or {"capabilities": ["speech"], "voices": ["Alfie", "Freya"], "requires": "0.40.9"}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/version":
            return httpx.Response(200, json={"version": version})
        if path == "/api/show":
            return httpx.Response(show_status, json=show)
        if path == "/v1/audio/speech":
            if speech_status != 200:
                return httpx.Response(speech_status, json=speech_body)
            return httpx.Response(200, stream=Chunks())
        return httpx.Response(404)

    return handler


def down(_request):
    raise httpx.ConnectError("refused")


@pytest.fixture
def client_for(monkeypatch):
    def build(handler):
        monkeypatch.setattr(
            main,
            "make_client",
            lambda: httpx.AsyncClient(
                base_url="http://ollama", transport=httpx.MockTransport(handler)
            ),
        )
        return TestClient(main.app)

    return build


def test_health_ok(client_for):
    with client_for(fake_ollama()) as c:
        body = c.get("/api/health").json()
    assert body["ok"] is True and body["problem"] is None


def test_health_ollama_unreachable(client_for):
    with client_for(down) as c:
        body = c.get("/api/health").json()
    assert body["ok"] is False and "not reachable" in body["problem"]


def test_health_ollama_dies_midway(client_for):
    def handler(request):
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.40.18"})
        raise httpx.ReadError("gone")

    with client_for(handler) as c:
        body = c.get("/api/health").json()
    assert body["ok"] is False and "stopped responding" in body["problem"]


def test_health_model_missing(client_for):
    with client_for(fake_ollama(show_status=404, show={"error": "not found"})) as c:
        body = c.get("/api/health").json()
    assert body["ok"] is False and "not installed" in body["problem"]
    assert "ollama pull" in body["hint"]


def test_health_not_a_speech_model(client_for):
    with client_for(fake_ollama(show={"capabilities": ["completion"]})) as c:
        body = c.get("/api/health").json()
    assert body["ok"] is False and "not a speech model" in body["problem"]


def test_health_ollama_too_old(client_for):
    with client_for(fake_ollama(version="0.39.0")) as c:
        body = c.get("/api/health").json()
    assert body["ok"] is False and "too old" in body["problem"]


def test_health_prerelease_version_is_compared_numerically(client_for):
    with client_for(fake_ollama(version="0.40.9-rc1")) as c:
        assert c.get("/api/health").json()["ok"] is True


def test_voices(client_for):
    with client_for(fake_ollama()) as c:
        body = c.get("/api/voices").json()
    assert body["voices"] == ["Alfie", "Freya"] and body["sample_rate"] == 24000


def test_voices_ollama_down_is_502(client_for):
    with client_for(down) as c:
        assert c.get("/api/voices").status_code == 502


def test_speak_streams_pcm(client_for):
    with client_for(fake_ollama()) as c:
        r = c.post("/api/speak", json={"text": "hello", "voice": "Alfie"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/L16"
    assert r.headers["x-sample-rate"] == "24000"
    assert r.content == PCM


def test_speak_sends_trimmed_text_and_voice(client_for):
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        return httpx.Response(200, stream=Chunks())

    with client_for(handler) as c:
        c.post("/api/speak", json={"text": "  hi  ", "voice": "Freya"})
    assert seen == {"model": "phonon", "input": "hi", "voice": "Freya", "response_format": "pcm"}


def test_speak_unwraps_ollama_error(client_for):
    err = {"error": {"message": 'voice "x" not found'}}
    with client_for(fake_ollama(speech_status=400, speech_body=err)) as c:
        r = c.post("/api/speak", json={"text": "hi", "voice": "x"})
    assert r.status_code == 400 and r.json()["detail"] == 'voice "x" not found'


def test_speak_upstream_500_becomes_502(client_for):
    handler = fake_ollama(speech_status=500, speech_body={"error": {"message": "boom"}})
    with client_for(handler) as c:
        assert c.post("/api/speak", json={"text": "hi"}).status_code == 502


def test_speak_ollama_down_is_502(client_for):
    with client_for(down) as c:
        assert c.post("/api/speak", json={"text": "hi"}).status_code == 502


@pytest.mark.parametrize(
    "body",
    [{"text": ""}, {"text": "   "}, {"text": "x" * 8001}, {"text": "hi", "voice": ""}, {}],
)
def test_speak_rejects_bad_input(client_for, body):
    with client_for(fake_ollama()) as c:
        assert c.post("/api/speak", json=body).status_code == 422
