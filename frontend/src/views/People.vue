<script setup>
import { onMounted, ref } from "vue";
import { api } from "../api";

const rows = ref([]);
const error = ref("");

onMounted(async () => {
  try {
    rows.value = await api("/api/recruit/candidates");
  } catch (err) {
    error.value = err.message;
  }
});
</script>

<template>
  <h1>人员列表</h1>
  <p class="lede">这里只放已经通过简历评估的人。点邀请面试后才会进入出题，避免对空记录组卷。</p>
  <p v-if="error" class="error">{{ error }}</p>
  <div class="table-wrap">
    <table>
      <thead>
        <tr><th>姓名</th><th>公司</th><th>部门</th><th>岗位</th><th>JD 编码</th><th></th></tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.id">
          <td>{{ row.name }}</td>
          <td>{{ row.company }}</td>
          <td>{{ row.department }}</td>
          <td>{{ row.position }}</td>
          <td>{{ row.jd_code }}</td>
          <td><RouterLink :to="`/questions?candidate=${row.id}`">邀请面试</RouterLink></td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
