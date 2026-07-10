const PREFIX = 'ai.model.'

const KEYS = {
  extraction: PREFIX + 'extraction',
  gemini: PREFIX + 'gemini',
  claude: PREFIX + 'claude',
} as const

export type ModelPrefKey = keyof typeof KEYS

function storageKey(key: ModelPrefKey): string {
  return KEYS[key]
}

export function readModelPref(key: ModelPrefKey, fallback: string): string {
  try {
    const value = sessionStorage.getItem(storageKey(key))
    return value ?? fallback
  } catch {
    return fallback
  }
}

export function writeModelPref(key: ModelPrefKey, value: string): void {
  try {
    sessionStorage.setItem(storageKey(key), value)
  } catch {
    /* almacenamiento no disponible (modo privado) */
  }
}
