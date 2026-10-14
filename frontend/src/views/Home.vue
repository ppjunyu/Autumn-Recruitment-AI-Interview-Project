<script setup>
import { onMounted, ref } from "vue";
import { api } from "../api";
import { STATUS } from "../labels";

const rows = ref([]);
const error = ref("");

onMounted(async () => {
  try {
    rows.value = await api("/api/interviews");
  } catch (err) {
    error.value = err.message;
  }
});

function href(row) {
  if (row.status === "reported") return `/interviews/${row.id}/report`;
  if (row.status === "planned") return `/interviews/${row.id}/questions`;
  return `/interviews/${row.id}/room`;
}
</script>

<template>
  <h1>面试场次</h1>
  <p class="lede">一场初试从岗位说明和简历出题，文字作答后生成三阶段规则记录。</p>
  <p v-if="error" class="error">{{ error }}</p>
  <div v-if="rows.length" class="list">
    <RouterLink v-for="row in rows" :key="row.id" class="card" :to="href(row)">
      <strong>{{ row.candidate_name }} · {{ row.position }}</strong>
      <span class="muted">{{ STATUS[row.status] }} · {{ row.created_at }}</span>
    </RouterLink>
  </div>
  <div v-else class="panel">
    <p>还没有场次。</p>
    <RouterLink to="/new">新建一场初试</RouterLink>
  </div>
</template>
