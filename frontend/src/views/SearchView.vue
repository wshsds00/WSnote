<template>
  <el-input v-model="q" placeholder="输入检索词" @keyup.enter="run" />
  <el-button @click="run">搜索</el-button>
  <el-card v-for="h in hits" :key="h.chunk_id" style="margin-top:8px">
    <b>{{ h.note_id }} · {{ h.heading_path }}</b>
    <p>{{ h.text }}</p>
    <span>score: {{ h.score.toFixed(3) }}</span>
  </el-card>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { searchApi } from '../api'
const q = ref(''); const hits = ref<any[]>([])
async function run() {
  hits.value = (await searchApi.query(q.value)).data.data.hits
}
</script>
