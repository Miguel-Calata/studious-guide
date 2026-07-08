import { z } from 'zod'

export const projectCreateSchema = z.object({
  name: z
    .string()
    .min(1, 'El nombre es requerido')
    .max(255, 'Máximo 255 caracteres'),
  description: z
    .string()
    .max(2000, 'Máximo 2000 caracteres')
    .optional()
    .or(z.literal('').transform(() => undefined)),
})

export type ProjectCreateFormValues = z.infer<typeof projectCreateSchema>
