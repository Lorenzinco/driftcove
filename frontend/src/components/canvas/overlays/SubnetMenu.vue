<template>
  <transition name="fade-scale">
    <div
      v-if="open"
      class="position-absolute subnet-menu-surface"
      :style="{ left: x + 'px', top: y + 'px', transform: 'translateY(4px)' }"
      @mousedown.stop
    >
      <v-card class="pa-1 subnet-card" density="comfortable" elevation="8" rounded="lg">
        <v-list class="py-1" density="compact" nav style="min-width:230px;">
          <v-list-subheader class="text-overline opacity-70">Subnet Actions</v-list-subheader>
          <v-list-item
            prepend-icon="mdi-information-outline"
            title="Subnet Info"
            value="info"
            @click="$emit('info')"
          />
          <v-list-item
            prepend-icon="mdi-access-point-network"
            title="Create Subnet here"
            value="create-subnet"
            @click="$emit('create-subnet')"
          />
          <v-list-item
            prepend-icon="mdi-account-plus"
            title="Add Peer in this Subnet"
            value="add-peer"
            @click="$emit('create-peer')"
          />
          <v-list-item
            prepend-icon="mdi-connection"
            title="Connect…"
            value="connect"
            @click="$emit('connect')"
          />
          <v-divider class="my-1" />
          <v-list-item
            class="text-error"
            prepend-icon="mdi-delete-outline"
            title="Delete Subnet"
            value="delete"
            @click="$emit('delete')"
          />
        </v-list>
      </v-card>
    </div>
  </transition>
</template>

<script setup lang="ts">
  defineProps<{ open: boolean, x: number, y: number }>()
  defineEmits<{ (e: 'create-peer'): void, (e: 'info'): void, (e: 'create-subnet'): void, (e: 'connect'): void, (e: 'delete'): void }>()
</script>

<style scoped>
.fade-scale-enter-active, .fade-scale-leave-active { transition: all .14s cubic-bezier(.4,0,.2,1); }
.fade-scale-enter-from, .fade-scale-leave-to { opacity:0; transform:translateY(8px) scale(.96); }
.subnet-card :deep(.v-list-item) { border-radius:8px; }
.subnet-menu-surface { z-index: 1000; }
</style>
