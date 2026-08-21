---
title: TCP 连接
tags: [网络, TCP]
created: 2026-08-21
updated: 2026-08-21
---

# 三次握手

TCP 建立连接需要三次握手：客户端发送 SYN，服务端回复 SYN+ACK，客户端再回复 ACK，连接建立。

# 四次挥手

TCP 断开连接需要四次挥手：主动方发送 FIN，被动方回复 ACK，被动方再发送 FIN，主动方回复 ACK，连接关闭。
