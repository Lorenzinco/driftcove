<template>
  <v-container
    class="fill-height d-flex flex-column align-center justify-center"
  >
    <div class="d-flex align-center mb-10">
      <v-img
        alt="Driftcove Shield"
        src="@/assets/logo.svg"
        height="88"
        width="88"
        style="object-fit: contain"
      />
      <v-img
        alt="Driftcove Wordmark"
        src="@/assets/logo.png"
        width="360"
        height="120"
        style="object-fit: contain"
      />
    </div>
    <v-card max-width="480" width="100%" elevation="4" class="pa-4">
      <v-card-title class="text-h6 d-flex justify-space-between align-center">
        <span v-if="hasToken">API Token</span>
        <span v-else>Enter API Token</span>
        <v-chip v-if="hasToken" size="small" color="primary" variant="flat">
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
          type="error"
          density="comfortable"
          class="mb-4"
          :text="error"
        />

        <v-form @submit.prevent="saveToken" v-if="editing || !hasToken">
          <v-text-field
            v-model="tokenInput"
            label="API Token"
            :disabled="saving"
            prepend-inner-icon="mdi-key"
            variant="outlined"
            density="comfortable"
            autocomplete="off"
            required
          />
          <div class="text-caption text-medium-emphasis mb-4">
            The token is stored only in memory for this session (not persisted).
            It is sent as a Bearer Authorization header on every backend request
            until you refresh or close the page, after which you must re-enter
            it.
          </div>
          <v-btn
            block
            color="primary"
            :loading="saving"
            type="submit"
            prepend-icon="mdi-content-save"
            class="mb-2"
          >
            Save Token
          </v-btn>
          <v-btn block variant="text" :disabled="saving" @click="cancelEdit">
            Cancel
          </v-btn>
        </v-form>

        <div v-else class="d-flex flex-column ga-2">
          <v-btn
            color="primary"
            block
            prepend-icon="mdi-lan"
            @click="goNetwork"
          >
            Go to Network
          </v-btn>
          <v-btn
            block
            variant="tonal"
            prepend-icon="mdi-pencil"
            @click="startEdit"
          >
            Change Token
          </v-btn>
          <v-btn
            block
            color="error"
            variant="text"
            prepend-icon="mdi-delete"
            @click="clearToken"
          >
            Clear Token
          </v-btn>
        </div>
      </v-card-text>
      <v-divider />
      <v-card-actions class="justify-end">
        <v-btn
          variant="text"
          v-if="hasToken && !editing"
          @click="reloadData"
          :loading="reloading"
          prepend-icon="mdi-refresh"
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
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useBackendInteractionStore } from "@/stores/backendInteraction";

const backend = useBackendInteractionStore();
const router = useRouter();

const tokenInput = ref("");
const saving = ref(false);
const reloading = ref(false);
const error = ref("");
const editing = ref(false);

const hasToken = computed(() => !!backend.apiToken);

function startEdit() {
  editing.value = true;
  tokenInput.value = backend.apiToken;
  error.value = "";
}
function cancelEdit() {
  if (!hasToken.value) return;
  editing.value = false;
  error.value = "";
}
function clearToken() {
  backend.setApiToken("");
  tokenInput.value = "";
  editing.value = true;
}

async function saveToken() {
  if (!tokenInput.value.trim()) {
    error.value = "Token is required";
    return;
  }
  saving.value = true;
  error.value = "";
  try {
    backend.setApiToken(tokenInput.value.trim());
    editing.value = false;
    reloading.value = true;
    await backend.fetchTopology(true);
    // On successful fetch redirect to network
    router.push("/network");
  } catch (e: any) {
    error.value = e?.message || "Failed to save token";
  } finally {
    saving.value = false;
    reloading.value = false;
  }
}

async function reloadData() {
  if (!hasToken.value) return;
  reloading.value = true;
  error.value = "";
  try {
    await backend.fetchTopology(true);
  } catch (e: any) {
    error.value = e?.message || "Failed to refresh";
  } finally {
    reloading.value = false;
  }
}

function goNetwork() {
  router.push("/network");
}

onMounted(async () => {
  if (!hasToken.value) {
    editing.value = true;
  } else {
    // If a token already exists try an immediate fetch then redirect
    try {
      reloading.value = true;
      await backend.fetchTopology(true);
      router.push("/network");
    } finally {
      reloading.value = false;
    }
  }
});
</script>

<style scoped>
.fill-height {
  min-height: 100vh;
}
</style>
