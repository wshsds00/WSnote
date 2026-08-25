<template>
  <div class="chat-wrap">
    <div class="chat-head">
      <h1 class="page-title">知识问答</h1>
      <p class="page-sub">基于知识库的 RAG 问答，回答附带引用来源</p>
      <el-button v-if="messages.length" text :icon="Delete" class="clear-btn" @click="clear">
        清空对话
      </el-button>
    </div>

    <div ref="listEl" class="chat-list">
      <div v-if="messages.length === 0" class="empty-state">
        <div class="empty-icon">💬</div>
        <p>问点什么吧，比如「讲讲索引是怎么构建的」</p>
        <div class="suggestions">
          <el-tag
            v-for="s in suggestions"
            :key="s"
            effect="plain"
            class="suggest-tag ws-clickable"
            @click="ask(s)"
          >
            {{ s }}
          </el-tag>
        </div>
      </div>

      <template v-for="(m, i) in messages" :key="m.id">
        <!-- 用户问题 -->
        <div class="msg user">
          <div class="bubble user-bubble">{{ m.question }}</div>
        </div>

        <!-- 回答 -->
        <div class="msg ai">
          <el-alert
            v-if="m.degraded"
            class="degraded-alert"
            title="LLM 未配置，已降级为仅检索（只返回命中的原文片段）"
            type="warning"
            :closable="false"
            show-icon
          />
          <div class="bubble ai-bubble vditor-reset" v-html="m.answerHtml"></div>
          <span v-if="m.streaming" class="stream-caret"></span>

          <el-collapse v-if="m.citations.length" class="citations">
            <el-collapse-item v-for="(c, j) in m.citations" :key="j">
              <template #title>
                <span class="cite-title">
                  <span class="cite-num">{{ j + 1 }}</span>
                  {{ c.note_id }}
                  <span v-if="c.heading_path" class="cite-heading">· {{ c.heading_path }}</span>
                </span>
              </template>
              <p class="cite-text">{{ c.text }}</p>
              <el-button
                text
                size="small"
                type="primary"
                :icon="Position"
                class="cite-jump"
                @click="jump(c.note_id)"
              >
                打开原文
              </el-button>
            </el-collapse-item>
          </el-collapse>
          <div v-else class="no-cite">（无引用）</div>
        </div>
      </template>

      <!-- 思考中占位（开始流式输出后隐藏） -->
      <div v-if="thinking" class="msg ai">
        <div class="bubble ai-bubble thinking">
          <span class="th-dot"></span><span class="th-dot"></span><span class="th-dot"></span>
          思考中…
        </div>
      </div>
    </div>

    <div class="chat-input">
      <el-input
        v-model="question"
        type="textarea"
        :rows="2"
        resize="none"
        placeholder="输入问题，回车提问…"
        @keydown.enter.prevent="onEnter"
      />
      <el-button
        type="primary"
        :loading="loading"
        :icon="Promotion"
        class="send-btn"
        @click="ask(question)"
      >
        提问
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import Vditor from 'vditor'
import 'vditor/dist/index.css'
import { Delete, Position, Promotion } from '@element-plus/icons-vue'
import { chatApi } from '../api'
import type { ChatCitation } from '../api'
import { useTheme } from '../composables/useTheme'

const router = useRouter()
const { isDark } = useTheme()
const question = ref('')
const loading = ref(false)
const listEl = ref<HTMLElement | null>(null)

interface ChatMsg {
  id: number
  question: string
  answer: string
  answerHtml: string
  citations: ChatCitation[]
  degraded: boolean
  streaming: boolean
}

let seq = 0
const messages = ref<ChatMsg[]>([])
const streamingMsg = computed(() => messages.value.find((m) => m.streaming))
// 检索/首个 token 前的等待态；一旦开始流式输出则隐藏占位
const thinking = computed(() => loading.value && !streamingMsg.value)

// LLM 答案 → HTML（vditor 的 Lute 渲染，与笔记/整理页同源）
async function mdToHtml(md: string): Promise<string> {
  try {
    return await Vditor.md2html(md, { mode: isDark.value ? 'dark' : 'light' })
  } catch {
    // 渲染失败时按纯文本转义展示，避免漏出原始标记
    return md.replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' })[c] as string)
  }
}

const suggestions = ['介绍一下 WSnote 的架构', '混合检索是怎么工作的', '如何部署这个项目']

async function ask(text?: string) {
  const q = (text ?? question.value).trim()
  if (!q || loading.value) return
  question.value = ''
  loading.value = true
  const msg: ChatMsg = {
    id: seq++,
    question: q,
    answer: '',
    answerHtml: '',
    citations: [],
    degraded: false,
    streaming: true,
  }
  messages.value.push(msg)
  scrollToBottom()

  let renderTimer: number | null = null
  let renderTick: (() => void) | null = null
  const scheduleRender = (fn: () => void) => {
    renderTick = fn
    if (renderTimer !== null) return
    renderTimer = window.setTimeout(() => {
      renderTimer = null
      const fn2 = renderTick
      renderTick = null
      if (fn2) fn2()
    }, 90)
  }
  const applyHtml = async () => {
    const html = await mdToHtml(msg.answer)
    if (msg.answerHtml === html) return
    msg.answerHtml = html
    scrollToBottom()
  }
  let settled = false
  const finish = (ok: boolean) => {
    if (settled) return
    settled = true
    msg.streaming = false
    if (renderTimer !== null) {
      window.clearTimeout(renderTimer)
      renderTimer = null
    }
    renderTick = null
    loading.value = false
    if (ok) scrollToBottom('smooth')
  }

  await chatApi.askStream(q, {
    onMeta: (e) => {
      msg.citations = e.citations ?? []
      msg.degraded = e.degraded
      if (e.degraded && e.message) {
        msg.answer = e.message
        applyHtml()
      }
    },
    onDelta: (t) => {
      msg.answer += t
      scheduleRender(applyHtml)
    },
    onError: (m) => {
      if (!msg.answer) {
        msg.answer = m
        applyHtml()
      }
      finish(false)
    },
    onDone: () => {
      if (renderTimer !== null) {
        window.clearTimeout(renderTimer)
        renderTimer = null
      }
      renderTick = null
      applyHtml().then(() => finish(true))
    },
  })
  // 兜底：若 askStream 提前返回（极端情况），确保状态复位
  if (!settled) finish(true)
}

// 深色/浅色切换时，重新渲染已存在的回答
watch(isDark, async () => {
  for (const m of messages.value) {
    m.answerHtml = await mdToHtml(m.answer)
  }
})

function onEnter(e: KeyboardEvent) {
  if (e.shiftKey) return // 换行
  ask()
}

function clear() {
  messages.value = []
}

function jump(noteId: string) {
  router.push({ path: '/', query: { note: noteId } })
}

async function scrollToBottom(behavior: ScrollBehavior = 'auto') {
  await nextTick()
  listEl.value?.scrollTo({ top: listEl.value.scrollHeight, behavior })
}
</script>

<style scoped>
.chat-wrap {
  max-width: 860px;
  margin: 0 auto;
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 24px 24px 0;
}
.chat-head {
  display: flex;
  align-items: baseline;
  gap: 12px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--ws-border);
}
.page-title {
  margin: 0;
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.02em;
}
.page-sub {
  margin: 0;
  color: var(--ws-muted);
  font-size: 14px;
}
.clear-btn {
  margin-left: auto;
  color: var(--ws-muted);
}

.chat-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.empty-state {
  margin: auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  color: var(--ws-muted);
  text-align: center;
}
.empty-icon {
  font-size: 44px;
  opacity: 0.7;
}
.suggestions {
  margin-top: 8px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: center;
}
.suggest-tag:hover {
  border-color: var(--ws-primary);
  color: var(--ws-primary);
}

.msg {
  display: flex;
}
.msg.user {
  justify-content: flex-end;
}
.msg.ai {
  flex-direction: column;
  align-items: flex-start;
}
.bubble {
  max-width: 78%;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
}
.user-bubble {
  background: var(--ws-primary);
  color: #fff;
  border-bottom-right-radius: 4px;
}
.ai-bubble {
  background: var(--ws-surface);
  border: 1px solid var(--ws-border);
  border-bottom-left-radius: 4px;
  box-shadow: var(--ws-shadow);
  white-space: normal;
  padding: 12px 16px;
}
.degraded-alert {
  width: 100%;
  margin-bottom: 6px;
}
.stream-caret {
  width: 7px;
  height: 15px;
  margin-top: 4px;
  margin-left: 2px;
  border-radius: 2px;
  background: var(--ws-primary);
  display: inline-block;
  animation: blink 1s infinite alternate;
}
.thinking {
  color: var(--ws-muted);
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.th-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--ws-primary);
  animation: blink 1s infinite alternate;
}
.th-dot:nth-child(2) {
  animation-delay: 0.2s;
}
.th-dot:nth-child(3) {
  animation-delay: 0.4s;
}
@keyframes blink {
  from {
    opacity: 0.25;
  }
  to {
    opacity: 1;
  }
}

.citations {
  width: 100%;
  margin-top: 8px;
  border: 1px solid var(--ws-border);
  border-radius: 8px;
  background: var(--ws-surface);
}
.cite-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
}
.cite-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 4px;
  border-radius: 9px;
  background: var(--ws-primary-soft);
  color: var(--ws-primary);
  font-size: 12px;
}
.cite-heading {
  color: var(--ws-muted);
  font-weight: 400;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cite-text {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--ws-foreground);
  opacity: 0.85;
}
.cite-jump {
  margin-top: 4px;
}
.no-cite {
  margin-top: 6px;
  font-size: 12px;
  color: var(--ws-muted);
}

.chat-input {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  padding: 14px 0 20px;
  border-top: 1px solid var(--ws-border);
}
.send-btn {
  height: 58px;
  flex-shrink: 0;
}
</style>
