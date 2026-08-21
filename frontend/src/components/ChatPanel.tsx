import { useCallback, useEffect, useRef, useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'
import { Bot, LoaderCircle, MessageSquarePlus, Send, Square, RefreshCw } from 'lucide-react'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { api, API_BASE, USE_MOCK } from '@/services/api'
import { streamCall, StreamResponseError, type StreamChunk } from '@/api'
import { tokenStorage } from '@/auth/tokenStorage'
import type { ChatMessageDTO, ChatSessionDTO, ProvenanceEntry } from '@/services/types'
import ProvenanceView from './ProvenanceView'
import DegradedDataBadge from './DegradedDataBadge'
import { cn } from '@/lib/utils'

type ChatPanelProps = { open: boolean; onOpenChange: (open: boolean) => void; merchantRef: string }
type InlineError = { message: string; retryAfter: number; content: string } | null

const answerForMock = (content: string) => content.includes('مقایسه')
  ? 'در مقایسه با هم‌صنفی‌ها، جایگاه شما بالاتر از میانگین است؛ با این حال اندازه نمونه محدود است و نتیجه با اطمینان پایین‌تر تفسیر می‌شود.'
  : content.includes('خارج') ? 'می‌توانم درباره داده‌ها و عملکرد پرداخت پذیرندگی شما کمک کنم. برای موضوع‌های خارج از این حوزه، پاسخ قابل اتکایی ندارم.'
  : 'روند اخیر پرداخت‌های شما مثبت است. فروش در ۳۰ روز گذشته افزایش داشته و نرخ موفقیت تراکنش‌ها در محدوده پایدار قرار دارد.'

const mockChunks = (answer: string, buffered: boolean): StreamChunk[] => buffered
  ? [{ event: 'buffered', data: JSON.stringify({ content: answer, delivery_mode: 'buffered', data_freshness: 'live' }) }]
  : answer.split(/(?<=\s)/).map((data) => ({ event: 'token', data }))

export default function ChatPanel({ open, onOpenChange, merchantRef }: ChatPanelProps) {
  const [sessions, setSessions] = useState<ChatSessionDTO[]>([])
  const [sessionId, setSessionId] = useState<string>()
  const [messages, setMessages] = useState<ChatMessageDTO[]>([])
  const [historyPage, setHistoryPage] = useState(1)
  const [hasOlderMessages, setHasOlderMessages] = useState(false)
  const [draft, setDraft] = useState('')
  const [loading, setLoading] = useState(false)
  const [creating, setCreating] = useState(false)
  const [streaming, setStreaming] = useState(false)
  const [error, setError] = useState<InlineError>(null)
  const [provenance, setProvenance] = useState<Record<string, ProvenanceEntry[]>>({})
  const abortRef = useRef<AbortController | null>(null)

  const loadSessions = useCallback(async () => {
    setLoading(true)
    try {
      const result = await api.listChatSessions(merchantRef)
      setSessions(result.items)
      setSessionId((current) => current ?? result.items[0]?.id)
    } finally { setLoading(false) }
  }, [merchantRef])

  useEffect(() => {
    if (!open) return
    const timer = window.setTimeout(() => void loadSessions(), 0)
    return () => window.clearTimeout(timer)
  }, [open, loadSessions])
  useEffect(() => {
    if (!error || error.retryAfter <= 0) return
    const timer = window.setInterval(() => setError((current) => current ? { ...current, retryAfter: Math.max(0, current.retryAfter - 1) } : null), 1000)
    return () => window.clearInterval(timer)
  }, [error])
  useEffect(() => {
    if (!sessionId) return
    void api.listChatMessages(merchantRef, sessionId).then((result) => {
      setMessages(result.items)
      setHistoryPage(1)
      setHasOlderMessages(result.total > result.items.length)
    }).catch(() => setMessages([]))
  }, [merchantRef, sessionId])

  const loadOlderMessages = async () => {
    if (!sessionId) return
    const nextPage = historyPage + 1
    const result = await api.listChatMessages(merchantRef, sessionId, nextPage)
    setMessages((current) => [...result.items, ...current])
    setHistoryPage(nextPage)
    setHasOlderMessages(result.total > nextPage * result.page_size)
  }

  const createSession = async () => {
    setCreating(true)
    try {
      const session = await api.createChatSession(merchantRef)
      setSessions((value) => [session, ...value])
      setSessionId(session.id)
      setMessages([])
    } finally { setCreating(false) }
  }

  const loadProvenance = async (message: ChatMessageDTO) => {
    if (provenance[message.id] || !message.referenced_insight_ids.length) return
    const rows = (await Promise.all(message.referenced_insight_ids.map((id) => api.getInsightProvenance(merchantRef, id)))).flat()
    setProvenance((current) => ({ ...current, [message.id]: rows }))
  }

  const send = async (content = draft) => {
    const text = content.trim()
    if (!text || !sessionId || streaming) return
    setDraft(''); setError(null); setStreaming(true)
    const user: ChatMessageDTO = { id: `optimistic-user-${Date.now()}`, session_id: sessionId, role: 'user', content: text, referenced_insight_ids: [], created_at: new Date().toISOString() }
    const assistantId = `optimistic-assistant-${Date.now()}`
    setMessages((current) => [...current, user, { id: assistantId, session_id: sessionId, role: 'assistant', content: '', referenced_insight_ids: [], created_at: new Date().toISOString(), delivery_mode: 'streaming' }])
    const controller = new AbortController(); abortRef.current = controller
    let answer = ''; let mode: 'streaming' | 'buffered' = 'streaming'; let freshness: ChatMessageDTO['data_freshness'] = 'live'
    const update = (patch: Partial<ChatMessageDTO>) => setMessages((current) => current.map((message) => message.id === assistantId ? { ...message, ...patch } : message))
    try {
      await streamCall(`${API_BASE}/merchants/${merchantRef}/chat/sessions/${sessionId}/messages`, {
        body: { content: text }, signal: controller.signal,
        headers: tokenStorage.getAccessToken() ? { Authorization: `Bearer ${tokenStorage.getAccessToken()}`, 'Message-Key': crypto.randomUUID() } : { 'Message-Key': crypto.randomUUID() },
        mockChunks: USE_MOCK ? mockChunks(answerForMock(text), text.includes('بدون استریم')) : undefined,
        onChunk: (chunk) => {
          if (chunk.event === 'error') {
            const data = JSON.parse(chunk.data) as { error?: string; retry_after_seconds?: number }
            throw new StreamResponseError(data.error ?? 'CHAT_BUDGET_EXCEEDED', 503, data.error, data.retry_after_seconds)
          }
          if (chunk.event === 'buffered' || chunk.event === 'complete') {
            const data = JSON.parse(chunk.data) as { content?: string; answer?: string; delivery_mode?: 'buffered'; data_freshness?: ChatMessageDTO['data_freshness']; referenced_insight_ids?: string[] }
            answer = data.content ?? data.answer ?? ''; mode = data.delivery_mode ?? 'buffered'; freshness = data.data_freshness ?? 'live'
            update({ content: answer, delivery_mode: mode, data_freshness: freshness, referenced_insight_ids: data.referenced_insight_ids ?? [] })
            return
          }
          answer += chunk.data; update({ content: answer })
        },
      })
      const saved = USE_MOCK ? await api.saveChatMessages(merchantRef, sessionId, text, answer, mode) : undefined
      update(saved ?? { content: answer, delivery_mode: mode, data_freshness: freshness })
    } catch (cause) {
      setMessages((current) => current.filter((message) => message.id !== assistantId))
      if ((cause as Error).name !== 'AbortError') {
        const streamError = cause instanceof StreamResponseError ? cause : undefined
        setError({ content: text, retryAfter: streamError?.retryAfterSeconds ?? 1, message: streamError?.code === 'CHAT_BUDGET_EXCEEDED' ? 'بار گفتگو بالاست؛ کمی بعد دوباره تلاش کنید.' : 'ارسال پیام انجام نشد. دوباره تلاش کنید.' })
      }
    } finally { setStreaming(false); abortRef.current = null }
  }

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void send() } }
  const onSubmit = (event: FormEvent) => { event.preventDefault(); void send() }

  return <Sheet open={open} onOpenChange={onOpenChange}>
    <SheetContent side="left" className="w-full gap-0 p-0 sm:max-w-3xl" dir="rtl" aria-describedby="chat-panel-description">
      <SheetHeader className="border-b border-border/60 pe-14">
        <SheetTitle className="flex items-center gap-2"><Bot className="size-5 text-primary" /> گفتگوی هوشمند</SheetTitle>
        <SheetDescription id="chat-panel-description">پاسخ‌ها بر اساس داده‌ها و تحلیل‌های پذیرندگی شما ارائه می‌شوند.</SheetDescription>
      </SheetHeader>
      <div className="grid min-h-0 flex-1 grid-cols-[10rem_1fr] border-b border-border/60 sm:grid-cols-[13rem_1fr]">
        <aside className="border-e border-border/60 p-2" aria-label="جلسات گفتگو">
          <Button className="mb-2 w-full" size="sm" onClick={createSession} disabled={creating}><MessageSquarePlus aria-hidden="true" /> گفتگوی جدید</Button>
          <ScrollArea className="h-[calc(100dvh-15rem)]"><div className="space-y-1 pe-2">
            {loading ? <LoaderCircle className="mx-auto mt-5 size-4 animate-spin text-muted-foreground" /> : sessions.map((session) => <Button key={session.id} variant={session.id === sessionId ? 'secondary' : 'ghost'} className="h-auto w-full justify-start whitespace-normal text-right text-xs" onClick={() => setSessionId(session.id)}>{new Date(session.last_activity_at).toLocaleDateString('fa-IR')}</Button>)}
          </div></ScrollArea>
        </aside>
        <section className="flex min-w-0 flex-col" aria-label="پیام‌های گفتگو">
          <ScrollArea className="h-[calc(100dvh-15rem)]"><div className="space-y-4 p-4" aria-live="polite">
            {hasOlderMessages && <Button className="mx-auto flex" variant="ghost" size="sm" onClick={() => void loadOlderMessages()}>نمایش پیام‌های پیشین</Button>}
            {messages.map((message) => <article key={message.id} className={cn('flex flex-col gap-2', message.role === 'user' ? 'items-end' : 'items-start')}>
              <div dir="auto" className={cn('max-w-[90%] whitespace-pre-wrap rounded-2xl px-3 py-2 text-sm leading-7', message.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted text-foreground')}>
                {message.content || (streaming && message.role === 'assistant' ? <span className="inline-flex items-center gap-2 text-muted-foreground"><LoaderCircle className="size-3 animate-spin" /> در حال بررسی…</span> : null)}
                {streaming && message.id.startsWith('optimistic-assistant') && message.content && <span className="ms-1 inline-block h-4 w-0.5 animate-pulse bg-primary align-middle" aria-label="در حال تولید پاسخ" />}
              </div>
              {message.data_freshness === 'cached_fallback' && <DegradedDataBadge />}
              {message.role === 'assistant' && message.referenced_insight_ids.length > 0 && (provenance[message.id]
                ? <ProvenanceView rows={provenance[message.id]} title="مشاهده کوئری" />
                : <Button variant="ghost" size="sm" onClick={() => void loadProvenance(message)}>مشاهده کوئری</Button>)}
            </article>)}
            {error && <div className="rounded-xl border border-border bg-muted/50 p-3 text-sm text-muted-foreground" role="alert"><p>{error.message}</p><Button className="mt-2" variant="outline" size="sm" disabled={error.retryAfter > 1} onClick={() => void send(error.content)}><RefreshCw aria-hidden="true" /> تلاش دوباره{error.retryAfter > 1 ? ` (${error.retryAfter} ثانیه)` : ''}</Button></div>}
          </div></ScrollArea>
          <form className="border-t border-border/60 p-3" onSubmit={onSubmit}>
            <label className="sr-only" htmlFor="chat-message">پیام شما</label>
            <div className="flex items-end gap-2"><textarea id="chat-message" dir="auto" className="min-h-11 flex-1 resize-none rounded-xl border bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring" placeholder="سؤال خود را درباره عملکرد پذیرندگی بنویسید…" value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={onKeyDown} disabled={streaming} />
              {streaming ? <Button type="button" variant="outline" size="icon" aria-label="توقف پاسخ" onClick={() => abortRef.current?.abort()}><Square aria-hidden="true" /></Button> : <Button type="submit" size="icon" aria-label="ارسال پیام" disabled={!draft.trim() || !sessionId}><Send aria-hidden="true" /></Button>}
            </div><p className="mt-1 text-xs text-muted-foreground">Enter برای ارسال · Shift+Enter برای خط جدید</p>
          </form>
        </section>
      </div>
    </SheetContent>
  </Sheet>
}
