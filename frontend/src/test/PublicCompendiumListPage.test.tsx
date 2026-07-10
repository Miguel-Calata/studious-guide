import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { SWRConfig } from 'swr'

import { PublicCompendiumListPage } from '@/pages/PublicCompendiumListPage'
import type { PublicCompendiumListItem } from '@/types/public'

const compendiums: PublicCompendiumListItem[] = [
  {
    slug: 'lra',
    name: 'LRA',
    description: 'Lesión Renal Aguda',
    section_count: 11,
    published_at: '2026-07-08T00:00:00Z',
  },
  {
    slug: 'dm2',
    name: 'Diabetes Mellitus 2',
    description: null,
    section_count: 11,
    published_at: null,
  },
]

function setup(data: PublicCompendiumListItem[] = compendiums, status = 200) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () =>
      new Response(JSON.stringify(data), {
        status,
        headers: { 'Content-Type': 'application/json' },
      })
    )
  )
}

function renderPage() {
  return render(
    <SWRConfig value={{ provider: () => new Map() }}>
      <MemoryRouter initialEntries={['/compendiums']}>
        <Routes>
          <Route path="/compendiums" element={<PublicCompendiumListPage />} />
        </Routes>
      </MemoryRouter>
    </SWRConfig>
  )
}

describe('PublicCompendiumListPage', () => {
  beforeEach(() => vi.resetAllMocks())

  it('muestra el título Notas', async () => {
    setup()
    renderPage()
    expect(await screen.findByRole('heading', { name: 'Notas' })).toBeTruthy()
  })

  it('muestra las tarjetas de notas', async () => {
    setup()
    renderPage()
    expect(await screen.findByText('LRA')).toBeTruthy()
    expect(await screen.findByText('Diabetes Mellitus 2')).toBeTruthy()
    expect(await screen.findByText('Lesión Renal Aguda')).toBeTruthy()
    expect(screen.getAllByText('Abrir nota →')).toHaveLength(2)
  })

  it('muestra empty state cuando no hay notas', async () => {
    setup([])
    renderPage()
    expect(
      await screen.findByText(/no hay notas publicadas/i)
    ).toBeTruthy()
  })

  it('muestra error cuando falla la carga', async () => {
    setup([], 500)
    renderPage()
    await waitFor(() =>
      expect(
        screen.getByText(/no se pudieron cargar las notas/i)
      ).toBeTruthy()
    )
  })
})
