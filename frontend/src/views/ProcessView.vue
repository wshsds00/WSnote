<template>
  <div class="process-wrap">
    <!-- 左栏：输入面板 -->
    <aside class="input-pane">
      <div class="pane-head">
        <h2 class="pane-title">原始文稿</h2>
        <el-button text type="primary" @click="fileInput?.click()">
          选择文本文件
        </el-button>
      </div>
      <input
        ref="fileInput"
        type="file"
        accept=".txt,.md,.mp3,.wav,.m4a,.ogg,.webm,.flac"
        class="hidden-input"
        @change="onFile"
      />
      <!-- 音频上传入口 -->
      <div class="audio-upload" @click="audioInput?.click()">
        <input
          ref="audioInput"
          type="file"
          accept=".mp3,.wav,.m4a,.ogg,.webm,.flac"
          class="hidden-input"
          @change="onFile"
        />
        <div class="audio-upload-icon">🎙️</div>
        <div class="audio-upload-text" v-if="!isAudio">上传音频转写</div>
        <div class="audio-upload-text" v-else>{{ file?.name }}</div>
        <div class="audio-upload-hint" v-if="!isAudio">支持 mp3 / wav / m4a / ogg / webm / flac</div>
        <div class="audio-upload-hint" v-else>点击可重新选择音频文件</div>
      </div>

      <el-input
        v-model="source"
        type="textarea"
        :rows="16"
        resize="none"
        placeholder="粘贴面试录音文字稿、长文档或会议记录…&#10;支持 .txt / .md 文件，或上传音频自动转写"
      />

      <div class="mode-row">
        <span class="mode-label">整理方式</span>
        <el-radio-group v-model="mode" size="small">
          <el-radio-button value="interview">面试整理</el-radio-button>
          <el-radio-button value="general">通用整理</el-radio-button>
          <el-radio-button value="meeting">会议纪要</el-radio-button>
        </el-radio-group>
      </div>

      <!-- 音频文件：两个入口 -->
      <template v-if="isAudio">
        <el-button
          type="primary"
          :loading="transcribing"
          :icon="MagicStick"
          class="run-btn"
          @click="onTranscribeAndAnalyze"
        >
          {{ transcribing ? '转写中，请耐心等待…' : '转写并整理' }}
        </el-button>
        <el-button
          :loading="transcribing"
          class="run-btn"
          @click="onTranscribeOnly"
        >
          {{ transcribing ? '转写中，请耐心等待…' : '仅转写' }}
        </el-button>
        <div v-if="transcribing" class="tip">
          <p>本地模型首次加载较慢，较长音频可能需要数分钟…</p>
        </div>
      </template>
      <!-- 文本文件：原有逻辑 -->
      <el-button
        v-else
        type="primary"
        :loading="loading"
        :icon="MagicStick"
        class="run-btn"
        @click="onAnalyze"
      >
        {{ loading ? '整理中…' : '开始整理' }}
      </el-button>

      <div class="tip">
        <p>提示：AI 整理需 LLM（<code>WSNOTE_LLM_API_KEY</code>）；音频转写优先使用本地 whisper，未安装时需 <code>WSNOTE_ASR_API_KEY</code>。</p>
      </div>
    </aside>

    <!-- 右栏：结果面板 -->
    <section class="result-pane">
      <!-- 空态 -->
      <div v-if="!started" class="result-empty">
        <div class="empty-icon">🧭</div>
        <p>整理结果会显示在这里</p>
      </div>

      <template v-else>
        <el-alert
          v-if="degraded || errorMsg"
          class="degraded-alert"
          :title="errorMsg || 'LLM 不可用，请先配置环境变量 WSNOTE_LLM_API_KEY'"
          type="warning"
          :closable="false"
          show-icon
        />

        <!-- 仅转写模式：复制/下载 -->
        <div v-if="transcribeOnly && done" class="transcribe-actions">
          <el-button @click="copyText">复制全文</el-button>
          <el-button @click="downloadTxt">下载 .txt</el-button>
        </div>
        <div class="result-head">
          <div v-if="!transcribeOnly" class="save-box">
            <el-input v-model="saveTitle" size="large" placeholder="笔记标题" class="save-title" />
            <el-select
              v-model="saveTags"
              multiple
              filterable
              allow-create
              default-first-option
              size="large"
              placeholder="标签（可选）"
              class="save-tags"
            />
            <el-button type="primary" :loading="saving" :disabled="!done" :icon="Check" @click="onSave">
              {{ loading ? '生成中…' : '保存为笔记' }}
            </el-button>
          </div>
          <div v-if="loading && !errorMsg" class="streaming-hint">正在生成，内容实时刷新中…</div>
        </div>

        <div class="preview-container">
          <div id="process-preview" class="preview-box"></div>
        </div>
      </template>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import Vditor from 'vditor'
import 'vditor/dist/index.css'
import { Check, MagicStick } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { noteApi, processApi } from '../api'
import { useTheme } from '../composables/useTheme'
import { readFileText } from '../utils/file'

const router = useRouter()
const { isDark } = useTheme()

const AUDIO_EXTS = new Set(['.mp3', '.wav', '.m4a', '.ogg', '.webm', '.flac'])

const source = ref('')
const mode = ref<'interview' | 'general' | 'meeting'>('interview')
const file = ref<File | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const audioInput = ref<HTMLInputElement | null>(null)
const loading = ref(false)
const saving = ref(false)
const transcribing = ref(false)
const transcribeOnly = ref(false)
const started = ref(false)
const markdown = ref('')
const degraded = ref(false)
const errorMsg = ref('')
const done = ref(false)
const saveTitle = ref('')
const saveTags = ref<string[]>([])
let preview: Vditor | null = null
let flushTimer: number | null = null

const isAudio = computed(() => {
  if (!file.value) return false
  const ext = file.value.name.slice(file.value.name.lastIndexOf('.')).toLowerCase()
  return AUDIO_EXTS.has(ext)
})

const SUGGEST = {
  interview: '面试复盘',
  general: '整理笔记',
  meeting: '会议纪要',
}

function today(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

async function onFile(e: Event) {
  const input = e.target as HTMLInputElement
  const f = input.files?.[0]
  if (!f) return
  file.value = f
  source.value = ''
  transcribeOnly.value = false
  started.value = false
  done.value = false
  const ext = f.name.slice(f.name.lastIndexOf('.')).toLowerCase()
  if (AUDIO_EXTS.has(ext)) {
    input.value = ''  // 清空以便重复选同一文件
    return
  }
  try {
    source.value = await readFileText(f)
  } catch {
    ElMessage.error('读取文件失败')
  }
  input.value = ''
}

function destroyPreview() {
  if (preview) {
    preview.destroy()
    preview = null
  }
}

async function renderPreview(md = '') {
  destroyPreview()
  await nextTick()
  preview = new Vditor('process-preview', {
    value: md,
    mode: 'ir',
    height: '100%',
    cache: { enable: false },
    toolbar: [],
    theme: isDark.value ? 'dark' : 'classic',
    preview: { theme: { current: isDark.value ? 'dark' : 'light' } },
  })
}

function schedulePreview() {
  if (flushTimer !== null) return
  flushTimer = window.setTimeout(() => {
    flushTimer = null
    if (preview) preview.setValue(markdown.value)
  }, 120)
}

async function doTranscribe(): Promise<boolean> {
  if (!file.value) return false
  transcribing.value = true
  try {
    const { text } = await processApi.transcribeAudio(file.value)
    source.value = text
    return true
  } catch (err: any) {
    const msg = err?.response?.data?.detail || err?.message || '音频转写失败'
    ElMessage.error(msg)
    return false
  } finally {
    transcribing.value = false
  }
}

async function onTranscribeOnly() {
  const ok = await doTranscribe()
  if (!ok) return
  transcribeOnly.value = true
  started.value = true
  done.value = true
  loading.value = false
  // 仅转写模式：用 Vditor 渲染纯文本
  markdown.value = source.value
  await renderPreview(source.value)
}

async function onTranscribeAndAnalyze() {
  const ok = await doTranscribe()
  if (!ok) return
  // 转写完成后自动触发整理
  await onAnalyze()
}

async function onAnalyze() {
  if (!source.value.trim()) {
    ElMessage.warning('请先粘贴或上传文稿')
    return
  }
  loading.value = true
  started.value = true
  markdown.value = ''
  degraded.value = false
  errorMsg.value = ''
  done.value = false
  saveTitle.value = `${SUGGEST[mode.value as keyof typeof SUGGEST]} ${today()}`
  saveTags.value = []
  await renderPreview('')
  const finish = () => {
    loading.value = false
  }
  await processApi.analyzeStream(
    { text: source.value, mode: mode.value },
    {
      onMeta: (e) => {
        if (e.degraded) {
          degraded.value = true
          errorMsg.value = e.message || 'LLM 未配置，请设置环境变量 WSNOTE_LLM_API_KEY'
        }
      },
      onDelta: (text) => {
        markdown.value += text
        schedulePreview()
      },
      onError: (msg) => {
        errorMsg.value = msg
        finish()
      },
      onDone: () => {
        done.value = true
        if (preview) preview.setValue(markdown.value)
        finish()
      },
    },
  )
  finish()
}

async function onSave() {
  if (!markdown.value || !done.value) return
  const title = saveTitle.value.trim()
  if (!title) {
    ElMessage.warning('请填写笔记标题')
    return
  }
  saving.value = true
  try {
    const created = await noteApi.create({ title, content: markdown.value, tags: saveTags.value })
    ElMessage.success('已保存为笔记')
    router.push({ path: '/', query: { note: created.id } })
  } catch {
    /* 全局拦截器已提示（如标题重复 409） */
  } finally {
    saving.value = false
  }
}

async function copyText() {
  try {
    await navigator.clipboard.writeText(source.value)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败，请手动选择复制')
  }
}

function downloadTxt() {
  const blob = new Blob([source.value], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = (file.value?.name?.replace(/\.[^.]+$/, '') || '转写结果') + '.txt'
  a.click()
  URL.revokeObjectURL(url)
}

watch(isDark, (v) => {
  if (preview) preview.setTheme(v ? 'dark' : 'classic', v ? 'dark' : 'light')
})

onBeforeUnmount(() => {
  if (flushTimer !== null) window.clearTimeout(flushTimer)
  destroyPreview()
})
</script>

<style scoped>
.process-wrap {
  display: flex;
  height: 100%;
  max-width: 1280px;
  margin: 0 auto;
  width: 100%;
}
.input-pane {
  width: 400px;
  flex-shrink: 0;
  border-right: 1px solid var(--ws-border);
  background: var(--ws-surface);
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
}
.pane-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.pane-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}
.hidden-input {
  display: none;
}
.audio-upload {
  border: 2px dashed var(--ws-border);
  border-radius: var(--ws-radius);
  padding: 20px 16px;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
}
.audio-upload:hover {
  border-color: var(--ws-primary);
  background: var(--ws-primary-soft);
}
.audio-upload-icon {
  font-size: 32px;
  margin-bottom: 6px;
}
.audio-upload-text {
  font-size: 14px;
  font-weight: 600;
  color: var(--ws-text);
}
.audio-upload-hint {
  font-size: 12px;
  color: var(--ws-muted);
  margin-top: 4px;
}
.mode-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.mode-label {
  font-size: 13px;
  color: var(--ws-muted);
}
.run-btn {
  width: 100%;
}
.tip {
  font-size: 12px;
  color: var(--ws-muted);
  line-height: 1.6;
}
.tip code {
  background: var(--ws-primary-soft);
  padding: 1px 4px;
  border-radius: 4px;
  font-size: 11px;
}

.result-pane {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  padding: 20px 24px;
}
.result-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--ws-muted);
}
.empty-icon {
  font-size: 44px;
  opacity: 0.7;
}
.degraded-alert {
  margin-bottom: 12px;
}
.result-head {
  margin-bottom: 12px;
}
.save-box {
  display: flex;
  gap: 10px;
  align-items: center;
}
.save-title {
  flex: 1;
}
.save-tags {
  width: 220px;
}
.streaming-hint {
  margin-top: 8px;
  font-size: 12px;
  color: var(--ws-muted);
}
.transcribe-actions {
  margin-bottom: 12px;
  display: flex;
  gap: 10px;
}
.preview-container {
  flex: 1;
  min-height: 0;
}
.preview-box {
  height: 100%;
  border: 1px solid var(--ws-border);
  border-radius: var(--ws-radius);
  overflow: hidden;
  background: var(--ws-surface);
  box-shadow: var(--ws-shadow);
}
</style>
