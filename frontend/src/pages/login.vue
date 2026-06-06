<template>
  <div class="flex flex-row justify-center pa-6 items-center">
    <div class="flex flex-col items-center justify-center text-center mb-2">
      <v-img
        alt="Application Logo"
        class="mx-auto w-25"
        src="@/assets/logo.png"
      />
      <h1 class="text-h4 font-weight-medium m-0">
        Network administration
      </h1>
    </div>
    <div class="flex flex-col w-full items-center">
      <v-card
        class="mx-auto flex flex-col items-center justify-center text-center"
        elevation="6"
        width="420"
      >
        <v-toolbar color="primary" density="comfortable" flat>
          <v-toolbar-title class="font-weight-medium">Sign In</v-toolbar-title>
          <v-spacer />
          <v-btn icon variant="text">
            <v-icon>mdi-account</v-icon>
          </v-btn>
        </v-toolbar>

        <v-card-text class="w-100">
          <v-form @submit.prevent="() => {}">
            <v-text-field
              autocomplete="email"
              clearable
              label="Email"
              name="email"
              prepend-inner-icon="mdi-email"
              required
              type="email"
            />
            <v-text-field
              autocomplete="current-password"
              label="Password"
              name="password"
              prepend-inner-icon="mdi-lock"
              required
              type="password"
            />

            <div class="d-flex justify-space-between align-center mt-1">
              <v-checkbox
                density="compact"
                hide-details
                label="Remember me"
              />
              <v-btn size="small" variant="text">Forgot password?</v-btn>
            </div>

            <v-btn
              block
              class="mt-4"
              color="primary"
              type="submit"
            >
              Login
            </v-btn>

            <div class="text-center text-body-2 mt-4">
              <span>Don't have an account?</span>
              <v-btn size="small" variant="text">Register</v-btn>
            </div>
          </v-form>
        </v-card-text>
      </v-card>
    </div>
  </div>
</template>

<script lang="ts" setup>

</script>
