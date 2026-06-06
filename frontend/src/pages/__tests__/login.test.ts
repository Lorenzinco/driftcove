import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { defineComponent, h } from 'vue'
import LoginPage from '../login.vue'

const SlotStub = defineComponent({
  setup (_, { slots }) {
    return () => h('div', slots.default?.())
  },
})

const FieldStub = defineComponent({
  props: {
    label: String,
  },
  setup (props) {
    return () => h('label', props.label)
  },
})

const ButtonStub = defineComponent({
  setup (_, { slots }) {
    return () => h('button', slots.default?.())
  },
})

describe('login page', () => {
  it('renders the sign-in form fields and actions', () => {
    const wrapper = mount(LoginPage, {
      global: {
        stubs: {
          'v-img': SlotStub,
          'v-card': SlotStub,
          'v-toolbar': SlotStub,
          'v-toolbar-title': SlotStub,
          'v-spacer': SlotStub,
          'v-icon': SlotStub,
          'v-card-text': SlotStub,
          'v-form': SlotStub,
          'v-text-field': FieldStub,
          'v-checkbox': FieldStub,
          'v-btn': ButtonStub,
        },
      },
    })

    expect(wrapper.text()).toContain('Network administration')
    expect(wrapper.text()).toContain('Sign In')
    expect(wrapper.text()).toContain('Email')
    expect(wrapper.text()).toContain('Password')
    expect(wrapper.text()).toContain('Remember me')
    expect(wrapper.text()).toContain('Forgot password?')
    expect(wrapper.text()).toContain('Login')
    expect(wrapper.text()).toContain('Register')
  })
})
