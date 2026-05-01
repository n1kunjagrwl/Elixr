import { Component, type ErrorInfo, type ReactNode } from 'react'
import { RotateCcw } from 'lucide-react'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
  isChunkError: boolean
}

const CHUNK_ERROR_PATTERNS = [
  'Failed to fetch dynamically imported module',
  'Importing a module script failed',
  'error loading dynamically imported module',
  'Loading chunk',
]

function isChunkLoadError(error: Error): boolean {
  return CHUNK_ERROR_PATTERNS.some((p) => error.message.includes(p))
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, isChunkError: false }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, isChunkError: isChunkLoadError(error) }
  }

  componentDidCatch(error: Error, _info: ErrorInfo) {
    if (isChunkLoadError(error)) {
      // Stale service worker served old assets — reload to get fresh ones.
      window.location.reload()
    }
  }

  render() {
    if (this.state.hasError && !this.state.isChunkError) {
      return (
        <div className="flex h-full flex-col items-center justify-center gap-4 p-8 text-center">
          <p className="text-sm text-muted-foreground">Something went wrong loading this page.</p>
          <button
            onClick={() => this.setState({ hasError: false, isChunkError: false })}
            className="flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground"
          >
            <RotateCcw className="h-4 w-4" />
            Try again
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
