import { z } from 'zod'

export const loginSchema = z.object({
  email: z.string().email('Ingresa un email válido'),
  password: z.string().min(1, 'La contraseña es requerida'),
})

export type LoginFormValues = z.infer<typeof loginSchema>

export const registerSchema = z
  .object({
    email: z.string().email('Ingresa un email válido'),
    full_name: z.string().min(1, 'El nombre es requerido').optional(),
    password: z
      .string()
      .min(8, 'Mínimo 8 caracteres')
      .max(128, 'Máximo 128 caracteres')
      .regex(/[a-z]/, 'Debe tener al menos una minúscula')
      .regex(/[A-Z]/, 'Debe tener al menos una mayúscula')
      .regex(/\d/, 'Debe tener al menos un dígito'),
    confirm_password: z.string(),
  })
  .refine((data) => data.password === data.confirm_password, {
    message: 'Las contraseñas no coinciden',
    path: ['confirm_password'],
  })

export type RegisterFormValues = z.infer<typeof registerSchema>
