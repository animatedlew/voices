# Voices

Type or speak, and hear your words read back in a different voice. Voices runs text-to-speech locally with Ollama's `phonon` model. A FastAPI backend (`api/`) streams the audio, and a Vue 3 + Pinia + DaisyUI frontend (`ui/`) plays it while it is still being generated.

```
browser (Vue)  ──POST /api/speak──▶  FastAPI  ──/v1/audio/speech──▶  Ollama (phonon)
     ▲                                  │
     └────── streamed 24 kHz PCM ◀──────┘
```

It is a text-to-speech app, not a chatbot. No language model sits in between: the text you enter is what gets spoken.

## Requirements

| Tool | Notes |
| --- | --- |
| [Ollama](https://ollama.com) 0.40.9 or newer | Must be running (default `http://localhost:11434`). The `phonon` model requires this version. |
| `phonon` model | `ollama pull phonon` (about 112 MB). |
| [uv](https://docs.astral.sh/uv/) | Manages Python 3.14 and the backend dependencies. |
| Node.js 20.19+ and npm | Builds the UI. Developed with Node 24. |
| `make` | Optional, but all commands below use it. |
| A modern browser | Voice input needs a browser with speech recognition. Tested in Firefox. Chrome, Edge and Safari also provide it but are untested. Without it, typing still works. |

### Hardware

phonon is a small model (about 112 MB, 43M parameters) and runs on Ollama's MLX runner. I developed and tested this on an Apple silicon Mac (M1 Pro). I have not tested Intel, Linux or Windows, and I don't know whether the MLX runner supports them, so check Ollama's documentation if you are not on Apple silicon. Any machine that can run the model has more than enough power; the browser side is light.

### Optional

- `ffmpeg` is only needed for the "save a clip" example in the API section.
- A microphone and a supported browser are only needed for voice input. Without them, typing still works.

### What the app checks for you

When the page loads it asks the backend what is available (`GET /api/health`) and turns off what cannot work, with the reason shown on screen:

| Missing | What happens |
| --- | --- |
| Backend not running | Error banner. Nothing is spoken. |
| Ollama not running or wrong `OLLAMA_URL` | Warning banner with how to fix it. **Speak it** is disabled. |
| `phonon` not installed, not a speech model, or Ollama too old | Warning banner naming the problem and the fix. **Speak it** is disabled. |
| Browser without speech recognition, or a non-HTTPS page | Mic button is disabled with the reason. Typing still works. |
| Microphone permission denied | Shown when you press the mic. |

Press **Check again** in the banner after you fix the problem; no reload is needed.

## Quick start

```bash
ollama pull phonon   # once
make install         # once: installs Python and npm dependencies
make run             # builds the UI and serves it at http://localhost:8000
```

Open http://localhost:8000, type something, and press **Speak it** (or Enter).

## Make targets

| Target | What it does |
| --- | --- |
| `make install` | `uv sync` in `api/` and `npm install` in `ui/` |
| `make build` | Builds the UI into `ui/dist` |
| `make run` | Builds, then serves the app and API on port 8000 |
| `make api` | Backend only, with auto-reload, port 8000 |
| `make ui` | Vite dev server with hot reload, port 5173 (proxies `/api` to 8000) |
| `make dev` | Runs `api` and `ui` together; use http://localhost:5173 |
| `make test` | Runs the backend tests (Ollama is faked, so Ollama need not be running) |
| `make lint` | Ruff lint and format check, plus a UI build check |
| `make fmt` | Auto-formats the backend |
| `make clean` | Removes build output and caches |

`make help` prints this list.

## Using the app

- **Type** in the box and press Enter or **Speak it**. Shift+Enter adds a new line.
- **Speak** by pressing the mic button. Your words appear as you talk, and with *Speak automatically after I stop talking* on (the default) they are read back in the chosen voice when you pause. Turn that off to review the text first.
- **Stop** cuts off audio that is generating or playing.
- **History** keeps this session's clips. *Replay* reuses the audio already received, so it does not call the model again. *Edit* puts the text back in the box. History is kept in memory only, holds the last 20 clips, and is cleared on reload.

### Controls

| Control | Effect |
| --- | --- |
| Voice | Any voice phonon offers (38 on the default install, including characters such as "The Snow Queen" and "Old Mortlake"). |
| Speed (0.5x to 2x) | Applied in the browser, not by the model. **Pitch shifts with speed**, because phonon only supports 1x. Takes effect on the next clip. |
| Volume (0 to 150%) | Changes immediately, including during playback. |
| Speech input language | Language the browser should recognize when you talk. This does not change the voice's language. |
| Theme | Light, dark and several other DaisyUI themes. |

Settings are saved in your browser's local storage.

## Voice input notes

- Speech-to-text uses the browser's Web Speech API, not a local model. Depending on the browser, the audio may be sent to a cloud service for transcription instead of being processed on your machine, so check your browser's privacy documentation. If that matters to you, type instead. The text-to-speech side stays fully local.
- The microphone only works on `localhost` or over HTTPS. If you serve the app on another machine over plain HTTP, the mic button will fail.
- The first time you press the mic, the browser asks for microphone permission.

## API

The backend is a thin proxy over Ollama. Interactive docs are at http://localhost:8000/docs.

### `GET /api/health`

Returns `{"ok": true, ...}` when Ollama is reachable and the model is usable. Otherwise `ok` is false, with `problem` and `hint` strings explaining what to fix.

### `GET /api/voices`

```json
{ "model": "phonon", "sample_rate": 24000, "voices": ["Alfie", "Azgorath", "..."] }
```

### `POST /api/speak`

Body: `{"text": "Hello there", "voice": "Freya"}`. `text` is required and limited to 8000 characters. `voice` defaults to `default`.

The response is a stream of **raw PCM**: signed 16-bit little-endian, mono, 24000 Hz (`Content-Type: audio/L16`, with an `X-Sample-Rate` header). Errors come back as `{"detail": "..."}`. An unknown voice returns 400 with the list of valid voices, and an unreachable Ollama returns 502.

Save a clip from the command line:

```bash
curl -s localhost:8000/api/speak -H 'content-type: application/json' \
  -d '{"text":"Hello there","voice":"Freya"}' \
| ffmpeg -f s16le -ar 24000 -ac 1 -i - hello.wav
```

## Configuration

Set these as environment variables before starting the backend.

| Variable | Default | Purpose |
| --- | --- | --- |
| `OLLAMA_URL` | `http://localhost:11434` | Where Ollama is running |
| `PHONON_MODEL` | `phonon` | Model name to use for speech |

Example: `OLLAMA_URL=http://192.168.1.20:11434 make run`

## Technology

### UI (`ui/`)

| Technology | Used for |
| --- | --- |
| [Vue 3](https://vuejs.org) | Components, using the Composition API with `<script setup>`. |
| [Pinia](https://pinia.vuejs.org) | State: settings, voices, speech input, playback status and history live in one store (`src/stores/voice.js`). Settings persist to `localStorage`. |
| [Tailwind CSS 4](https://tailwindcss.com) and [DaisyUI 5](https://daisyui.com) | Styling and the component classes and themes. |
| [Vite](https://vite.dev) | Dev server with hot reload, the production build, and the `/api` proxy to the backend in dev. |
| **Web Speech API** (`SpeechRecognition`) | Voice input, done by the browser's own speech recognition rather than by this project. |
| **Fetch streaming** (`ReadableStream`) | Reads the audio response chunk by chunk instead of waiting for the whole clip. |
| **Web Audio API** | Decodes each raw PCM chunk and schedules it for gapless playback. Volume is a gain node, and speed is the playback rate (which is why pitch shifts with it). See `src/lib/player.js`. |

There is no UI framework beyond these, and no TypeScript or frontend test suite.

### API (`api/`)

| Technology | Used for |
| --- | --- |
| [Python 3.14](https://www.python.org) and [uv](https://docs.astral.sh/uv/) | Runtime, and dependency and virtual environment management (`pyproject.toml` and `uv.lock`). |
| [FastAPI](https://fastapi.tiangolo.com) | The HTTP API, with generated docs at `/docs`. Async endpoints, and `StreamingResponse` to pass audio through as it arrives. |
| [Pydantic](https://docs.pydantic.dev) | Validates request bodies (text length, blank text, voice). |
| [Uvicorn](https://www.uvicorn.org) | The ASGI server. |
| [httpx](https://www.python-httpx.org) | Async client for talking to Ollama. Streams the response with no read timeout, because long text takes a while to generate. |
| [Ollama](https://ollama.com) with the `phonon` model | Does the actual text-to-speech through its OpenAI-style `/v1/audio/speech` endpoint, returning raw 24 kHz PCM. The API also reads the voice list and model details from `/api/show`. |
| [pytest](https://docs.pytest.org) and [Ruff](https://docs.astral.sh/ruff/) | Tests (with Ollama faked through `httpx.MockTransport`), linting and formatting. |

The API serves the built UI from `ui/dist` when it exists, so one process serves the whole app in production mode.

## Project layout

```
Makefile                  Run, build, test and lint commands (run from here)
README.md
api/                      Python backend (uv project)
  main.py                   FastAPI app: API endpoints, plus serves ui/dist
  tests/test_api.py         Backend tests with a fake Ollama
  pyproject.toml            Python dependencies, ruff and pytest config
ui/                       Vue frontend (npm project)
  src/lib/player.js         Streams PCM chunks into the Web Audio API
  src/stores/voice.js       Pinia store: settings, speech input, playback, history
  src/components/           Composer, Controls, History
  vite.config.js            Tailwind/DaisyUI plugin and the /api dev proxy
```

## Troubleshooting

- **"Backend problem: Cannot reach Ollama"**: Ollama is not running or `OLLAMA_URL` is wrong. Start it with `ollama serve` (or open the Ollama app) and press Retry.
- **Voice list is empty or `model not found`**: run `ollama pull phonon`. Check that `ollama list` shows it, and that your Ollama is 0.40.9 or newer (`ollama --version`).
- **Page shows `{"detail":"Not Found"}` or is blank at port 8000**: the UI has not been built. Run `make build`, or use `make run`.
- **Mic button is disabled**: the browser has no speech recognition. Typing still works, or try a different browser.
- **Mic says `not-allowed`**: microphone permission was denied. Allow it in the browser's site settings and reload.
- **No sound**: browsers block audio until you interact with the page. Press the button again, and check the volume slider and your system output.
- **In `make dev`, requests fail with a CORS error**: use http://localhost:5173 (or `127.0.0.1:5173`), which the backend allows. Other origins are blocked unless you edit `allow_origins` in `api/main.py`.
- **Long text takes a while to start**: the model generates audio in order, so playback starts after the first chunk is ready and continues as the rest arrives.

## Limitations

- Speed changes pitch (see above).
- No authentication. The backend is meant for local use, so do not expose it to the internet as is.
- Only WAV and PCM are available from phonon, so the API streams PCM and does not offer MP3.
