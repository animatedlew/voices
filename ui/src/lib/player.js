// Streams raw PCM (s16le, mono) into the Web Audio API as it arrives.
// Speed uses playbackRate, so pitch shifts with it (phonon itself only supports 1x).

export class PcmPlayer {
  constructor() {
    this.ctx = null
    this.gain = null
    this.sources = new Set()
    this.nextTime = 0
    this.token = 0 // bumped by stop() so in-flight play() calls know they were cancelled
    this.finish = null // resolves the pending play() promise early on stop()
  }

  #ensure() {
    if (!this.ctx) {
      this.ctx = new AudioContext()
      this.gain = this.ctx.createGain()
      this.gain.connect(this.ctx.destination)
    }
    if (this.ctx.state === 'suspended') this.ctx.resume()
  }

  setVolume(v) {
    if (this.gain) this.gain.gain.value = v
  }

  stop() {
    this.token++
    for (const s of this.sources) {
      s.onended = null
      try { s.stop() } catch { /* already stopped */ }
    }
    this.sources.clear()
    this.nextTime = 0
    this.finish?.()
    this.finish = null
  }

  /**
   * Play an async iterable of Uint8Array PCM chunks.
   * Resolves when the last scheduled audio has finished, or immediately if stop() is called.
   */
  async play(chunks, { sampleRate = 24000, speed = 1, volume = 1, onFirstAudio } = {}) {
    this.stop()
    this.#ensure()
    this.setVolume(volume)
    const token = this.token
    let carry = null // odd trailing byte between network chunks
    let first = true
    let last = null

    for await (const raw of chunks) {
      if (token !== this.token) return
      let bytes = raw
      if (carry !== null) {
        const merged = new Uint8Array(bytes.length + 1)
        merged[0] = carry
        merged.set(bytes, 1)
        bytes = merged
        carry = null
      }
      if (bytes.length % 2) {
        carry = bytes[bytes.length - 1]
        bytes = bytes.subarray(0, bytes.length - 1)
      }
      if (!bytes.length) continue

      const samples = bytes.length / 2
      const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.length)
      const buf = this.ctx.createBuffer(1, samples, sampleRate)
      const ch = buf.getChannelData(0)
      for (let i = 0; i < samples; i++) ch[i] = view.getInt16(i * 2, true) / 32768

      const src = this.ctx.createBufferSource()
      src.buffer = buf
      src.playbackRate.value = speed
      src.connect(this.gain)
      // Small lead-in on the first chunk, and re-sync if playback ran dry.
      const now = this.ctx.currentTime
      if (first || this.nextTime < now) this.nextTime = now + 0.06
      src.start(this.nextTime)
      this.nextTime += buf.duration / speed
      this.sources.add(src)
      src.onended = () => this.sources.delete(src)
      last = src
      if (first) {
        first = false
        onFirstAudio?.()
      }
    }

    if (token !== this.token || !last || !this.sources.has(last)) return
    await new Promise((resolve) => {
      this.finish = resolve
      last.onended = () => {
        this.sources.delete(last)
        this.finish = null
        resolve()
      }
    })
  }
}

/** Fetch the backend stream as an async iterable of Uint8Array. */
export async function* streamSpeech(text, voice, signal) {
  const res = await fetch('/api/speak', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, voice }),
    signal,
  })
  if (!res.ok) throw new Error(await errorMessage(res))
  const reader = res.body.getReader()
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) return
      yield value
    }
  } finally {
    // Closing early (stop button) cancels the request, which stops generation upstream.
    reader.cancel().catch(() => {})
  }
}

async function errorMessage(res) {
  const body = await res.text()
  try {
    const detail = JSON.parse(body).detail
    if (typeof detail === 'string') return detail
    // FastAPI validation errors are a list of {msg, loc}
    if (Array.isArray(detail)) return detail.map((d) => d.msg).join('; ')
  } catch { /* not JSON */ }
  return body || `Request failed (${res.status})`
}
