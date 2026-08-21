<template>
  <el-input v-model="question" placeholder="问你的知识库" @keyup.enter="ask" />
  <el-button type="primary" @click="ask">提问</el-button>
  <el-alert v-if="ans.degraded" title="LLM 未配置，已降级为仅检索" type="warning" />
  <p>{{ ans.answer }}</p>
  <el-collapse>
    <el-collapse-item v-for="(c, i) in ans.citations" :key="i" :title="`${c.note_id} · ${c.heading_path}`">
      {{ c.text }}
    </el-collapse-item>
  </el-collapse>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { chatApi } from '../api'
const question = ref(''); const ans = ref<any>({ answer: '', citations: [], degraded: false })
async function ask() {
  ans.value = (await chatApi.ask(question.value)).data.data
}
</script>
