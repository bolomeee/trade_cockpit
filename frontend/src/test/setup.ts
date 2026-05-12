import '@testing-library/jest-dom'
import { vi } from 'vitest'

// Radix UI pointer capture APIs required for Select/DropdownMenu/Popover in JSDOM
window.HTMLElement.prototype.hasPointerCapture = vi.fn()
window.HTMLElement.prototype.setPointerCapture = vi.fn()
window.HTMLElement.prototype.releasePointerCapture = vi.fn()
window.HTMLElement.prototype.scrollIntoView = vi.fn()
