<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { api } from "../api";

const props = defineProps({ id: String });
const router = useRouter();
const interview = ref(null);
const error = ref("");
const pending = ref(false);

onMounted(async () => {
  interview.value = await api(`/api/interviews/${props.id}`);
});

async function start() {
  pending.value = true;
  error.value = "";
  try {
    await api(`/api/interviews/${props.id}/start`, { method: "POST" });
    router.push(`/interviews/${props.id}/room`);
  } catch (err) {
    error.value = err.message;
  } finally {
    pending.value = false;
  }
}
</script>

<template>
  <div v-if="interview">
    <h1>{{ interview.candidate_name }} 的题目</h1>
    <p class="lede">
      {{ interview.position }}。每题旁边是 BM25 命中的原句。这是字面检索分数，不是召回率。
    </p>
    <div class="list">
      <article v-for="question in interview.questions" :key="question.id" class="panel">
        <span class="tag">{{ question.intent }}</span>
        <p>{{ question.text }}</p>
        <p class="muted">
          来源 {{ question.evidence.source }} · BM25 {{ question.evidence.bm25 }} · 查询「{{ question.evidence.query }}」
        </p>
        <p class="evidence">{{ question.evidence.text }}</p>
      </article>
    </div>
    <p v-if="error" class="error">{{ error }}</p>
    <div class="row" style="margin-top: 0.8rem">
      <button :disabled="pending" @click="start">开始文字面试</button>
    </div>
  </div>
</template>
