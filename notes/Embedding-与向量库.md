---
title: Embedding 与向量库
tags: [AI, 向量]
created: 2026-08-21
updated: 2026-08-21
---

# 向量库

向量库用于存储与检索高维向量。FAISS 是常用的本地向量库，支持索引落盘与近邻搜索，WSnote 使用 FAISS 存储笔记分块向量。

# bge 模型

bge-small-zh-v1.5 是中文 embedding 模型，输出 512 维向量，适合个人知识库检索场景。
