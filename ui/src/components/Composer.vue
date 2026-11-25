<script setup>
import { useVoiceStore } from '../stores/voice'
const store = useVoiceStore()

function onKey(e) {
  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey || !e.shiftKey)) {
    e.preventDefault()
    store.submit()
  }
}
</script>

<template>
  <section class="card bg-base-100 shadow">
    <div class="card-body gap-3">
      <div class="flex items-center justify-between">
        <h2 class="card-title">Say something</h2>
        <div class="flex items-center gap-2 text-sm" aria-live="polite">
          <span v-if="store.listening" class="badge badge-error gap-1"><span class="loading loading-ring loading-xs"></span>Listening</span>
          <span v-else-if="store.status === 'generating'" class="badge badge-warning gap-1"><span class="loading loading-dots loading-xs"></span>Generating</span>
          <span v-else-if="store.status === 'playing'" class="badge badge-success gap-1">Playing</span>
          <span v-else class="badge badge-ghost">Ready</span>
        </div>
      </div>

      <div class="relative">
        <textarea
          v-model="store.draft"
          @keydown="onKey"
          rows="4"
          class="textarea w-full text-base"
          aria-label="Text to speak"
          :placeholder="store.sttSupported ? 'Type here, or press the mic and talk…' : 'Type here (' + store.sttProblem + ')'"
        ></textarea>
        <p v-if="store.interim" class="absolute left-3 bottom-2 right-3 text-sm italic opacity-60 truncate pointer-events-none">{{ store.interim }}</p>
      </div>

      <p v-if="!store.sttSupported" class="text-sm opacity-70">Voice input is off: {{ store.sttProblem }}</p>
      <div v-if="store.error" role="alert" class="alert alert-warning py-2 text-sm">{{ store.error }}</div>

      <div class="flex flex-wrap items-center gap-2">
        <button
          class="btn btn-circle btn-lg"
          :class="store.listening ? 'btn-error animate-pulse' : 'btn-primary'"
          :disabled="!store.sttSupported"
          :title="store.sttSupported ? 'Speak' : store.sttProblem"
          :aria-pressed="store.listening"
          aria-label="Toggle microphone"
          @click="store.toggleListening"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-7 w-7" viewBox="0 0 24 24" fill="currentColor"><path d="M12 14a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3Zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-3.08A7 7 0 0 0 19 11h-2Z"/></svg>
        </button>

        <button class="btn btn-secondary" :disabled="!store.draft.trim() || !store.ready" @click="store.submit()">
          Speak it
          <kbd class="kbd kbd-sm text-base-content hidden sm:inline-flex">↵</kbd>
        </button>
        <button v-if="store.busy" class="btn btn-outline" @click="store.halt">■ Stop</button>
        <button v-if="store.draft" class="btn btn-ghost ml-auto" @click="store.draft = ''">Clear</button>
      </div>
    </div>
  </section>
</template>
