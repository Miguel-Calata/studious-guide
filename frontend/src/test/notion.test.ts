import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  getNotionStatus,
  connectNotion,
  searchNotionPages,
  updateNotionConfig,
  publishToNotion,
} from '@/api/notion'
import { ApiError } from '@/api/client'

function mockFetch(handler: (url: string, init?: RequestInit) => Response) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) =>
      handler(String(input), init)
    )
  )
}

const ok = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })

describe('api/notion', () => {
  beforeEach(() => vi.resetAllMocks())

  it('getNotionStatus hace GET a /notion/status', async () => {
    mockFetch((url, init) => {
      expect(url).toBe('/api/v1/notion/status')
      expect(init?.method).toBe('GET')
      return ok({
        is_connected: true,
        workspace_name: 'Mi workspace',
        default_parent_page_id: 'abc',
      })
    })
    const res = await getNotionStatus()
    expect(res.is_connected).toBe(true)
    expect(res.workspace_name).toBe('Mi workspace')
  })

  it('connectNotion hace POST con api_key', async () => {
    mockFetch((url, init) => {
      expect(url).toBe('/api/v1/notion/connect')
      expect(init?.method).toBe('POST')
      expect(JSON.parse(init?.body as string)).toEqual({
        api_key: 'secret_abc',
      })
      return ok({
        is_connected: true,
        workspace_name: 'WS',
        default_parent_page_id: null,
      })
    })
    const res = await connectNotion('secret_abc')
    expect(res.is_connected).toBe(true)
  })

  it('searchNotionPages hace GET a /notion/search?q', async () => {
    mockFetch((url, init) => {
      expect(url).toBe('/api/v1/notion/search?query=mi%20busqueda')
      expect(init?.method).toBe('GET')
      return ok([{ id: 'p1', title: 'Página', object: 'page' }])
    })
    const res = await searchNotionPages('mi busqueda')
    expect(res).toHaveLength(1)
    expect(res[0].title).toBe('Página')
  })

  it('updateNotionConfig hace PUT con body', async () => {
    mockFetch((url, init) => {
      expect(url).toBe('/api/v1/notion/config')
      expect(init?.method).toBe('PUT')
      expect(JSON.parse(init?.body as string)).toEqual({
        default_parent_page_id: 'pid',
      })
      return ok({
        is_connected: true,
        workspace_name: null,
        default_parent_page_id: 'pid',
      })
    })
    const res = await updateNotionConfig({ default_parent_page_id: 'pid' })
    expect(res.default_parent_page_id).toBe('pid')
  })

  it('publishToNotion hace POST con parent_page_id', async () => {
    mockFetch((url, init) => {
      expect(url).toBe('/api/v1/projects/proj1/publish/notion')
      expect(init?.method).toBe('POST')
      expect(JSON.parse(init?.body as string)).toEqual({
        parent_page_id: 'ppid',
      })
      return ok({
        project_id: 'proj1',
        compendium_page_id: 'cpid',
        sections_published: [],
        notion_url: 'https://notion.so/cpid',
      })
    })
    const res = await publishToNotion('proj1', 'ppid')
    expect(res.notion_url).toBe('https://notion.so/cpid')
  })

  it('publishToNotion sin parent_page_id envía body null', async () => {
    mockFetch((url, init) => {
      expect(url).toBe('/api/v1/projects/proj1/publish/notion')
      expect(init?.body).toBe('null')
      return ok({
        project_id: 'proj1',
        compendium_page_id: 'cpid',
        sections_published: [],
        notion_url: 'https://notion.so/cpid',
      })
    })
    await publishToNotion('proj1')
  })

  it('propaga ApiError en 409', async () => {
    mockFetch(() =>
      new Response(
        JSON.stringify({ detail: 'Notion no conectado' }),
        { status: 409, headers: { 'Content-Type': 'application/json' } }
      )
    )
    await expect(getNotionStatus()).rejects.toBeInstanceOf(ApiError)
  })
})
