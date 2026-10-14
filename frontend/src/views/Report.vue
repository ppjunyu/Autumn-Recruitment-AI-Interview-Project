<script setup>
import { onMounted, ref } from "vue";
import { api } from "../api";

const props = defineProps({ id: String });
const interview = ref(null);
const error = ref("");

onMounted(async () => {
  try {
    const current = await api(`/api/interviews/${props.id}`);
    interview.value = current.report
      ? current
      : await api(`/api/interviews/${props.id}/report`, { method: "POST" });
  } catch (err) {
    error.value = err.message;
  }
});
</script>

<template>
  <p v-if="error" class="error">{{ error }}</p>
  <div v-if="interview?.report" class="stack">
    <h1>{{ interview.report.candidate_name }} 的初试记录</h1>
    <p class="lede">
      {{ interview.report.position }}。均分 {{ interview.report.mean_score }} / 5。
      三个阶段是规则汇总，没有调用多章大模型提示词。
    </p>
    <section class="score-grid">
      <div v-for="(value, name) in interview.report.stages[1].dimensions" :key="name">
        <span class="muted">{{ name }}</span>
        <strong>{{ value }}</strong>
      </div>
    </section>
    <section class="panel">
      <span class="tag">阶段三</span>
      <h2 style="margin-bottom: 0.3rem">{{ interview.report.stages[2].advice }}</h2>
      <p>{{ interview.report.stages[2].reason }}</p>
    </section>
    <section v-for="chapter in interview.report.chapters" :key="chapter.title" class="panel">
      <h2 style="margin-top: 0; font-size: 1.05rem">{{ chapter.title }}</h2>
      <p>{{ chapter.body }}</p>
    </section>
    <section class="panel">
      <h2 style="margin-top: 0; font-size: 1.05rem">逐题</h2>
      <div v-for="item in interview.report.stages[0].items" :key="item.intent" style="margin-bottom: 0.8rem">
        <strong>{{ item.intent }} · {{ item.total }}/5</strong>
        <p>{{ item.question }}</p>
      </div>
    </section>
  </div>
</template>
