let csrf = ''
export function setCsrf(value: string) {
  csrf = value
}
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
  }
}

async function send(path: string, options: RequestInit = {}) {
  const headers = new Headers(options.headers)
  if (!(options.body instanceof FormData) && options.body)
    headers.set('Content-Type', 'application/json')
  if (options.method && options.method !== 'GET') headers.set('X-CSRF-Token', csrf)
  let response: Response
  try {
    response = await fetch(`/api${path}`, { ...options, headers, credentials: 'same-origin' })
  } catch {
    throw new Error('Cannot reach SanketAI. Check that the API is running and try again.')
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    const detail =
      typeof payload.detail === 'string'
        ? payload.detail
        : Array.isArray(payload.detail)
          ? payload.detail.map((e: { msg: string }) => e.msg).join('; ')
          : `Request failed (${response.status})`
    if (response.status === 401 && !path.startsWith('/auth/'))
      window.dispatchEvent(new Event('sanket:session-expired'))
    throw new ApiError(response.status, detail)
  }
  return response
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await send(path, options)
  return response.status === 204 ? (undefined as T) : response.json()
}

export async function download(path: string) {
  const response = await send(path)
  const disposition = response.headers.get('Content-Disposition') ?? ''
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = /filename="([^"]+)"/.exec(disposition)?.[1] ?? 'download'
  link.click()
  URL.revokeObjectURL(url)
}
export function post<T>(path: string, body?: unknown) {
  return api<T>(path, {
    method: 'POST',
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}
