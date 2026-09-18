import axios from 'axios'
import { ElMessage } from 'element-plus'

export const http = axios.create({ baseURL: '/api' })

// 全局错误拦截：HTTP 错误 → 统一 ElMessage
http.interceptors.response.use(
  (res) => res,
  (err) => {
    const msg = err?.response?.data?.detail || err.message || '请求失败'
    ElMessage.error(msg)
    return Promise.reject(err)
  },
)

// 后端统一返回 {code, data}，这里解包直接拿到 data
function unwrap<T>(body: any): T {
  if (body && typeof body === 'object' && 'code' in body) {
    return body.data as T
  }
  return body as T
}

export interface NoteMeta {
  id: string
  title: string
  tags: string[]
  created: string
  updated: string
}
export interface Note extends NoteMeta {
  content: string
}
export interface RetrievalHit {
  chunk_id: string
  note_id: string
  heading_path: string
  text: string
  score: number
}
export interface ChatCitation {
  note_id: string
  heading_path: string
  text: string
}
export interface ChatAnswer {
  answer: string
  citations: ChatCitation[]
  degraded: boolean
}
export interface ChatStreamHandlers {
  onMeta?: (e: { degraded: boolean; citations: ChatCitation[]; message?: string }) => void
  onDelta?: (text: string) => void
  onError?: (message: string) => void
  onDone?: () => void
}
export interface IndexStatus {
  notes: number
  chunks: number
}

export const noteApi = {
  list: async (): Promise<NoteMeta[]> => unwrap((await http.get('/notes')).data),
  create: async (d: { title: string; content: string; tags: string[] }): Promise<Note> =>
    unwrap((await http.post('/notes', d)).data),
  get: async (id: string): Promise<Note> => unwrap((await http.get(`/notes/${id}`)).data),
  update: async (id: string, d: { title: string; content: string; tags: string[] }): Promise<Note> =>
    unwrap((await http.put(`/notes/${id}`, d)).data),
  del: async (id: string): Promise<{ ok: boolean }> => unwrap((await http.delete(`/notes/${id}`)).data),
  rebuild: async (): Promise<IndexStatus> => unwrap((await http.post('/index/rebuild')).data),
  status: async (): Promise<IndexStatus> => unwrap((await http.get('/index/status')).data),
}

export const searchApi = {
  query: async (q: string, k = 5): Promise<{ hits: RetrievalHit[] }> =>
    unwrap((await http.get('/search', { params: { q, k } })).data),
}

export const chatApi = {
  ask: async (question: string): Promise<ChatAnswer> => unwrap((await http.post('/chat', { question })).data),
  // SSE 流式问答：meta(含 citations/degraded) → delta*N → done；LLM 未配置时后端返回 JSON 降级
  askStream: async (question: string, h: ChatStreamHandlers = {}): Promise<void> => {
    let res: Response
    try {
      res = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      })
    } catch {
      const msg = '网络错误，提问失败'
      ElMessage.error(msg)
      h.onError?.(msg)
      return
    }
    if (!res.ok) {
      let msg = '提问失败'
      try {
        const j = await res.json()
        msg = j.detail || msg
      } catch {
        /* 非 JSON 错误体，用默认文案 */
      }
      ElMessage.error(msg)
      h.onError?.(msg)
      return
    }
    const ctype = res.headers.get('content-type') || ''
    if (!ctype.includes('text/event-stream')) {
      // 降级路径：LLM 未配置 → 后端直接返回 JSON（含引用）
      const body = await res.json()
      const data = unwrap<ChatAnswer>(body)
      h.onMeta?.({ degraded: true, citations: data.citations ?? [], message: data.answer })
      h.onDone?.()
      return
    }
    const reader = res.body!.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    let settled = false
    const dispatch = (ev: any) => {
      if (ev.type === 'meta') h.onMeta?.({ degraded: !!ev.degraded, citations: ev.citations ?? [], message: ev.message })
      else if (ev.type === 'delta') h.onDelta?.(ev.content)
      else if (ev.type === 'error') {
        settled = true
        h.onError?.(ev.message)
      } else if (ev.type === 'done') {
        settled = true
        h.onDone?.()
      }
    }
    try {
      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        let idx
        while ((idx = buf.indexOf('\n\n')) !== -1) {
          const block = buf.slice(0, idx)
          buf = buf.slice(idx + 2)
          const line = block.split('\n').find((l) => l.startsWith('data:'))
          if (!line) continue
          try {
            dispatch(JSON.parse(line.slice(5).trim()))
          } catch {
            /* 忽略无法解析的帧 */
          }
        }
      }
    } catch {
      settled = true
      h.onError?.('读取流失败')
    }
    if (!settled) h.onDone?.() // 流自然结束（如降级 meta 后无 done）也视为完成
  },
}

export const tagApi = {
  list: async (): Promise<Record<string, number>> => unwrap((await http.get('/tags')).data),
}

export interface ImportResult {
  created: NoteMeta[]
  skipped: string[]
}
export interface AnalyzeResult {
  markdown: string
  degraded: boolean
  mode: string
  message?: string
}
export interface AnalyzeStreamHandlers {
  onMeta?: (e: { degraded: boolean; mode: string; message?: string }) => void
  onDelta?: (text: string) => void
  onError?: (message: string) => void
  onDone?: () => void
}

export const processApi = {
  importText: async (d: { text: string; mode?: string; title?: string; tags?: string[] }): Promise<ImportResult> =>
    unwrap((await http.post('/process/import', d)).data),
  // 音频转文字：上传音频文件，返回转写文本
  transcribeAudio: async (file: File): Promise<{ text: string }> => {
    const form = new FormData()
    form.append('file', file)
    const res = await http.post('/process/transcribe', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 600_000,  // 音频转写可能较慢，10 分钟
    })
    return unwrap<{ text: string }>(res.data)
  },
  // SSE 流式整理：后端逐段推送 delta，前端渐进渲染
  analyzeStream: async (d: { text: string; mode: string }, h: AnalyzeStreamHandlers = {}): Promise<void> => {
    let res: Response
    try {
      res = await fetch('/api/process/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(d),
      })
    } catch {
      const msg = '网络错误，整理请求失败'
      ElMessage.error(msg)
      h.onError?.(msg)
      return
    }
    if (!res.ok) {
      let msg = '整理请求失败'
      try {
        const j = await res.json()
        msg = j.detail || msg
      } catch {
        /* 非 JSON 错误体，用默认文案 */
      }
      ElMessage.error(msg)
      h.onError?.(msg)
      return
    }
    const ctype = res.headers.get('content-type') || ''
    if (!ctype.includes('text/event-stream')) {
      // 降级路径：LLM 未配置 → 后端直接返回 JSON
      const body = await res.json()
      const data = unwrap<AnalyzeResult>(body)
      if (data.degraded) h.onMeta?.({ degraded: true, mode: data.mode, message: data.message })
      else if (data.markdown) h.onDelta?.(data.markdown)
      h.onDone?.()
      return
    }
    const reader = res.body!.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    const dispatch = (ev: any) => {
      if (ev.type === 'meta') h.onMeta?.({ degraded: !!ev.degraded, mode: ev.mode, message: ev.message })
      else if (ev.type === 'delta') h.onDelta?.(ev.content)
      else if (ev.type === 'error') h.onError?.(ev.message)
      else if (ev.type === 'done') h.onDone?.()
    }
    try {
      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        let idx
        while ((idx = buf.indexOf('\n\n')) !== -1) {
          const block = buf.slice(0, idx)
          buf = buf.slice(idx + 2)
          const line = block.split('\n').find((l) => l.startsWith('data:'))
          if (!line) continue
          try {
            dispatch(JSON.parse(line.slice(5).trim()))
          } catch {
            /* 忽略无法解析的帧 */
          }
        }
      }
    } catch {
      h.onError?.('读取流失败')
    }
  },
}
