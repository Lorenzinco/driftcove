<template>
  <transition name="fade-scale">
    <div
      v-if="open"
      class="position-absolute peer-menu-surface"
      :style="{ left: x + 'px', top: y + 'px', transform: 'translateY(4px)' }"
      @mousedown.stop
    >
      <v-card class="pa-1 peer-card" density="comfortable" elevation="8" rounded="lg">
        <v-list class="py-1" density="compact" nav style="min-width:230px;">
          <v-list-subheader class="text-overline opacity-70">Peer Actions</v-list-subheader>
          <v-list-item
            prepend-icon="mdi-information-outline"
            title="Open Peer Info"
            value="info"
            @click="$emit('info')"
          />
          <v-list-item
            prepend-icon="mdi-connection"
            title="Connect this peer"
            value="connect"
            @click="$emit('connect')"
          />
          <v-divider class="my-1" />
          <v-list-item
            class="text-error"
            prepend-icon="mdi-delete-outline"
            title="Delete Peer"
            value="delete"
            @click="$emit('delete')"
          />
        </v-list>
      </v-card>
    </div>
  </transition>
</template>

<script setup lang="ts">
  withDefaults(defineProps<{ open: boolean, x: number, y: number }>(), { x: 0, y: 0 })
  defineEmits<{ (e: 'info'): void, (e: 'connect'): void, (e: 'delete'): void }>()
</script>

<style scoped>
.fade-scale-enter-active, .fade-scale-leave-active { transition: all .14s cubic-bezier(.4,0,.2,1); }
.fade-scale-enter-from, .fade-scale-leave-to { opacity:0; transform:translateY(8px) scale(.96); }
.peer-card :deep(.v-list-item) { border-radius:8px; }
.peer-menu-surface { z-index: 1000; }
</style>
