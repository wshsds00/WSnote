---
title: Spring Boot
tags: [Java, Spring]
created: 2026-08-21
updated: 2026-08-21
---

# 自动装配

Spring Boot 自动装配通过 @EnableAutoConfiguration 与 spring.factories 配置文件，在启动时按条件注解装配 Bean，减少手动配置。

# 启动流程

Spring Boot 启动流程包括创建 SpringApplication、加载自动装配配置、刷新应用上下文、启动内嵌 Tomcat 等步骤。
