/**
 * Contract for the Task 1.5 silent-refresh interceptor. The active application
 * continues to use its compatible legacy service while this module gives future
 * fetch clients one shared retry shape.
 */
export async function withSilentRefresh<T>(request: () => Promise<T>, refresh: () => Promise<boolean>): Promise<T> {
  try {
    return await request()
  } catch (error) {
    if (!(error instanceof Response) || error.status !== 401 || !(await refresh())) throw error
    return request()
  }
}
