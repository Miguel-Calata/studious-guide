import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { act } from 'react'
import { SWRConfig } from 'swr'

import { useProjectPolling } from '@/hooks/useProjectPolling'
import type { Project } from '@/types/project'

function makeProject(status: Project['status']): Project {
  return {
    id: 'p1',
    name: 'LRA',
    slug: 'lra',
    description: null,
    status,
    merged_content: null,
    is_published: false,
    public_url: null,
    created_at: '2026-07-06T18:00:00Z',
    updated_at: '2026-07-06T18:00:00Z',
  }
}

function flush() {
  return act(async () => {
    await Promise.resolve()
  })
}

describe('useProjectPolling', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('no revalida (polling detenido) cuando el proyecto está idle', async () => {
    const spy = vi.fn(async () =>
      new Response(JSON.stringify(makeProject('draft')), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    )
    vi.stubGlobal('fetch', spy)

    renderHook(() => useProjectPolling('p1'), {
      wrapper: ({ children }) => (
        <SWRConfig value={{ provider: () => new Map() }}>
          {children}
        </SWRConfig>
      ),
    })
    await flush()

    const afterInitial = spy.mock.calls.length
    expect(afterInitial).toBeGreaterThanOrEqual(1)

    await act(async () => {
      vi.advanceTimersByTime(15000)
      await Promise.resolve()
    })

    expect(spy.mock.calls.length).toBe(afterInitial)
  })

  it('revalida (polling activo) cuando el proyecto está ocupado', async () => {
    const spy = vi.fn(async () =>
      new Response(JSON.stringify(makeProject('extracting')), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    )
    vi.stubGlobal('fetch', spy)

    renderHook(() => useProjectPolling('p1'), {
      wrapper: ({ children }) => (
        <SWRConfig value={{ provider: () => new Map() }}>
          {children}
        </SWRConfig>
      ),
    })
    await flush()

    const afterInitial = spy.mock.calls.length
    expect(afterInitial).toBeGreaterThanOrEqual(1)

    await act(async () => {
      vi.advanceTimersByTime(15000)
      await Promise.resolve()
    })

    expect(spy.mock.calls.length).toBeGreaterThan(afterInitial)
  })
})
