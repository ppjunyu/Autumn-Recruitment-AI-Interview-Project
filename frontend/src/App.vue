<script setup>
import { onMounted, ref } from "vue";
import { api } from "./api";

const health = ref(null);

onMounted(async () => {
  health.value = await api("/api/health");
});
</script>

<template>
  <div class="shell">
    <aside>
      <p class="brand">招聘面试智能体</p>
      <p class="brand-note">初试切片 · 恒道实习复刻</p>
      <nav>
        <RouterLink to="/">面试场次</RouterLink>
        <RouterLink to="/new">新建初试</RouterLink>
        <RouterLink to="/status">能力与卡点</RouterLink>
      </nav>
    </aside>
    <div class="main">
      <header v-if="health" class="capability">
        <span>检索 {{ health.retrieval }}</span>
        <span>编排 {{ health.orchestration }}</span>
        <span>{{ health.llm_configured ? "大模型已配置" : "大模型未配置" }}</span>
        <span>语音未接入</span>
        <span>钉钉未连接</span>
        <RouterLink to="/status">查看卡点</RouterLink>
      </header>
      <RouterView />
    </div>
  </div>
</template>
