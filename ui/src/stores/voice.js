import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'
import { PcmPlayer, streamSpeech } from '../lib/player'

const SETTINGS_KEY = 'voices:settings'
const MAX_HISTORY = 20 // clips are kept in memory (~48 KB per second of audio)
const SR = window.SpeechRecognition || window.webkitSpeechRecognition

const MIC_ERRORS = {
  'not-allowed': 'Microphone access was blocked. Allow it in your browser\'s site settings and try again.',
  'service-not-allowed': 'Speech recognition is blocked by the browser or system settings.',
  'audio-capture': 'No microphone was found.',
  network: 'Speech recognition needs a network connection in this browser.',
}

const defaults = {
  voice: 'default',
  speed: 1,
  volume: 1,
  lang: navigator.language || 'en-US',
  autoSubmit: true,
  theme: 'dark',
}

function loadSettings() {
  try { return { ...defaults, ...JSON.parse(localStorage.getItem(SETTINGS_KEY) || '{}') } }
  catch { return { ...defaults } }
}

export const useVoiceStore = defineStore('voice', () => {
  const settings = ref(loadSettings())
  const voices = ref([])
  const sampleRate = ref(24000)
  const backendError = ref('')
  const health = ref(null) // { ok, problem, hint, ... } from /api/health

  const draft = ref('')
  const interim = ref('')
  const listening = ref(false)
  // Why voice input is unavailable, or '' if it works.
  const sttProblem = !SR
    ? 'Speech recognition is not supported in this browser.'
    : !window.isSecureContext
      ? 'The microphone needs HTTPS or localhost.'
      : ''
  const sttSupported = !sttProblem

  // idle | generating | playing
  const status = ref('idle')
  const error = ref('')
  const history = ref([])
  const activeId = ref(null)

  const player = new PcmPlayer()
  const pcmCache = new Map() // id -> { chunks: Uint8Array[], complete: boolean }
  let controller = null
  let recognition = null
  let nextId = 1

  const busy = computed(() => status.value !== 'idle')
  const ready = computed(() => !!health.value?.ok && voices.value.length > 0)

  watch(settings, (s) => {
    try { localStorage.setItem(SETTINGS_KEY, JSON.stringify(s)) } catch {}
    document.documentElement.dataset.theme = s.theme
  }, { deep: true, immediate: true })

  // Volume applies live; speed only applies to chunks scheduled afterward.
  watch(() => settings.value.volume, (v) => player.setVolume(v))

  async function loadVoices() {
    try {
      const h = await fetch('/api/health')
      if (!h.ok) throw new Error(`Backend returned ${h.status}`)
      health.value = await h.json()
      if (!health.value.ok) { voices.value = []; backendError.value = ''; return }
      const r = await fetch('/api/voices')
      if (!r.ok) throw new Error((await r.json()).detail ?? r.statusText)
      const d = await r.json()
      voices.value = d.voices
      sampleRate.value = d.sample_rate
      backendError.value = ''
      if (!d.voices.includes(settings.value.voice)) settings.value.voice = d.voices[0]
    } catch (e) {
      health.value = null
      backendError.value = `Cannot reach the Voices backend (${e.message}). Is it running?`
    }
  }

  function halt() {
    controller?.abort()
    player.stop()
    status.value = 'idle'
    activeId.value = null
  }

  async function run(id, source) {
    halt()
    controller = new AbortController()
    const { signal } = controller
    error.value = ''
    activeId.value = id
    status.value = 'generating'
    try {
      await player.play(source(signal), {
        sampleRate: sampleRate.value,
        speed: settings.value.speed,
        volume: settings.value.volume,
        onFirstAudio: () => { if (!signal.aborted) status.value = 'playing' },
      })
    } catch (e) {
      if (e.name !== 'AbortError' && !signal.aborted) error.value = e.message
    } finally {
      if (!signal.aborted) { status.value = 'idle'; activeId.value = null }
    }
  }

  // Generate (or regenerate) audio for a history item, caching it once complete.
  async function generate(item) {
    const clip = { chunks: [], complete: false }
    pcmCache.set(item.id, clip)
    await run(item.id, async function* (signal) {
      for await (const chunk of streamSpeech(item.text, item.voice, signal)) {
        clip.chunks.push(chunk)
        yield chunk
      }
      clip.complete = true // only reached when the stream finished normally
    })
    // A cancelled or failed generation leaves a partial clip; never replay it.
    if (!clip.complete) pcmCache.delete(item.id)
  }

  async function submit(text = draft.value) {
    text = text.trim()
    if (!text || !ready.value) return
    stopListening()
    const item = { id: nextId++, text, voice: settings.value.voice, at: Date.now() }
    history.value.unshift(item)
    for (const old of history.value.splice(MAX_HISTORY)) pcmCache.delete(old.id)
    draft.value = ''
    interim.value = ''
    await generate(item)
  }

  async function replay(item) {
    const clip = pcmCache.get(item.id)
    if (clip?.complete) await run(item.id, async function* () { yield* clip.chunks })
    else await generate(item)
  }

  function removeItem(id) {
    if (activeId.value === id) halt()
    pcmCache.delete(id)
    history.value = history.value.filter((h) => h.id !== id)
  }

  function clearHistory() {
    halt()
    pcmCache.clear()
    history.value = []
  }

  // ---- speech to text (browser Web Speech API) ----
  function startListening() {
    if (!SR || listening.value) return
    halt() // don't transcribe our own output
    recognition = new SR()
    recognition.lang = settings.value.lang
    recognition.interimResults = true
    recognition.continuous = false
    let finalText = ''
    recognition.onresult = (e) => {
      let live = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i]
        if (r.isFinal) finalText += r[0].transcript
        else live += r[0].transcript
      }
      interim.value = live
      if (finalText) draft.value = (draft.value + ' ' + finalText).trim()
    }
    recognition.onerror = (e) => {
      if (e.error === 'no-speech' || e.error === 'aborted') return
      error.value = MIC_ERRORS[e.error] ?? `Speech recognition failed (${e.error}).`
    }
    recognition.onend = () => {
      listening.value = false
      interim.value = ''
      recognition = null
      if (finalText && settings.value.autoSubmit) submit()
    }
    error.value = ''
    recognition.start()
    listening.value = true
  }

  function stopListening() {
    if (recognition) {
      recognition.onend = () => { listening.value = false; interim.value = ''; recognition = null }
      recognition.stop()
    }
    listening.value = false
  }

  function toggleListening() {
    listening.value ? stopListening() : startListening()
  }

  return {
    settings, voices, backendError, health, ready, sttProblem, draft, interim, listening, sttSupported, status, busy,
    error, history, activeId,
    loadVoices, submit, replay, halt, removeItem, clearHistory, toggleListening, stopListening,
  }
})
