import { RouterProvider } from 'react-router-dom'
import { router } from './routes'
import { Provider } from 'react-redux'
import { store } from './store/store'
import { hydrateTokensFromStorage } from './services/api'
import { TooltipProvider } from '@/components/ui/tooltip'

hydrateTokensFromStorage().catch(() => {})

function App() {
  return (
    <Provider store={store}>
      <TooltipProvider delayDuration={0}>
        <RouterProvider router={router} />
      </TooltipProvider>
    </Provider>
  )
}

export default App
