<template>
  <v-container
    class="fill-height d-flex flex-column align-center justify-center"
  >
    <div class="d-flex align-center mb-10">
      <BrandLogo height="72px" />
    </div>
    <v-card class="pa-4" elevation="4" max-width="480" width="100%">
      <v-card-title class="text-h6 d-flex justify-space-between align-center">
        <span v-if="hasToken">API Token</span>
        <span v-else>Enter API Token</span>
        <v-chip v-if="hasToken" color="primary" size="small" variant="flat">
          Active
        </v-chip>
      </v-card-title>
      <v-divider class="mb-4" />
      <v-card-text class="pt-0">
        <div v-if="!editing && hasToken" class="text-body-2 mb-4">
          A token is already configured. You can proceed to the application or
          update the token.
        </div>

        <v-alert
          v-if="error"
          class="mb-4"
          density="comfortable"
          :text="error"
          type="error"
        />

        <v-form v-if="editing || !hasToken" @submit.prevent="saveToken">
          <v-text-field
            v-model="tokenInput"
            autocomplete="off"
            density="comfortable"
            :disabled="saving"
            label="API Token"
            prepend-inner-icon="mdi-key"
            required
            variant="outlined"
          />
          <div class="text-caption text-medium-emphasis mb-4">
            The token is stored only in memory for this session (not persisted).
            It is sent as a Bearer Authorization header on every backend request
            until you refresh or close the page, after which you must re-enter
            it.
          </div>
          <v-btn
            block
            class="mb-2"
            color="primary"
            :loading="saving"
            prepend-icon="mdi-content-save"
            type="submit"
          >
            Save Token
          </v-btn>
          <v-btn block :disabled="saving" variant="text" @click="cancelEdit">
            Cancel
          </v-btn>
        </v-form>

        <div v-else class="d-flex flex-column ga-2">
          <v-btn
            block
            color="primary"
            prepend-icon="mdi-lan"
            @click="goNetwork"
          >
            Go to Network
          </v-btn>
          <v-btn
            block
            prepend-icon="mdi-pencil"
            variant="tonal"
            @click="startEdit"
          >
            Change Token
          </v-btn>
          <v-btn
            block
            color="error"
            prepend-icon="mdi-delete"
            variant="text"
            @click="clearToken"
          >
            Clear Token
          </v-btn>
        </div>
      </v-card-text>
      <v-divider />
      <v-card-actions class="justify-end">
        <v-btn
          v-if="hasToken && !editing"
          :loading="reloading"
          prepend-icon="mdi-refresh"
          variant="text"
          @click="reloadData"
        >
          Refresh Topology
        </v-btn>
      </v-card-actions>
    </v-card>
    <div class="text-caption mt-6 text-medium-emphasis">
      Driftcove Frontend • Token Gate
    </div>
  </v-container>
</template>

<script lang="ts" setup>
  import { computed, onMounted, ref } from 'vue'
  import { useRouter } from 'vue-router'
  import BrandLogo from '@/components/BrandLogo.vue'
  import { useBackendInteractionStore } from '@/stores/backendInteraction'

  const backend = useBackendInteractionStore()
  const router = useRouter()

  const tokenInput = ref('')
  const saving = ref(false)
  const reloading = ref(false)
  const error = ref('')
  const editing = ref(false)

  const hasToken = computed(() => !!backend.apiToken)

  function startEdit () {
    editing.value = true
    tokenInput.value = backend.apiToken
    error.value = ''
  }
  function cancelEdit () {
    if (!hasToken.value) return
    editing.value = false
    error.value = ''
  }
  function clearToken () {
    backend.setApiToken('')
    tokenInput.value = ''
    editing.value = true
  }

  async function saveToken () {
    if (!tokenInput.value.trim()) {
      error.value = 'Token is required'
      return
    }
    saving.value = true
    error.value = ''
    try {
      backend.setApiToken(tokenInput.value.trim())
      editing.value = false
      reloading.value = true
      await backend.fetchTopology(true)
      // On successful fetch redirect to network
      router.push('/network')
    } catch (error_: any) {
      error.value = error_?.message || 'Failed to save token'
    } finally {
      saving.value = false
      reloading.value = false
    }
  }

  async function reloadData () {
    if (!hasToken.value) return
    reloading.value = true
    error.value = ''
    try {
      await backend.fetchTopology(true)
    } catch (error_: any) {
      error.value = error_?.message || 'Failed to refresh'
    } finally {
      reloading.value = false
    }
  }

  function goNetwork () {
    router.push('/network')
  }

  onMounted(async () => {
    if (hasToken.value) {
      // If a token already exists try an immediate fetch then redirect
      try {
        reloading.value = true
        await backend.fetchTopology(true)
        router.push('/network')
      } finally {
        reloading.value = false
      }
    } else {
      editing.value = true
    }
  })
</script>

<style scoped>
.fill-height {
  min-height: 100vh;
}
</style>
