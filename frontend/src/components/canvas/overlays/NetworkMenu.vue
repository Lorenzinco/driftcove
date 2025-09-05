<template>
  <transition name="fade-scale">
    <div
      v-if="open"
      class="position-absolute network-menu-surface"
      :style="{ left: x + 'px', top: y + 'px', transform: 'translateY(4px)' }"
      @mousedown.stop
    >
      <v-card elevation="8" density="comfortable" class="pa-1 network-card" rounded="lg">
        <v-list density="compact" nav class="py-1" style="min-width:230px;">
          <v-list-subheader class="text-overline opacity-70">Network Actions</v-list-subheader>
          <v-list-item
            value="create-subnet"
            prepend-icon="mdi-access-point-network"
            title="Create Subnet here"
            @click="$emit('create-subnet')"
          />
        </v-list>
      </v-card>
    </div>
  </transition>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ open:boolean; x:number; y:number }>(), { x:0, y:0 });
defineEmits<{ (e:'create-subnet'):void }>();
</script>

<style scoped>
.fade-scale-enter-active, .fade-scale-leave-active { transition: all .14s cubic-bezier(.4,0,.2,1); }
.fade-scale-enter-from, .fade-scale-leave-to { opacity:0; transform:translateY(8px) scale(.96); }
.network-card :deep(.v-list-item) { border-radius:8px; }
.network-menu-surface { z-index: 1000; }
</style>
