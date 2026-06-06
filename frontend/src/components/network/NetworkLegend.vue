<template>
  <v-card class="mt-4 w-100" variant="tonal">
    <v-card-text>
      <div class="d-flex align-center ga-6">
        <div><span class="legend-dot peer-online" /> Peer (online)</div>
        <div><span class="legend-dot peer-offline" /> Peer (offline)</div>
        <div>
          <span class="subnet-line" />
          Subnet (boundary)
        </div>
        <v-spacer />
        <div class="text-caption text-medium-emphasis">
          Wheel to zoom • Middle drag or Shift+Drag to pan • Del to delete • Esc to exit tool
        </div>
      </div>
    </v-card-text>
  </v-card>
</template>

<style scoped>
.legend-dot {
  width: 12px;
  height: 12px;
  border-radius: 9999px;
  display: inline-block;
  margin-right: 8px;
}

.peer-online {
  background: #7ad7f0;
}

.peer-offline {
  background: #9ca3af;
}

.subnet-line {
  display: inline-block;
  width: 28px;
  height: 0;
  border-top: 2px dotted #7cf29a;
  margin-right: 8px;
  vertical-align: middle;
}
</style>
