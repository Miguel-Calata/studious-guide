import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { DocumentUploader } from '@/components/documents/DocumentUploader'
import { DocumentList } from '@/components/documents/DocumentList'
import type { SourceDocument } from '@/types/document'

function makeFile(name: string): File {
  return new File(['x'], name, { type: 'application/pdf' })
}

describe('DocumentUploader', () => {
  beforeEach(() => vi.resetAllMocks())

  it('sube por grupos de tipo inferido al soltar archivos', async () => {
    const calls: Array<{ url: string; type: string }> = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if (url.includes('/projects/p1/documents') && init?.method === 'POST') {
          const body = init.body as FormData
          calls.push({
            url,
            type: String(body.get('document_type')),
          })
          return new Response(
            JSON.stringify({ documents: [] }),
            { status: 201, headers: { 'Content-Type': 'application/json' } }
          )
        }
        return new Response('{}', { status: 200 })
      })
    )

    const onUploaded = vi.fn()
    render(
      <MemoryRouter>
        <DocumentUploader projectId="p1" onUploaded={onUploaded} />
      </MemoryRouter>
    )

    const dropzone = screen.getByText(/Arrastra y suelta/i).parentElement!
    const files = [makeFile('KDIGO_AKI.pdf'), makeFile('articulo_lancet.pdf')]
    const dt = {
      files,
      items: files.map((f) => ({ kind: 'file', type: f.type, getAsFile: () => f })),
      types: ['Files'],
    }
    fireEvent.drop(dropzone, { dataTransfer: dt })

    await waitFor(() => expect(onUploaded).toHaveBeenCalled())
    expect(calls).toHaveLength(2)
    expect(calls.map((c) => c.type).sort()).toEqual(['article', 'guideline'])
  })

  it('muestra error si se supera el límite de 15 archivos', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{}')))
    render(
      <MemoryRouter>
        <DocumentUploader projectId="p1" onUploaded={() => {}} />
      </MemoryRouter>
    )
    const dropzone = screen.getByText(/Arrastra y suelta/i).parentElement!
    const files = Array.from({ length: 16 }, (_, i) => makeFile(`doc${i}.pdf`))
    const dt = {
      files,
      items: files.map((f) => ({ kind: 'file', type: f.type, getAsFile: () => f })),
      types: ['Files'],
    }
    fireEvent.drop(dropzone, { dataTransfer: dt })
    await waitFor(() =>
      expect(screen.getByRole('alert').textContent).toMatch(/Máximo 15/)
    )
  })
})

describe('DocumentList', () => {
  beforeEach(() => vi.resetAllMocks())

  const docs: SourceDocument[] = [
    {
      id: 'd1',
      project_id: 'p1',
      filename: 'KDIGO_AKI.pdf',
      file_size: 2_500_000,
      document_type: 'guideline',
      status: 'uploaded',
      created_at: '2026-07-06T18:00:00Z',
      updated_at: '2026-07-06T18:00:00Z',
    },
  ]

  it('muestra nombre, tipo y tamaño formateado', () => {
    render(
      <MemoryRouter>
        <DocumentList documents={docs} isLoading={false} onChanged={() => {}} />
      </MemoryRouter>
    )
    expect(screen.getByText('KDIGO_AKI.pdf')).toBeTruthy()
    expect(screen.getByText('Guía clínica')).toBeTruthy()
    expect(screen.getByText('2.4 MB')).toBeTruthy()
  })

  it('solicita confirmación antes de eliminar', async () => {
    const onChanged = vi.fn()
    render(
      <MemoryRouter>
        <DocumentList documents={docs} isLoading={false} onChanged={onChanged} />
      </MemoryRouter>
    )
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: /Acciones/i }))
    await user.click(await screen.findByRole('menuitem', { name: /Eliminar/i }))
    expect(await screen.findByText(/Seguro que quieres eliminar/i)).toBeTruthy()

    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(null, { status: 204 }))
    )
    await user.click(screen.getByRole('button', { name: 'Eliminar' }))
    await waitFor(() => expect(onChanged).toHaveBeenCalled())
  })
})
