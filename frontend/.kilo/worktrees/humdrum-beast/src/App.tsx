import { RouterProvider } from 'react-router-dom'
import { router } from './routes'
import { Provider } from 'react-redux'
import { store } from './store/store'
import { hydrateTokensFromStorage } from './services/api'

hydrateTokensFromStorage().catch(() => {})

function App() {
  return (
    <Provider store={store}>
      <RouterProvider router={router} />
    </Provider>
  )
}

export default App
