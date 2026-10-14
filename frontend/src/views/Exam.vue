<script setup>
import { ref } from "vue";
import { api } from "../api";

const props = defineProps({ id: String });
const account = ref("");
const password = ref("");
const invitation = ref(null);
const error = ref("");

async function enter() {
  error.value = "";
  try {
    invitation.value = await api(`/api/recruit/invitations/${props.id}/enter`, {
      method: "POST",
      body: JSON.stringify({ account: account.value, password_code: password.value }),
    });
  } catch (err) {
    error.value = err.message;
  }
}
</script>

<template>
  <h1>初试题单</h1>
  <p class="lede">这里只核对账号并展示已勾选的题目。语音房间不在这一期。</p>
  <form v-if="!invitation" class="card stack" @submit.prevent="enter">
    <label>账号<input v-model="account" /></label>
    <label>密码<input v-model="password" /></label>
    <button>进入题单</button>
    <p v-if="error" class="error">{{ error }}</p>
  </form>
  <div v-else class="stack">
    <div class="card">{{ invitation.candidate.name }} · {{ invitation.candidate.position }}</div>
    <article v-for="row in [...invitation.basic_questions, ...invitation.skill_questions].filter((item) => item.selected)" :key="row.id" class="card">
      <span class="tag">{{ row.category }}</span>
      <p>{{ row.stem }}</p>
    </article>
  </div>
</template>
