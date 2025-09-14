<template>
<div class="flex flex-row justify-center pa-6 items-center">
    <div class="flex flex-col items-center justify-center text-center mb-2">
        <v-img
            src="@/assets/logo.png"
            alt="Application Logo"
            class="mx-auto w-25"
        />
        <h1 class="text-h4 font-weight-medium m-0">
            Network administration
        </h1>
    </div>
    <div class="flex flex-col w-full items-center">
        <v-card
            width="420"
            elevation="6"
            class="mx-auto flex flex-col items-center justify-center text-center"
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
                        label="Email"
                        name="email"
                        type="email"
                        autocomplete="email"
                        prepend-inner-icon="mdi-email"
                        required
                        clearable
                    />
                    <v-text-field
                        label="Password"
                        name="password"
                        type="password"
                        autocomplete="current-password"
                        prepend-inner-icon="mdi-lock"
                        required
                    />

                    <div class="d-flex justify-space-between align-center mt-1">
                        <v-checkbox
                            density="compact"
                            hide-details
                            label="Remember me"
                        />
                        <v-btn variant="text" size="small">Forgot password?</v-btn>
                    </div>

                    <v-btn
                        type="submit"
                        color="primary"
                        class="mt-4"
                        block
                    >
                        Login
                    </v-btn>

                    <div class="text-center text-body-2 mt-4">
                        <span>Don't have an account?</span>
                        <v-btn variant="text" size="small">Register</v-btn>
                    </div>
                </v-form>
            </v-card-text>
        </v-card>
    </div>
</div>
</template>

<script lang="ts" setup>

</script>