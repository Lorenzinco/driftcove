<template>
  <v-footer app height="44" class="footer-root">
    <div class="social-link d-flex align-center">
      <a href="https://diocane.com" target="_blank" rel="noopener" class="d-inline-flex align-center link-part logo-wrap" title="Driftcove Docs">
        <v-img src="@/assets/logo.svg" width="30" height="30" class="me-2 footer-logo" cover alt="Driftcove" />
      </a>
      <a href="https://github.com/lorenzinco/driftcove" target="_blank" rel="noopener" class="d-inline-flex align-center link-part" title="GitHub">
        <v-icon icon="mdi-github" size="18" class="github-icon" />
      </a>
    </div>

    <div
      class="text-caption text-disabled"
      style="position: absolute; right: 16px;"
    >
      &copy; {{ (new Date()).getFullYear() }} <span class="d-none d-sm-inline-block">Driftcove</span>
      —
      <a
        class="text-decoration-none on-surface"
        href="https://github.com/lorenzinco/driftcove?tab=MIT-1-ov-file#readme"
        rel="noopener noreferrer"
        target="_blank"
      >
        MIT License
      </a>
    </div>
  </v-footer>
</template>

<script setup lang="ts">
  const items = [
    {
      title: 'Driftcove Documentation',
      icon: `@/assets/logo.svg`,
      href: 'https://diocane.com/',
    },
    {
      title: 'Driftcove GitHub',
      icon: `mdi-github`,
      href: 'https://github.com/lorenzinco/driftcove',
    }
  ]
</script>

<style scoped lang="sass">
  .footer-root
    padding-inline: 12px !important

  .social-link
    gap: 4px
    color: rgba(var(--v-theme-on-background), var(--v-disabled-opacity))

  .social-link .link-part
    text-decoration: none
    line-height: 1
    color: inherit
    transition: opacity .2s ease

    &:hover .footer-logo
      opacity: 1

  .footer-logo
    display: inline-block
    opacity: .9
    transition: opacity .2s ease

  .github-icon
    opacity: .75
    transition: opacity .2s ease, color .2s ease
    &:hover
      opacity: 1
</style>
