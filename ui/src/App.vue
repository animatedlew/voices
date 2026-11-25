<script setup>
import { onMounted } from 'vue'
import { useVoiceStore } from './stores/voice'
import Composer from './components/Composer.vue'
import Controls from './components/Controls.vue'
import History from './components/History.vue'

const store = useVoiceStore()
onMounted(store.loadVoices)
</script>

<template>
  <div class="min-h-screen bg-base-200">
    <div class="navbar bg-base-100 shadow-sm px-4 sticky top-0 z-10">
      <div class="flex-1 gap-2">
        <span class="text-2xl">🎙️</span>
        <span class="text-xl font-bold tracking-tight">Voices</span>
        <span class="badge badge-ghost hidden sm:inline-flex">phonon · local</span>
      </div>
      <select v-model="store.settings.theme" class="select select-sm w-32" aria-label="Theme">
        <option v-for="t in ['light','dark','cupcake','synthwave','dracula','nord','sunset']" :key="t" :value="t">{{ t }}</option>
      </select>
    </div>

    <main class="mx-auto max-w-6xl p-4 grid gap-4 lg:grid-cols-[1fr_20rem]">
      <div class="grid gap-4 content-start">
        <div v-if="store.backendError" role="alert" class="alert alert-error">
          <span>{{ store.backendError }}</span>
          <button class="btn btn-sm" @click="store.loadVoices">Retry</button>
        </div>
        <div v-else-if="store.health && !store.health.ok" role="alert" class="alert alert-warning">
          <div>
            <p class="font-semibold">{{ store.health.problem }}</p>
            <p class="text-sm">{{ store.health.hint }}</p>
          </div>
          <button class="btn btn-sm" @click="store.loadVoices">Check again</button>
        </div>
        <Composer />
        <History />
      </div>
      <Controls class="lg:sticky lg:top-20 self-start" />
    </main>
  </div>
</template>
