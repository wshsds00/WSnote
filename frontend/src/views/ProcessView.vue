<template>
  <div class="process-wrap">
    <!-- 左栏：输入面板 -->
    <aside class="input-pane">
      <div class="pane-head">
        <h2 class="pane-title">原始文稿</h2>
        <el-button text type="primary" :icon="Upload" @click="fileInput?.click()">
          {{ file ? file.name : '选择文件' }}
        </el-button>
      </div>
      <input
        ref="fileInput"
        type="file"
        accept=".txt,.md"
        class="hidden-input"
        @change="onFile"
      />

      <el-input
        v-model="source"
        type="textarea"
        :rows="16"
        resize="none"
        placeholder="粘贴面试录音文字稿、长文档或会议记录…（支持 .txt / .md 文件）"
      />

      <div class="mode-row">
        <span class="mode-label">整理方式</span>
        <el-radio-group v-model="mode" size="small">
          <el-radio-button value="interview">面试整理</el-radio-button>
          <el-radio-button value="general">通用整理</el-radio-button>
          <el-radio-button value="meeting">会议纪要</el-radio-button>
        </el-radio-group>
      </div>

      <el-button
        type="primary"
        :loading="loading"
        :icon="MagicStick"
        class="run-btn"
        @click="onAnalyze"
      >
        {{ loading ? '整理中…' : '开始整理' }}
      </el-button>

      <div class="tip">
        <p>提示：AI 整理需要已配置 LLM（环境变量 <code>WSNOTE_LLM_API_KEY</code>）。</p>
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

        <div class="result-head">
          <div class="save-box">
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
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import Vditor from 'vditor'
import 'vditor/dist/index.css'
import { Check, MagicStick, Upload } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { noteApi, processApi } from '../api'
import { useTheme } from '../composables/useTheme'
import { readFileText } from '../utils/file'

const router = useRouter()
const { isDark } = useTheme()

const source = ref('')
const mode = ref<'interview' | 'general' | 'meeting'>('interview')
const file = ref<File | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const loading = ref(false)
const saving = ref(false)
const started = ref(false)
const markdown = ref('')
const degraded = ref(false)
const errorMsg = ref('')
const done = ref(false)
const saveTitle = ref('')
const saveTags = ref<string[]>([])
let preview: Vditor | null = null
let flushTimer: number | null = null

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
  const f = (e.target as HTMLInputElement).files?.[0]
  if (!f) return
  file.value = f
  try {
    source.value = await readFileText(f)
  } catch {
    ElMessage.error('读取文件失败')
  }
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
