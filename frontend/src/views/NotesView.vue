<template>
  <el-row :gutter="12">
    <el-col :span="8">
      <el-input v-model="keyword" placeholder="标题搜索" />
      <el-button type="primary" @click="createNote">新建</el-button>
      <el-menu v-for="m in filtered()" :key="m.id" @click="open(m.id)">
        <el-menu-item>{{ m.title }} <el-tag v-for="t in m.tags" :key="t">{{ t }}</el-tag></el-menu-item>
      </el-menu>
    </el-col>
    <el-col :span="16">
      <div v-if="current"><input v-model="current.title" />
        <div id="editor" style="height:60vh"></div>
        <el-button type="primary" @click="save">保存</el-button>
      </div>
    </el-col>
  </el-row>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import Vditor from 'vditor'
import 'vditor/dist/index.css'
import { noteApi } from '../api'
const list = ref<any[]>([])
const current = ref<any>(null)
const keyword = ref('')
let editor: Vditor
const filtered = () => list.value.filter(m => m.title.includes(keyword.value))

onMounted(async () => { list.value = (await noteApi.list()).data.data })
function createNote() {
  current.value = { title: '', content: '' }
  nextTick(async () => {
    if (editor) editor.destroy()
    editor = new Vditor('editor', { value: '', height: 500 })
  })
}
async function open(id: string) {
  current.value = (await noteApi.get(id)).data.data
  nextTick(() => {
    if (editor) editor.destroy()
    editor = new Vditor('editor', { value: current.value.content, height: 500 })
  })
}
async function save() {
  if (!editor) return
  const d = current.value
  if (!d.title) return
  if (d.id) await noteApi.update(d.id, { title: d.title, content: editor.getValue(), tags: d.tags ?? [] })
  else await noteApi.create({ title: d.title, content: editor.getValue(), tags: d.tags ?? [] })
  list.value = (await noteApi.list()).data.data
}
</script>
