<!-- components/BrandLogo.vue -->
<template>
  <picture>
    <!-- Dark mode -->
    <source
      media="(prefers-color-scheme: dark)"
      :srcset="darkLogo"
      type="image/svg+xml"
    />
    <!-- Light mode fallback -->
    <img
      alt="Driftcove Logo"
      decoding="async"
      :class="imgClass"
      loading="eager"
      :src="lightLogo"
      :style="{ height }"
    />
  </picture>
</template>

<script setup>
import darkLogo from "@/assets/driftcove_dark.svg";
import lightLogo from "@/assets/driftcove_light.svg";

defineProps({
  height: { type: String, default: "80px" },
  imgClass: { type: String, default: "" },
});
</script>
