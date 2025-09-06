<template>
  <transition name="fade-scale">
    <div
      v-if="open"
      class="position-absolute subnet-menu-surface"
      :style="{ left: x + 'px', top: y + 'px', transform: 'translateY(4px)' }"
      @mousedown.stop
    >
      <v-card elevation="8" density="comfortable" class="pa-1 subnet-card" rounded="lg">
        <v-list density="compact" nav class="py-1" style="min-width:230px;">
          <v-list-subheader class="text-overline opacity-70">Subnet Actions</v-list-subheader>
          <v-list-item
            value="create-subnet"
            prepend-icon="mdi-access-point-network"
            title="Create Subnet here"
            @click="$emit('create-subnet')"
          />
          <v-list-item
            value="add-peer"
            prepend-icon="mdi-account-plus"
            title="Add Peer in this Subnet"
            @click="$emit('create-peer')"
          />
          <v-list-item
            value="connect"
            prepend-icon="mdi-connection"
            title="Connect…"
            @click="$emit('connect')"
          />
          <v-divider class="my-1" />
            <v-list-item
              value="info"
              prepend-icon="mdi-information-outline"
              title="Subnet Info"
              @click="$emit('info')"
            />
        </v-list>
      </v-card>
    </div>
  </transition>
</template>

<script setup lang="ts">
defineProps<{ open: boolean; x: number; y: number }>();
defineEmits<{ (e:'create-peer'): void; (e:'info'): void; (e:'create-subnet'): void; (e:'connect'): void }>();
</script>

<style scoped>
.fade-scale-enter-active, .fade-scale-leave-active { transition: all .14s cubic-bezier(.4,0,.2,1); }
.fade-scale-enter-from, .fade-scale-leave-to { opacity:0; transform:translateY(8px) scale(.96); }
.subnet-card :deep(.v-list-item) { border-radius:8px; }
.subnet-menu-surface { z-index: 1000; }
</style>
