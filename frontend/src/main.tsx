import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'sonner'
import './index.css'
import App from '@/App'
import { useThemeStore, applyThemeClass } from '@/store/useThemeStore'

const queryClient = new QueryClient()

// Keep <html>.dark in sync with the persisted theme. The inline script in
// index.html sets the initial class pre-paint (no FOUC); this re-asserts it and
// tracks future toggles.
applyThemeClass(useThemeStore.getState().theme)
useThemeStore.subscribe((s) => applyThemeClass(s.theme))

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
        <Toaster position="bottom-right" />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
