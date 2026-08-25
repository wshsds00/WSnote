<template>
  <el-container class="app-root">
    <el-header class="app-header">
      <div class="brand">
        <span class="brand-logo">W</span>
        <span class="brand-name">WSnote</span>
        <span class="brand-sub">本地优先 Markdown 知识库</span>
      </div>

      <el-menu mode="horizontal" :default-active="route.path" router class="nav" :ellipsis="false">
        <el-menu-item index="/">笔记</el-menu-item>
        <el-menu-item index="/search">搜索</el-menu-item>
        <el-menu-item index="/chat">问答</el-menu-item>
        <el-menu-item index="/process">整理</el-menu-item>
      </el-menu>

      <div class="header-right">
        <el-tag v-if="status" size="small" effect="plain" class="status-pill">
          {{ status.notes }} 笔记 · {{ status.chunks }} 块
        </el-tag>
        <el-tooltip :content="isDark ? '切换到浅色' : '切换到深色'" placement="bottom">
          <el-button class="theme-btn" :icon="isDark ? Sunny : Moon" circle @click="toggle" aria-label="切换主题" />
        </el-tooltip>
      </div>
    </el-header>

    <el-main class="app-main">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Moon, Sunny } from '@element-plus/icons-vue'
import { noteApi } from './api'
import { useTheme } from './composables/useTheme'
import type { IndexStatus } from './api'

const route = useRoute()
const { isDark, toggle } = useTheme()
const status = ref<IndexStatus | null>(null)

onMounted(async () => {
  try {
    status.value = await noteApi.status()
  } catch {
    /* 索引状态加载失败不阻塞 UI */
  }
})
</script>

<style scoped>
.app-root {
  height: 100%;
}
.app-header {
  display: flex;
  align-items: center;
  gap: 16px;
  height: 56px;
  padding: 0 20px;
  background: var(--ws-surface);
  border-bottom: 1px solid var(--ws-border);
  transition: background-color 0.2s, border-color 0.2s;
}
.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
}
.brand-logo {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 7px;
  background: linear-gradient(135deg, #4f46e5, #7c3aed);
  color: #fff;
  font-weight: 700;
  font-size: 14px;
}
.brand-name {
  font-weight: 700;
  font-size: 16px;
  letter-spacing: -0.01em;
}
.brand-sub {
  color: var(--ws-muted);
  font-size: 12px;
  margin-left: 4px;
}
.nav {
  flex: 1;
  border-bottom: none;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}
.status-pill {
  color: var(--ws-muted);
}
.theme-btn {
  border-color: var(--ws-border);
}
.app-main {
  padding: 0;
  height: calc(100% - 56px);
  overflow: hidden;
}
</style>
