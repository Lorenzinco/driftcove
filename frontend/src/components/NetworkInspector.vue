<template>
  <div class="pa-4">
    <div class="d-flex align-center justify-space-between mb-2">
      <div class="text-h6 d-flex align-center">Network</div>
    </div>
    <v-divider class="my-4" />
    <v-expansion-panels multiple>
      <v-expansion-panel value="subnets">
        <v-expansion-panel-title class="text-subtitle-2">
          <v-icon icon="mdi-lan" size="18" class="me-1" /> Subnetworks ({{
            store.subnets.length
          }})
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <v-list density="compact">
            <v-list-item
              v-for="s in store.subnets"
              :key="s.id"
              :title="s.name + ' (' + s.cidr + ')'"
              @click="selectSubnet(s)"
              :active="
                !!(
                  store.selection &&
                  store.selection.type === 'subnet' &&
                  store.selection.id === s.id
                )
              "
              rounded="sm"
            >
              <template #prepend>
                <v-icon
                  icon="mdi-hexagon-multiple-outline"
                  size="16"
                  class="me-1"
                />
              </template>
            </v-list-item>
            <v-list-item
              v-if="!store.subnets.length"
              title="No subnets"
              disabled
            />
          </v-list>
        </v-expansion-panel-text>
      </v-expansion-panel>
      <v-expansion-panel v-if="store.selectedSubnet" value="hosts">
        <v-expansion-panel-title class="text-subtitle-2">
          <v-icon icon="mdi-server" size="18" class="me-1" /> Hosts ({{
            hostPeers.length
          }})
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <v-list density="compact">
            <v-list-item
              v-for="p in hostPeers"
              :key="p.id"
              :title="p.name + (p.ip ? ' (' + p.ip + ')' : '')"
              @click="selectPeer(p)"
              :active="
                !!(
                  store.selection &&
                  store.selection.type === 'peer' &&
                  store.selection.id === p.id
                )
              "
              rounded="sm"
            >
              <template #prepend>
                <v-icon icon="mdi-server" size="16" class="me-1" />
              </template>
              <template #append>
                <v-icon
                  :color="
                    Date.now() / 1000 - (p as any).lastHandshake < 300
                      ? 'blue'
                      : 'yellow'
                  "
                  icon="mdi-lightbulb"
                  size="16"
                />
              </template>
            </v-list-item>
            <v-list-item v-if="!hostPeers.length" title="No hosts" disabled />
          </v-list>
        </v-expansion-panel-text>
      </v-expansion-panel>
      <v-expansion-panel v-if="store.selectedSubnet" value="peers">
        <v-expansion-panel-title class="text-subtitle-2">
          <v-icon icon="mdi-account-group" size="18" class="me-1" /> Peers ({{
            nonHostPeers.length
          }})
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <v-list density="compact">
            <v-list-item
              v-for="p in nonHostPeers"
              :key="p.id"
              :title="p.name + (p.ip ? ' (' + p.ip + ')' : '')"
              @click="selectPeer(p)"
              :active="
                !!(
                  store.selection &&
                  store.selection.type === 'peer' &&
                  store.selection.id === p.id
                )
              "
              rounded="sm"
            >
              <template #prepend>
                <v-icon
                  icon="mdi-account-circle-outline"
                  size="16"
                  class="me-1"
                />
              </template>
              <template #append>
                <v-icon
                  :color="
                    Date.now() / 1000 - (p as any).lastHandshake < 300
                      ? 'blue'
                      : 'yellow'
                  "
                  icon="mdi-lightbulb"
                  size="16"
                />
              </template>
            </v-list-item>
            <v-list-item
              v-if="!nonHostPeers.length"
              title="No peers"
              disabled
            />
          </v-list>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>
    <div class="d-flex mt-3 ga-2 w-100">
      <v-btn
        class="flex-grow-1"
        color="primary"
        variant="outlined"
        prepend-icon="mdi-download"
        @click="exportTopology"
        :disabled="applying"
      >
        Export
      </v-btn>
      <v-btn
        class="flex-grow-1"
        color="primary"
        variant="outlined"
        prepend-icon="mdi-upload"
        @click="beginImport"
        :disabled="applying"
      >
        Import
      </v-btn>
      <input
        ref="importInput"
        type="file"
        accept="application/json"
        class="d-none"
        @change="handleImportFile"
      />
    </div>
    <div class="mt-3">
      <v-btn
        block
        :color="backend.topologyDirty ? 'info' : 'success'"
        :loading="applying"
        prepend-icon="mdi-content-save"
        @click="applyToBackend"
        :disabled="applying || !backend.topologyDirty"
      >
        {{
          backend.topologyDirty && !applying
            ? "Save Changes"
            : "All Changes Saved"
        }}
      </v-btn>
    </div>
    <v-alert
      v-if="applyMessage"
      class="mt-3"
      density="comfortable"
      dismissible
      :type="applySuccess ? 'success' : 'error'"
      @click:close="applyMessage = ''"
    >
      {{ applyMessage }}
    </v-alert>
    <div style="height: 80px; flex-shrink: 0"></div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, nextTick } from "vue";
import { useBackendInteractionStore } from "@/stores/backendInteraction";
import { useNetworkStore } from "@/stores/network";
import { emitRedraw } from "@/utils/bus";

const store = useNetworkStore();
const backend = useBackendInteractionStore();
const confirmOpen = ref(false);
const applying = ref(false);
const applyMessage = ref("");
const applySuccess = ref(false);
const importInput = ref<HTMLInputElement | null>(null);

// Categorised peer lists
const hostPeers = computed(() => {
  const selSubnetId = store.selectedSubnet?.id || null;
  if (!selSubnetId) return [];
  return store.peers.filter((p) => p.host && p.subnetId === selSubnetId);
});
const nonHostPeers = computed(() => {
  const selSubnetId = store.selectedSubnet?.id || null;
  if (!selSubnetId) return [];
  return store.peers.filter((p) => !p.host && p.subnetId === selSubnetId);
});

const problematicLinksInNetwork = computed(() => {
  const links = store.links;
  const problems: any[] = [];
  for (const p of store.peers) {
    const outgoingP2P = links.filter(
      (l) => l.fromId === p.id && l.kind === "p2p",
    );
    const incomingP2P = links.filter(
      (l) => l.toId === p.id && l.kind === "p2p",
    );
    const outgoingService = links.filter(
      (l) => l.fromId === p.id && l.kind === "service",
    );
    const incomingService = links.filter(
      (l) => l.toId === p.id && l.kind === "service",
    );
    // Outgoing p2p vs outgoing service
    for (const pp of outgoingP2P) {
      for (const ps of outgoingService)
        if (pp.toId === ps.toId) problems.push(pp);
    }
    // Outgoing p2p vs incoming service
    for (const pp of outgoingP2P) {
      for (const ps of incomingService)
        if (pp.toId === ps.fromId) problems.push(pp);
    }
    // Incoming p2p vs outgoing service
    for (const pp of incomingP2P) {
      for (const ps of outgoingService)
        if (pp.fromId === ps.toId) problems.push(pp);
    }
    // Incoming p2p vs incoming service
    for (const pp of incomingP2P) {
      for (const ps of incomingService)
        if (pp.fromId === ps.fromId) problems.push(pp);
    }
  }
  return problems;
});

// Subnet color handling
const hexColor = ref("");
// Vuetify v-color-picker in rgba mode emits object { r,g,b,a } (numbers 0-255 except a 0-1)
const pickerRgba = ref<{
  r: number;
  g: number;
  b: number;
  a: number;
} | null>(null);

function subnetRgbaToComponents(rgbaNum: number) {
  const r = (rgbaNum >> 24) & 0xff;
  const g = (rgbaNum >> 16) & 0xff;
  const b = (rgbaNum >> 8) & 0xff;
  const a = (rgbaNum & 0xff) / 255;
  return { r, g, b, a };
}
function componentsToRgbaNumber(r: number, g: number, b: number, a: number) {
  const aByte = Math.round(a * 255) & 0xff;
  return ((r & 0xff) << 24) | ((g & 0xff) << 16) | ((b & 0xff) << 8) | aByte;
}
function updateColorModels() {
  const s = store.selectedSubnet as any;
  if (!s || typeof s.rgba !== "number") {
    hexColor.value = "";
    pickerRgba.value = null;
    return;
  }
  const { r, g, b, a } = subnetRgbaToComponents(s.rgba);
  hexColor.value = `#${r.toString(16).padStart(2, "0")}${g.toString(16).padStart(2, "0")}${b.toString(16).padStart(2, "0")}${aByteHex(a)}`;
  pickerRgba.value = { r, g, b, a };
}
function aByteHex(a: number) {
  const v = Math.round(a * 255);
  return v.toString(16).padStart(2, "0");
}
function applyHexColor() {
  const s = store.selectedSubnet as any;
  if (!s) return;
  const v = hexColor.value.replace("#", "").trim();
  if (![6, 8].includes(v.length)) return; // ignore invalid
  const r = Number.parseInt(v.slice(0, 2), 16);
  const g = Number.parseInt(v.slice(2, 4), 16);
  const b = Number.parseInt(v.slice(4, 6), 16);
  const a = v.length === 8 ? Number.parseInt(v.slice(6, 8), 16) / 255 : 0.9;
  s.rgba = componentsToRgbaNumber(r, g, b, a);
  pickerRgba.value = { r, g, b, a };
  invalidateCanvas();
}
function applyPicker(val: any) {
  if (!val) return;
  const s = store.selectedSubnet as any;
  if (!s) return;
  const r = val.r ?? 0,
    g = val.g ?? 0,
    b = val.b ?? 0,
    a = val.a ?? 1;
  s.rgba = componentsToRgbaNumber(r, g, b, a);
  hexColor.value = `#${r.toString(16).padStart(2, "0")}${g.toString(16).padStart(2, "0")}${b.toString(16).padStart(2, "0")}${aByteHex(a)}`;
  invalidateCanvas();
}
function invalidateCanvas() {
  emitRedraw();
}
watch(
  () => store.selectedSubnet?.id,
  () => updateColorModels(),
  { immediate: true },
);
watch(
  () => (store.selectedSubnet as any)?.rgba,
  () => updateColorModels(),
);

function selectPeer(p: any) {
  // Flag that this selection originated from the inspector (read by canvas logic)
  (window as any).__selectionFromInspector = true;
  store.openPeerDetails(p.id);
  emitRedraw();
}
function selectSubnet(s: any) {
  // Flag that this selection originated from the inspector (read by canvas logic)
  (window as any).__selectionFromInspector = true;
  store.selection = { type: "subnet", id: s.id, name: s.name };
  emitRedraw();
}

function performDelete() {
  store.deleteSelection();
  confirmOpen.value = false;
}

async function applyToBackend() {
  applying.value = true;
  applyMessage.value = "";
  try {
    const payload = backend.buildCurrentTopologyPayload();
    const ok = await backend.uploadTopology(payload);
    applySuccess.value = !!ok;
    applyMessage.value = ok
      ? "Topology uploaded successfully"
      : backend.lastError || "Upload failed";
    if (ok) {
      // Refresh topology from backend to sync any generated keys / adjustments
      await backend.fetchTopology(true);
    }
  } catch (error: any) {
    applySuccess.value = false;
    applyMessage.value = error?.message || "Unexpected error while uploading";
  } finally {
    applying.value = false;
  }
}

function exportTopology() {
  try {
    const payload = backend.buildCurrentTopologyPayload();
    const blob = new Blob([JSON.stringify(payload, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `topology-${new Date().toISOString().replace(/[:.]/g, "-")}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    applyMessage.value = "Topology exported";
    applySuccess.value = true;
  } catch (error: any) {
    applyMessage.value = error?.message || "Failed to export topology";
    applySuccess.value = false;
  }
}

function beginImport() {
  importInput.value?.click();
}

function handleImportFile(ev: Event) {
  const input = ev.target as HTMLInputElement;
  const file = input.files && input.files[0];
  if (!file) return;
  const reader = new FileReader();
  applying.value = true;
  applyMessage.value = "";
  reader.onload = async () => {
    try {
      const text = String(reader.result || "");
      const parsed = JSON.parse(text);
      const ok = await backend.uploadTopology(parsed);
      applySuccess.value = !!ok;
      applyMessage.value = ok
        ? `Imported ${file.name}`
        : backend.lastError || "Import failed";
      if (ok) await backend.fetchTopology(true);
    } catch (error: any) {
      applySuccess.value = false;
      applyMessage.value = error?.message || "Failed to import file";
    } finally {
      applying.value = false;
      // reset input so same file can be chosen again
      if (input) input.value = "";
    }
  };
  reader.onerror = () => {
    applySuccess.value = false;
    applyMessage.value = "Failed to read file";
    applying.value = false;
  };
  reader.readAsText(file);
}
</script>

<style scoped></style>
