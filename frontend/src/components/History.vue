<script setup>
import { useVoiceStore } from '../stores/voice'
const store = useVoiceStore()
</script>

<template>
  <section v-if="store.history.length" class="grid gap-3">
    <div class="flex items-center justify-between px-1">
      <h2 class="font-semibold opacity-70">History</h2>
      <button class="btn btn-ghost btn-xs" @click="store.clearHistory">Clear all</button>
    </div>
    <TransitionGroup name="list" tag="div" class="grid gap-3">
      <div
        v-for="h in store.history"
        :key="h.id"
        class="chat chat-end"
      >
        <div class="chat-header text-xs opacity-60 mb-1">
          {{ h.voice }} · {{ new Date(h.at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }}
        </div>
        <div class="chat-bubble chat-bubble-primary max-w-full whitespace-pre-wrap">{{ h.text }}</div>
        <div class="chat-footer mt-1 flex gap-1">
          <button v-if="store.activeId === h.id" class="btn btn-xs btn-outline" @click="store.halt">
            <span v-if="store.status === 'generating'" class="loading loading-spinner loading-xs"></span>■ Stop
          </button>
          <button v-else class="btn btn-xs btn-ghost" @click="store.replay(h)">▶ Replay</button>
          <button class="btn btn-xs btn-ghost" @click="store.draft = h.text">Edit</button>
          <button class="btn btn-xs btn-ghost" aria-label="Remove" @click="store.removeItem(h.id)">✕</button>
        </div>
      </div>
    </TransitionGroup>
  </section>
  <p v-else class="text-center opacity-50 py-6">Nothing yet. Type or speak, and your words come back in a new voice.</p>
</template>

<style scoped>
.list-enter-active { transition: all .25s ease; }
.list-enter-from { opacity: 0; transform: translateY(-8px); }
</style>
