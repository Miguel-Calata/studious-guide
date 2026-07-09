import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { SectionList } from '@/components/sections/SectionList'
import type { CompendiumSection } from '@/types/compendium'

const sections: CompendiumSection[] = [
  {
    id: 's1',
    project_id: 'p1',
    section_number: 2,
    section_name: 'Epidemiología',
    content: 'x',
    model_used: 'gemini',
    dosification: 'STANDARD',
    input_tokens: null,
    output_tokens: null,
    cost_usd: null,
    status: 'completed',
    prompt_version: null,
    notion_page_id: null,
    error_message: null,
    created_at: '2026-07-06T18:00:00Z',
    updated_at: '2026-07-06T18:00:00Z',
  },
  {
    id: 's2',
    project_id: 'p1',
    section_number: 1,
    section_name: 'Resumen',
    content: 'y',
    model_used: null,
    dosification: 'MAX',
    input_tokens: null,
    output_tokens: null,
    cost_usd: null,
    status: 'failed',
    prompt_version: null,
    notion_page_id: null,
    error_message: 'boom',
    created_at: '2026-07-06T18:00:00Z',
    updated_at: '2026-07-06T18:00:00Z',
  },
]

describe('SectionList', () => {
  it('ordena por número de sección y muestra estados', () => {
    render(<SectionList sections={sections} onSelect={() => {}} />)
    const rows = screen.getAllByRole('button')
    expect(rows[0]).toHaveTextContent('1.')
    expect(rows[0]).toHaveTextContent('Resumen')
    expect(rows[0]).toHaveTextContent('Fallida')
    expect(rows[1]).toHaveTextContent('2.')
    expect(rows[1]).toHaveTextContent('Completada')
  })

  it('llama a onSelect con la sección clicada', async () => {
    const onSelect = vi.fn()
    render(<SectionList sections={sections} onSelect={onSelect} />)
    await userEvent.click(screen.getByText('Epidemiología'))
    expect(onSelect).toHaveBeenCalledWith(
      expect.objectContaining({ id: 's1' })
    )
  })
})
