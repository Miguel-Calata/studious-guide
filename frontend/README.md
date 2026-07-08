# SAM Platform — Frontend

Interfaz web del creador para la plataforma SAM (compendios médicos). SPA en React 18 + Vite + TypeScript + Tailwind CSS + shadcn/ui.

## 🚀 Stack

| Capa | Tecnología |
|------|-----------|
| Framework | React 19 + Vite 8 |
| Lenguaje | TypeScript |
| Router | React Router v6 |
| UI | shadcn/ui (Tailwind CSS) |
| Estado servidor | SWR |
| Forms | react-hook-form + zod |
| Auth | Cookies httpOnly (JWT) |
| Tests | Vitest + React Testing Library |

## 📋 Requisitos

- Node.js 20+
- Backend SAM corriendo en `http://localhost:8000` (ver `../docker` y `../backend`).

## ⚡ Inicio rápido

```bash
# 1. Instalar dependencias
npm install

# 2. Configurar variables (opcional; el default usa el proxy de Vite)
cp .env.example .env

# 3. Levantar en dev
npm run dev
```

El frontend queda en `http://localhost:5173` y el proxy de Vite reenvía
`/api/v1/*` al backend en `http://localhost:8000`.

## 🔐 Autenticación (cookies httpOnly)

- `POST /api/v1/auth/login` y `/auth/refresh` setean cookies `access_token` y
  `refresh_token` con `httpOnly=true`.
- El cliente (`src/api/client.ts`) envía `credentials: include` y reintenta
  automáticamente con `/auth/refresh` ante un `401`.
- El contexto (`src/contexts/AuthContext.tsx`) restaura la sesión con
  `GET /auth/me` al cargar la app.
- No se almacenan tokens en `localStorage`.

## 🧪 Tests

```bash
npm test          # corre todos los tests (vitest run)
npm run test:watch
```

## 🏗️ Build

```bash
npm run build     # tsc -b && vite build
npm run preview   # sirve el build
```
