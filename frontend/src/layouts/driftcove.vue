<template>
    <v-app>
    <!-- ChatGPT-like right drawer -->
    <v-navigation-drawer
    app
    location="right"
    v-model="store.inspectorOpen"
    :temporary="display.smAndDown.value"
    width="360"
    elevation="2"
    >
        <NetworkInspector />
    </v-navigation-drawer>


    <v-main>
        <router-view />
    </v-main>
    </v-app>
</template>


<script setup lang="ts">
    import { useDisplay } from 'vuetify'
    import NetworkInspector from '@/components/NetworkInspector.vue'
    import { useNetworkStore } from '@/stores/network'


    const store = useNetworkStore()
    const display = useDisplay()
</script>

<style scoped>
/* Fix double right offset: inner v-main shouldn't inherit outer drawer shift */
:deep(.v-main .v-main) {
    --v-layout-right: 0 !important;
    padding-right: 0 !important;
    margin-right: 0 !important;
}
</style>