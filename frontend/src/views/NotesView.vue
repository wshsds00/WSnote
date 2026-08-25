<template>
  <div class="notes-wrap">
    <!-- 左栏：笔记列表 -->
    <aside class="sidebar" v-loading="loadingList">
      <div class="sidebar-top">
        <el-input v-model="keyword" placeholder="搜索标题" clearable :prefix-icon="Search" size="large" />
        <div class="sidebar-actions">
          <el-button type="primary" :icon="Plus" @click="createNote">新建</el-button>
          <el-button :icon="Upload" @click="importVisible = true">导入</el-button>
        </div>
      </div>

      <div class="list-meta">
        <span>{{ filtered.length }} 篇笔记</span>
      </div>

      <div class="note-list">
        <transition-group name="ws-fade">
          <div
            v-for="m in filtered"
            :key="m.id"
            class="note-item"
            :class="{ active: currentId === m.id }"
            @click="open(m.id)"
          >
            <div class="note-item-main">
              <div class="note-title">{{ m.title }}</div>
              <div class="note-tags">
                <el-tag v-for="t in m.tags" :key="t" size="small" effect="plain">{{ t }}</el-tag>
              </div>
              <div class="note-updated">{{ m.updated }}</div>
            </div>
            <el-button
              class="del-btn"
              :icon="Delete"
              circle
              size="small"
              text
              aria-label="删除笔记"
              @click.stop="del(m)"
            />
          </div>
        </transition-group>

        <div v-if="!loadingList && filtered.length === 0" class="empty-side">
          <p>{{ list.length === 0 ? '还没有笔记，点「新建」开始' : '没有匹配的笔记' }}</p>
        </div>
      </div>
    </aside>

    <!-- 右栏：编辑器 -->
    <section class="editor-pane">
      <!-- 空状态占位 -->
      <div v-if="!current" class="editor-empty">
        <div class="editor-empty-icon">📝</div>
        <p>选择左侧笔记，或点「新建」开始记录</p>
      </div>

      <!-- 编辑器 -->
      <template v-else>
        <div class="editor-head">
          <input
            v-model="current.title"
            class="title-input"
            placeholder="笔记标题"
            :class="{ 'is-empty': !current.title }"
            @input="markDirty"
          />
          <div class="editor-actions">
            <span v-if="dirty" class="dirty-hint">未保存</span>
            <el-button :loading="saving" type="primary" @click="save">保存</el-button>
            <el-button v-if="currentId" :icon="Delete" @click="delCurrent">删除</el-button>
          </div>
        </div>

        <div class="tag-row">
          <el-tag
            v-for="(t, i) in current.tags"
            :key="t + i"
            closable
            @close="removeTag(i)"
            @click.stop
          >
            {{ t }}
          </el-tag>
          <el-input
            v-model="tagInput"
            class="tag-input"
            size="small"
            placeholder="+ 标签"
            @keyup.enter="addTag"
            @blur="commitTag"
          />
        </div>

        <div class="editor-container">
          <div id="editor" class="vditor-box"></div>
        </div>
      </template>
    </section>

    <!-- 导入文稿弹窗 -->
    <el-dialog v-model="importVisible" title="导入文稿" width="560px" append-to-body>
      <div class="import-body">
        <div class="import-file-row">
          <el-button :icon="Upload" @click="importFileInput?.click()">
            {{ importFile ? importFile.name : '选择 .txt / .md 文件' }}
          </el-button>
          <el-button v-if="importFile" text type="danger" @click="clearImportFile">清除</el-button>
        </div>
        <input ref="importFileInput" type="file" accept=".txt,.md" class="hidden-input" @change="onImportFile" />

        <el-input
          v-model="importTextArea"
          type="textarea"
          :rows="8"
          resize="none"
          placeholder="或直接粘贴文稿内容…"
        />

        <div class="import-opts">
          <span class="mode-label">拆分方式</span>
          <el-radio-group v-model="importMode">
            <el-radio-button value="single">整篇一篇</el-radio-button>
            <el-radio-button value="split_h1">按一级标题拆分</el-radio-button>
          </el-radio-group>
        </div>

        <el-input
          v-if="importMode === 'single'"
          v-model="importTitle"
          placeholder="笔记标题（可选，默认取首行）"
        />
        <el-select
          v-model="importTags"
          multiple
          filterable
          allow-create
          default-first-option
          placeholder="标签（可选）"
        />
      </div>
      <template #footer>
        <el-button @click="importVisible = false">取消</el-button>
        <el-button type="primary" :loading="importing" @click="onImport">导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Vditor from 'vditor'
import 'vditor/dist/index.css'
import { Delete, Plus, Search, Upload } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { noteApi, processApi } from '../api'
import { useTheme } from '../composables/useTheme'
import { readFileText } from '../utils/file'
import type { Note, NoteMeta } from '../api'

const route = useRoute()
const router = useRouter()
const { isDark } = useTheme()

const list = ref<NoteMeta[]>([])
const loadingList = ref(false)
const keyword = ref('')
const current = ref<(Note & { tags: string[] }) | null>(null)
const currentId = ref<string | null>(null)
const dirty = ref(false)
const saving = ref(false)
const tagInput = ref('')
let editor: Vditor | null = null

// 导入文稿
const importVisible = ref(false)
const importTextArea = ref('')
const importMode = ref<'single' | 'split_h1'>('single')
const importTitle = ref('')
const importTags = ref<string[]>([])
const importFile = ref<File | null>(null)
const importFileInput = ref<HTMLInputElement | null>(null)
const importing = ref(false)

const filtered = computed(() => list.value.filter((m) => m.title.includes(keyword.value.trim())))

function markDirty() {
  dirty.value = true
}

async function loadList() {
  loadingList.value = true
  try {
    list.value = await noteApi.list()
  } finally {
    loadingList.value = false
  }
}

function destroyEditor() {
  if (editor) {
    editor.destroy()
    editor = null
  }
}

function initEditor(content: string) {
  destroyEditor()
  const theme = isDark.value ? 'dark' : 'classic'
  editor = new Vditor('editor', {
    value: content,
    height: '100%',
    mode: 'ir',
    theme,
    preview: { theme: { current: isDark.value ? 'dark' : 'light' } },
    toolbarConfig: { pin: true },
    input: markDirty,
  })
}

async function confirmDiscard(): Promise<boolean> {
  if (!dirty.value) return true
  try {
    await ElMessageBox.confirm('当前修改尚未保存，确定放弃吗？', '未保存的修改', {
      confirmButtonText: '放弃修改',
      cancelButtonText: '继续编辑',
      type: 'warning',
    })
    return true
  } catch {
    return false
  }
}

async function open(id: string) {
  if (id === currentId.value && current.value) return
  if (!(await confirmDiscard())) return
  try {
    const note = await noteApi.get(id)
    current.value = { ...note, tags: [...(note.tags || [])] }
    currentId.value = id
    dirty.value = false
    await nextTick()
    initEditor(note.content)
    router.replace({ query: { ...route.query, note: id } })
  } catch {
    /* 404 等已在全局拦截器提示 */
  }
}

async function createNote() {
  if (!(await confirmDiscard())) return
  current.value = { id: '', title: '', content: '', tags: [], created: '', updated: '' }
  currentId.value = null
  dirty.value = false
  tagInput.value = ''
  await nextTick()
  initEditor('')
  router.replace({ query: {} })
}

function addTag() {
  const t = tagInput.value.trim()
  if (!t || !current.value) return
  if (current.value.tags.includes(t)) {
    tagInput.value = ''
    return
  }
  current.value.tags.push(t)
  tagInput.value = ''
  markDirty()
}

function commitTag() {
  if (tagInput.value.trim()) addTag()
}

function removeTag(i: number) {
  current.value?.tags.splice(i, 1)
  markDirty()
}

async function save() {
  if (!current.value || !editor) return
  const d = current.value
  const title = d.title.trim()
  if (!title) {
    ElMessage.warning('请先填写笔记标题')
    return
  }
  saving.value = true
  try {
    const payload = { title, content: editor.getValue(), tags: d.tags }
    if (currentId.value) {
      await noteApi.update(currentId.value, payload)
    } else {
      const created = await noteApi.create(payload)
      currentId.value = created.id
    }
    dirty.value = false
    ElMessage.success('已保存')
    await loadList()
    if (currentId.value) router.replace({ query: { ...route.query, note: currentId.value } })
  } finally {
    saving.value = false
  }
}

async function doDelete(id: string) {
  try {
    await ElMessageBox.confirm('删除后不可恢复，确定删除这篇笔记吗？', '删除笔记', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
      confirmButtonClass: 'el-button--danger',
    })
  } catch {
    return
  }
  try {
    await noteApi.del(id)
    ElMessage.success('已删除')
    if (currentId.value === id) {
      current.value = null
      currentId.value = null
      destroyEditor()
      router.replace({ query: {} })
    }
    await loadList()
  } catch {
    /* 全局拦截器已提示 */
  }
}

function del(m: NoteMeta) {
  doDelete(m.id)
}

async function delCurrent() {
  if (currentId.value) await doDelete(currentId.value)
}

// 路由跳转支持：搜索/问答点引用 → ?note=<id> 打开
watch(
  () => route.query.note,
  (id) => {
    if (id && typeof id === 'string') open(id)
  },
  { immediate: true },
)

// 深色模式跟随 vditor
watch(isDark, (v) => {
  if (editor) editor.setTheme(v ? 'dark' : 'classic', v ? 'dark' : 'light')
})

async function onImportFile(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0]
  if (!f) return
  importFile.value = f
  try {
    importTextArea.value = await readFileText(f)
  } catch {
    ElMessage.error('读取文件失败')
  }
}

function clearImportFile() {
  importFile.value = null
  if (importFileInput.value) importFileInput.value.value = ''
}

async function onImport() {
  const text = importTextArea.value.trim()
  if (!text) {
    ElMessage.warning('请粘贴文稿或选择文件')
    return
  }
  importing.value = true
  try {
    const res = await processApi.importText({
      text,
      mode: importMode.value,
      title: importTitle.value,
      tags: importTags.value,
    })
    const n = res.created.length
    const s = res.skipped.length
    ElMessage.success(s > 0 ? `导入 ${n} 篇，跳过 ${s} 篇（标题重复）` : `导入 ${n} 篇`)
    importVisible.value = false
    importTextArea.value = ''
    importTitle.value = ''
    importTags.value = []
    importFile.value = null
    await loadList()
    if (res.created.length) open(res.created[0].id)
  } catch {
    /* 全局拦截器已提示 */
  } finally {
    importing.value = false
  }
}

onMounted(loadList)
</script>

<style scoped>
.notes-wrap {
  display: flex;
  height: 100%;
}
.sidebar {
  width: 320px;
  flex-shrink: 0;
  border-right: 1px solid var(--ws-border);
  background: var(--ws-surface);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: background-color 0.2s, border-color 0.2s;
}
.sidebar-top {
  padding: 14px 14px 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.sidebar-actions {
  display: flex;
  gap: 8px;
}
.sidebar-actions :deep(.el-button) {
  flex: 1;
}
.list-meta {
  padding: 4px 16px 8px;
  font-size: 12px;
  color: var(--ws-muted);
}
.note-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px 12px;
}
.note-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 10px 10px 10px 12px;
  border-radius: var(--ws-radius);
  cursor: pointer;
  transition: background-color 0.15s, color 0.15s;
}
.note-item:hover {
  background: var(--ws-primary-soft);
}
.note-item.active {
  background: var(--ws-primary-soft);
  box-shadow: inset 2px 0 0 var(--ws-primary);
}
.note-item-main {
  flex: 1;
  min-width: 0;
}
.note-title {
  font-weight: 500;
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.note-tags {
  margin-top: 3px;
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}
.note-updated {
  margin-top: 3px;
  font-size: 11px;
  color: var(--ws-muted);
}
.del-btn {
  opacity: 0;
  transition: opacity 0.15s;
  color: var(--ws-destructive);
}
.note-item:hover .del-btn {
  opacity: 1;
}
.empty-side {
  padding: 24px 16px;
  text-align: center;
  color: var(--ws-muted);
  font-size: 13px;
}

.editor-pane {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: var(--ws-bg);
}
.editor-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--ws-muted);
  gap: 8px;
}
.editor-empty-icon {
  font-size: 40px;
  opacity: 0.6;
}
.editor-head {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px 8px;
}
.title-input {
  flex: 1;
  font-size: 22px;
  font-weight: 600;
  border: none;
  outline: none;
  background: transparent;
  color: var(--ws-foreground);
  padding: 4px 0;
}
.title-input.is-empty {
  color: var(--ws-muted);
}
.editor-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.dirty-hint {
  font-size: 12px;
  color: #d97706;
}
.tag-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 20px 12px;
  flex-wrap: wrap;
}
.tag-input {
  width: 110px;
}
.tag-input :deep(.el-input__wrapper) {
  box-shadow: none;
  border-bottom: 1px solid var(--ws-border);
  border-radius: 0;
  background: transparent;
}
.editor-container {
  flex: 1;
  min-height: 0;
  padding: 0 20px 16px;
}
.vditor-box {
  height: 100%;
  border-radius: var(--ws-radius);
  overflow: hidden;
  box-shadow: var(--ws-shadow);
}

/* 导入弹窗 */
.import-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.hidden-input {
  display: none;
}
.import-opts {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.mode-label {
  font-size: 13px;
  color: var(--ws-muted);
}
</style>
