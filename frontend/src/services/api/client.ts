import type { AxiosInstance } from 'axios'
import axios from 'axios'

let runtimeApiToken: string | null = null
let client: AxiosInstance | null = null
let onUnauthorized: (() => void) | null = null

export function resolveBaseURL () {
  const explicit = import.meta.env.VITE_API_BASE_URL as string | undefined
  if (explicit) {
    return explicit.replace(/\/$/, '')
  }

  try {
    const url = new URL(window.location.href)
    if (url.port === '5173') {
      url.port = '8000'
    }
    return url.origin
  } catch {
    return 'http://localhost:8000'
  }
}

export function configureUnauthorizedHandler (handler: () => void) {
  onUnauthorized = handler
}

export function setRuntimeApiToken (token: string) {
  runtimeApiToken = token || null

  if (!client) {
    return
  }
  if (runtimeApiToken) {
    client.defaults.headers.common.Authorization = `Bearer ${runtimeApiToken}`
  } else {
    delete client.defaults.headers.common.Authorization
  }
}

export function getClient () {
  if (client) {
    return client
  }

  client = axios.create({ baseURL: resolveBaseURL(), timeout: 10_000 })

  client.interceptors.request.use(config => {
    if (runtimeApiToken) {
      config.headers = config.headers || {};
      (config.headers as any).Authorization = `Bearer ${runtimeApiToken}`
    }
    return config
  })

  client.interceptors.response.use(
    response => response,
    error => {
      if (error?.response?.status === 401) {
        runtimeApiToken = null
        if (client) {
          delete client.defaults.headers.common.Authorization
        }
        onUnauthorized?.()
        if (window.location.pathname !== '/') {
          window.location.replace('/')
        }
      }
      return Promise.reject(error)
    },
  )

  return client
}
