<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { api } from "../api";

const router = useRouter();
const form = ref({
  candidate_name: "",
  position: "",
  jd_text: "",
  resume_text: "",
});
const error = ref("");
const pending = ref(false);

onMounted(async () => {
  const sample = await api("/api/sample");
  form.value = { ...sample };
});

async function fillSample() {
  form.value = await api("/api/sample");
}

async function submit() {
  error.value = "";
  pending.value = true;
  try {
    const created = await api("/api/interviews", {
      method: "POST",
      body: JSON.stringify(form.value),
    });
    router.push(`/interviews/${created.id}/questions`);
  } catch (err) {
    error.value = err.message;
  } finally {
    pending.value = false;
  }
}
</script>

<template>
  <h1>新建初试</h1>
  <p class="lede">示例候选人周宁是虚构的，用来检查出题是否引用了材料原句。不要填入真人简历。</p>
  <form class="panel stack" @submit.prevent="submit">
    <label>候选人<input v-model="form.candidate_name" type="text" required /></label>
    <label>岗位<input v-model="form.position" type="text" required /></label>
    <label>岗位说明<textarea v-model="form.jd_text" required /></label>
    <label>简历<textarea v-model="form.resume_text" required /></label>
    <p v-if="error" class="error">{{ error }}</p>
    <div class="row">
      <button type="submit" :disabled="pending">生成题目</button>
      <button type="button" class="secondary" @click="fillSample">重新填入示例</button>
    </div>
  </form>
</template>
