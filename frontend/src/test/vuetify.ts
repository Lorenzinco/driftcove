import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'

export function createTestVuetify () {
  return createVuetify({
    components,
    directives,
    theme: {
      defaultTheme: 'light',
    },
  })
}
