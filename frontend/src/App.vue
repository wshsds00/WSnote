<template>
  <el-container>
    <el-header>
      <div class="brand">WSnote</div>
      <el-menu mode="horizontal" :default-active="$route.path" router>
        <el-menu-item index="/">笔记</el-menu-item>
        <el-menu-item index="/search">搜索</el-menu-item>
        <el-menu-item index="/chat">问答</el-menu-item>
      </el-menu>
    </el-header>
    <el-main><router-view /></el-main>
  </el-container>
</template>
