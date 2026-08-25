<template>
  <div class="search-wrap">
    <div class="search-head">
      <h1 class="page-title">语义搜索</h1>
      <p class="page-sub">关键词 + 向量语义混合检索，命中笔记片段</p>

      <div class="search-bar">
        <el-input
          v-model="q"
          placeholder="输入检索词，回车搜索…"
          size="large"
          :prefix-icon="Search"
          clearable
          @keyup.enter="run"
          @clear="hits = []; searched = false"
        />
        <el-button type="primary" size="large" :loading="loading" @click="run">搜索</el-button>
      </div>

      <div class="search-opts">
        <span class="k-label">返回条数</span>
        <el-radio-group v-model="k" size="small" @change="onKChange">
          <el-radio-button :value="5">5</el-radio-button>
          <el-radio-button :value="10">10</el-radio-button>
          <el-radio-button :value="20">20</el-radio-button>
        </el-radio-group>
      </div>
    </div>

    <!-- 空态 -->
    <div v-if="!searched && !loading" class="empty-state">
      <div class="empty-icon">🔍</div>
      <p>输入你想找的内容，比如「分布式一致性」</p>
    </div>

    <!-- 无结果 -->
    <div v-else-if="searched && hits.length === 0" class="empty-state">
      <div class="empty-icon">🫥</div>
      <p>没有命中「{{ q }}」，换个说法试试</p>
    </div>

    <!-- 结果列表 -->
    <div v-else class="results">
      <div v-for="h in hits" :key="h.chunk_id" class="hit-card ws-clickable" @click="jump(h)">
        <div class="hit-top">
          <div class="hit-title">
            <span class="dot"></span>
            <span>{{ h.note_id }}</span>
          </div>
          <el-tag size="small" effect="plain" class="score-tag">
            {{ (h.score * 100).toFixed(1) }}%
          </el-tag>
        </div>

        <div class="hit-breadcrumb">
          <template v-if="h.heading_path">
            <span v-for="(part, i) in h.heading_path.split(' / ')" :key="i">
              <template v-if="i > 0"> / </template>{{ part }}
            </span>
          </template>
          <span v-else class="muted">正文</span>
        </div>

        <p class="hit-preview" v-html="highlight(h.text)"></p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Search } from '@element-plus/icons-vue'
import { searchApi } from '../api'
import type { RetrievalHit } from '../api'

const router = useRouter()
const q = ref('')
const k = ref(5)
const loading = ref(false)
const searched = ref(false)
const hits = ref<RetrievalHit[]>([])

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] as string,
  )
}

/** 关键词高亮：把命中片段中的 q 包进 <mark class="hl">，并做 HTML 转义防注入 */
function highlight(text: string): string {
  const kw = q.value.trim()
  if (!kw) return escapeHtml(text)
  const esc = escapeHtml(text)
  const terms = kw.split(/\s+/).filter(Boolean)
  const re = new RegExp(`(${terms.map((t) => escapeRegExp(t)).join('|')})`, 'gi')
  return esc.replace(re, '<mark class="hl">$1</mark>')
}

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

async function run() {
  const kw = q.value.trim()
  if (!kw) return
  loading.value = true
  try {
    const res = await searchApi.query(kw, k.value)
    hits.value = res.hits ?? []
    searched.value = true
  } finally {
    loading.value = false
  }
}

function onKChange() {
  if (searched.value) run()
}

function jump(h: RetrievalHit) {
  router.push({ path: '/', query: { note: h.note_id } })
}
</script>

<style scoped>
.search-wrap {
  max-width: 860px;
  margin: 0 auto;
  padding: 40px 24px 60px;
  height: 100%;
  overflow-y: auto;
}
.page-title {
  margin: 0;
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.02em;
}
.page-sub {
  margin: 6px 0 24px;
  color: var(--ws-muted);
  font-size: 14px;
}
.search-bar {
  display: flex;
  gap: 10px;
}
.search-opts {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
}
.k-label {
  font-size: 13px;
  color: var(--ws-muted);
}

.empty-state {
  margin-top: 60px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  color: var(--ws-muted);
}
.empty-icon {
  font-size: 44px;
  opacity: 0.7;
}

.results {
  margin-top: 24px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.hit-card {
  background: var(--ws-surface);
  border: 1px solid var(--ws-border);
  border-radius: var(--ws-radius);
  padding: 16px 18px;
  box-shadow: var(--ws-shadow);
  transition: border-color 0.15s, transform 0.15s, box-shadow 0.15s;
}
.hit-card:hover {
  border-color: var(--ws-primary);
  box-shadow: 0 2px 8px rgba(79, 70, 229, 0.12);
  transform: translateY(-1px);
}
.hit-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.hit-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 15px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--ws-primary);
  flex-shrink: 0;
}
.score-tag {
  flex-shrink: 0;
  color: var(--ws-muted);
}
.hit-breadcrumb {
  margin-top: 8px;
  font-size: 12px;
  color: var(--ws-primary);
  opacity: 0.85;
}
.hit-breadcrumb .muted {
  color: var(--ws-muted);
}
.hit-preview {
  margin: 10px 0 0;
  font-size: 13px;
  line-height: 1.65;
  color: var(--ws-foreground);
  opacity: 0.9;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
