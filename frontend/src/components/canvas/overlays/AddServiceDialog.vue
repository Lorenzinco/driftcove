<template>
  <v-dialog v-model="open" max-width="560">
    <v-card>
      <v-card-title class="d-flex justify-space-between align-center">
        <span>Add Service to {{ peerLabel }}</span>
        <v-btn icon="mdi-close" variant="text" @click="close" />
      </v-card-title>
      <v-divider />
      <v-card-text class="text-body-2">
        <v-alert
          v-if="error"
          type="error"
          class="mb-3"
          density="comfortable"
          :text="error"
        />
        <v-form @submit.prevent="submit" ref="formRef">
          <v-text-field
            v-model="serviceName"
            label="Service Name"
            :disabled="loading"
            required
            density="comfortable"
            autofocus
          />
          <v-text-field
            v-model="department"
            label="Department"
            :disabled="loading"
            density="comfortable"
          />
          <v-text-field
            v-model.number="port"
            label="Port"
            :disabled="loading"
            type="number"
            min="1"
            max="65535"
            required
            density="comfortable"
          />
          <div class="d-flex flex-column mb-2">
            <div class="d-flex align-center ga-4">
              <div class="text-caption">Protocols:</div>
              <v-checkbox
                v-model="tcpSelected"
                :disabled="loading"
                label="TCP"
                color="red"
                density="comfortable"
                hide-details
              />
              <v-checkbox
                v-model="udpSelected"
                :disabled="loading"
                label="UDP"
                color="blue"
                density="comfortable"
                hide-details
              />
            </div>
            <div class="text-caption text-medium-emphasis mt-1">
              Select one or both. Both = service reachable via TCP &amp; UDP.
            </div>
          </div>
          <v-textarea
            v-model="description"
            label="Description"
            :disabled="loading"
            rows="2"
            auto-grow
            density="comfortable"
          />
          <div class="text-caption text-medium-emphasis mb-3">
            Name must be unique across the network. Port must be free on this
            peer. It is not possibile to assign a service on a port in tcp and
            another service on the same port as udp, either a services uses both
            protocols or just one.
          </div>
          <v-btn
            :loading="loading"
            color="primary"
            type="submit"
            block
            prepend-icon="mdi-cloud-plus"
            >Add Service</v-btn
          >
        </v-form>
        <v-expand-transition>
          <div v-if="conflicts.length" class="mt-3">
            <div class="text-caption font-italic mb-1">Conflicts:</div>
            <v-chip
              v-for="c in conflicts"
              :key="c"
              color="error"
              size="small"
              class="ma-1"
              variant="tonal"
              >{{ c }}</v-chip
            >
          </div>
        </v-expand-transition>
      </v-card-text>
      <v-divider />
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="close">Cancel</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
<script setup lang="ts">
import { ref, computed } from "vue";
import { useNetworkStore } from "@/stores/network";
import { useBackendInteractionStore } from "@/stores/backendInteraction";

const open = ref(false);
const loading = ref(false);
const error = ref("");
const serviceName = ref("");
const department = ref("");
const port = ref<number | null>(null);
const description = ref("");
const targetPeerId = ref<string | null>(null);
const conflicts = ref<string[]>([]);
const formRef = ref();

// Protocol selection via two checkboxes
const tcpSelected = ref(true);
const udpSelected = ref(false);
const protocolsSelected = computed<string[]>(() => {
  const arr: string[] = [];
  if (tcpSelected.value) arr.push("tcp");
  if (udpSelected.value) arr.push("udp");
  return arr;
});

const net = useNetworkStore();
const backend = useBackendInteractionStore();

const peer = computed(() => net.peers.find((p) => p.id === targetPeerId.value));
const peerLabel = computed(() => (peer.value ? peer.value.name : "Peer"));

function show(peerId: string) {
  targetPeerId.value = peerId;
  serviceName.value = "";
  department.value = "";
  port.value = null;
  description.value = "";
  error.value = "";
  conflicts.value = [];
  tcpSelected.value = true;
  udpSelected.value = false;
  open.value = true;
}
function close() {
  open.value = false;
}

function validateLocal(): boolean {
  conflicts.value = [];
  if (!serviceName.value.trim()) {
    error.value = "Service name required";
    return false;
  }
  if (
    port.value == null ||
    isNaN(port.value) ||
    port.value < 1 ||
    port.value > 65535
  ) {
    error.value = "Valid port required";
    return false;
  }
  if (protocolsSelected.value.length === 0) {
    error.value = "Select at least one protocol";
    return false;
  }
  // Global name uniqueness
  const nameExists = net.peers.some((p) =>
    Object.keys(p.services || {}).some((n) => n === serviceName.value.trim()),
  );
  if (nameExists) conflicts.value.push("Service name already exists");
  // Port uniqueness on this peer
  if (peer.value) {
    const portClash = Object.values(peer.value.services || {}).some(
      (s: any) => Number(s.port) === Number(port.value),
    );
    if (portClash) conflicts.value.push("Port already in use on this peer");
  }
  if (conflicts.value.length) {
    error.value = "Resolve conflicts before submitting";
    return false;
  }
  error.value = "";
  return true;
}

async function submit() {
  if (!peer.value) {
    error.value = "Peer not found";
    return;
  }
  if (!validateLocal()) return;
  loading.value = true;
  try {
    const protocolToSend =
      protocolsSelected.value.length === 2
        ? "both"
        : protocolsSelected.value[0];
    // Updated API call includes protocol
    const ok = await backend.createService(
      peer.value.name,
      serviceName.value.trim(),
      department.value.trim(),
      Number(port.value),
      description.value.trim(),
      protocolToSend,
    );
    if (!ok) {
      error.value = backend.lastError || "Failed to create service";
      return;
    }
    open.value = false;
  } catch (e: any) {
    error.value = e?.message || "Unexpected error";
  } finally {
    loading.value = false;
  }
}

defineExpose({ show, close });
</script>
