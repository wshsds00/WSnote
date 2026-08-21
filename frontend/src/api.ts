import axios from 'axios'
const http = axios.create({ baseURL: '/api' })
export const noteApi = {
  list: () => http.get('/notes'),
  create: (d: any) => http.post('/notes', d),
  get: (id: string) => http.get(`/notes/${id}`),
  update: (id: string, d: any) => http.put(`/notes/${id}`, d),
  del: (id: string) => http.delete(`/notes/${id}`),
  rebuild: () => http.post('/index/rebuild'),
  status: () => http.get('/index/status'),
}
export const searchApi = { query: (q: string, k = 5) => http.get('/search', { params: { q, k } }) }
export const chatApi = { ask: (question: string) => http.post('/chat', { question }) }
export const tagApi = { list: () => http.get('/tags') }
