<script setup>
import { onMounted, ref } from "vue";
import { api } from "../api";

const health = ref(null);
const dingtalk = ref(null);
const error = ref("");

onMounted(async () => {
  health.value = await api("/api/health");
});

async function checkDingTalk() {
  error.value = "";
  try {
    dingtalk.value = await api("/api/integrations/dingtalk");
  } catch (err) {
    error.value = err.message;
  }
}
</script>

<template>
  <h1>能力与卡点</h1>
  <p class="lede">这一页只报告现在这台环境里实际接上的东西。检测失败不会被写成已上线。</p>
  <div v-if="health" class="panel stack">
    <p v-for="item in health.blockers" :key="item">{{ item }}</p>
  </div>
  <div class="row" style="margin-top: 0.8rem">
    <button @click="checkDingTalk">检测钉钉</button>
  </div>
  <p v-if="error" class="error">{{ error }}</p>
  <p v-if="dingtalk" class="panel" style="margin-top: 0.8rem">
    连接状态：未连接。SSO、JSAPI、Stream 都未开通。{{ dingtalk.reason }}
  </p>
</template>
