/**
 * Catálogo de modelos disponibles en OpenRouter.
 *
 * Para agregar/quitar/cambiar modelos, edita esta lista.
 * El backend tiene la misma lista en: backend/app/modules/ai_gateway/models.py
 */

export interface AiModel {
  id: string
  label: string
}

export const MODELS: AiModel[] = [
  { id: 'anthropic/claude-opus-4.8', label: 'Claude Opus 4.8' },
  { id: 'anthropic/claude-sonnet-5', label: 'Claude Sonnet 5' },
  { id: 'google/gemini-3.1-pro-preview', label: 'Gemini 3.1 Pro' },
  { id: 'openai/gpt-5-pro', label: 'GPT-5 Pro' },
  { id: 'openai/gpt-4o', label: 'GPT-4o' },
  { id: 'qwen/qwen3-vl-235b-a22b-instruct', label: 'Qwen3 VL 235B' },
  { id: 'google/gemini-3.5-flash', label: 'Gemini 3.5 Flash' },
  { id: 'deepseek/deepseek-v4-flash', label: 'DeepSeek V4 Flash' },
  { id: 'openai/gpt-4o-mini', label: 'GPT-4o Mini' },
  { id: 'qwen/qwen3.6-flash', label: 'Qwen3.6 Flash' },
  { id: 'meta-llama/llama-3.3-70b-instruct:free', label: 'Llama 3.3 70B (free)' },
  { id: 'mistralai/mistral-small-3.2-24b-instruct', label: 'Mistral Small 3.2' },
  { id: 'poolside/laguna-xs-2.1:free', label: 'Laguna XS 2.1 (free)' },
  { id: 'tencent/hy3:free', label: 'HY3 (free)' },
  { id: 'tencent/hy3', label: 'HY3' },
  { id: 'x-ai/grok-4.5', label: 'Grok 4.5' },
]

export const DEFAULT_MODEL = 'google/gemini-3.1-pro-preview'
