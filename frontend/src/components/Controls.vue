<script setup>
import { useVoiceStore } from '../stores/voice'
const store = useVoiceStore()

const langs = [
  ['en-US', 'English (US)'], ['en-GB', 'English (UK)'], ['en-AU', 'English (AU)'],
  ['es-ES', 'Español'], ['fr-FR', 'Français'], ['de-DE', 'Deutsch'],
  ['it-IT', 'Italiano'], ['pt-BR', 'Português'], ['ja-JP', '日本語'],
]
</script>

<template>
  <aside class="card bg-base-100 shadow">
    <div class="card-body gap-3">
      <h2 class="card-title">Controls</h2>

      <fieldset class="fieldset">
        <legend class="fieldset-legend">Voice</legend>
        <select v-model="store.settings.voice" class="select w-full" :disabled="!store.voices.length">
          <option v-for="v in store.voices" :key="v" :value="v">{{ v }}</option>
        </select>
      </fieldset>

      <fieldset class="fieldset">
        <legend class="fieldset-legend w-full justify-between">
          Speed <span class="font-mono opacity-70">{{ store.settings.speed.toFixed(2) }}×</span>
        </legend>
        <input v-model.number="store.settings.speed" type="range" min="0.5" max="2" step="0.05" class="range range-primary range-sm w-full" aria-label="Speed" />
        <p class="label whitespace-normal">Applied in your browser, so pitch shifts with speed. Takes effect on the next clip.</p>
      </fieldset>

      <fieldset class="fieldset">
        <legend class="fieldset-legend w-full justify-between">
          Volume <span class="font-mono opacity-70">{{ Math.round(store.settings.volume * 100) }}%</span>
        </legend>
        <input v-model.number="store.settings.volume" type="range" min="0" max="1.5" step="0.05" class="range range-secondary range-sm w-full" aria-label="Volume" />
      </fieldset>

      <div class="divider my-0"></div>

      <fieldset class="fieldset">
        <legend class="fieldset-legend">Speech input language</legend>
        <select v-model="store.settings.lang" class="select select-sm w-full">
          <option v-for="[code, name] in langs" :key="code" :value="code">{{ name }}</option>
        </select>
      </fieldset>

      <label class="flex items-center justify-between gap-3 cursor-pointer">
        <span class="text-sm">Speak automatically after I stop talking</span>
        <input v-model="store.settings.autoSubmit" type="checkbox" class="toggle toggle-primary toggle-sm" />
      </label>

      <button class="btn btn-sm btn-ghost" @click="Object.assign(store.settings, { speed: 1, volume: 1 })">Reset speed &amp; volume</button>
    </div>
  </aside>
</template>
