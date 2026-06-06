import { config } from '@vue/test-utils'
import { vi } from 'vitest'

// Vuetify and canvas-oriented components expect several browser APIs that jsdom
// does not implement. Keep these shims small and explicit so component tests run
// close to the browser without requiring a real layout engine.
class ResizeObserverMock {
  observe () {}
  unobserve () {}
  disconnect () {}
}

class IntersectionObserverMock {
  observe () {}
  unobserve () {}
  disconnect () {}
  takeRecords () {
    return []
  }
}

Object.defineProperty(window, 'ResizeObserver', {
  writable: true,
  configurable: true,
  value: ResizeObserverMock,
})
Object.defineProperty(globalThis, 'ResizeObserver', {
  writable: true,
  configurable: true,
  value: ResizeObserverMock,
})
Object.defineProperty(window, 'IntersectionObserver', {
  writable: true,
  configurable: true,
  value: IntersectionObserverMock,
})
Object.defineProperty(globalThis, 'IntersectionObserver', {
  writable: true,
  configurable: true,
  value: IntersectionObserverMock,
})

Object.defineProperty(window, 'matchMedia', {
  writable: true,
  configurable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

// Vuetify uses transition components heavily. Stubbing them makes tests faster
// and removes timing noise while preserving rendered content.
config.global.stubs = {
  'transition': false,
  'transition-group': false,
}
