<script setup>
import { ref } from "vue";
import { role, setRole } from "./api";

const current = ref(role());

function change(event) {
  setRole(event.target.value);
  current.value = event.target.value;
}
</script>

<template>
  <div class="shell">
    <aside class="side">
      <p class="brand">招聘面试智能体</p>
      <p class="brand-note">语音面试 · 面试题生成</p>
      <nav>
        <RouterLink to="/people">人员列表</RouterLink>
        <RouterLink to="/questions">面试题生成</RouterLink>
        <RouterLink to="/materials">岗位资料与题库</RouterLink>
      </nav>
      <label class="role">
        当前身份
        <select :value="current" @change="change">
          <option value="hr">HR</option>
          <option value="leader">团队负责人</option>
        </select>
      </label>
    </aside>
    <main class="main">
      <RouterView />
    </main>
  </div>
</template>
