<script setup>
import { ref } from "vue";
import { api, role } from "../api";

const form = ref({
  company: "山东鲁软",
  department: "营销部",
  position: "电费核算后端开发",
  kind: "position_material",
  source_label: "本岗位",
});
const rows = ref([]);
const error = ref("");
const message = ref("");

async function load() {
  rows.value = await api(
    `/api/recruit/documents?company=${encodeURIComponent(form.value.company)}&department=${encodeURIComponent(form.value.department)}&position=${encodeURIComponent(form.value.position)}`,
  );
}

async function upload(event) {
  error.value = "";
  message.value = "";
  const file = event.target.files?.[0];
  if (!file) return;
  if (role() === "leader") {
    error.value = "团队负责人不能上传资料";
    return;
  }
  const body = new FormData();
  Object.entries(form.value).forEach(([key, value]) => body.append(key, value));
  body.append("file", file);
  try {
    const result = await api("/api/recruit/documents", { method: "POST", body });
    message.value = `已入库 ${result.chunk_count} 个切片`;
    await load();
  } catch (err) {
    error.value = err.message;
  }
}
</script>

<template>
  <h1>岗位资料与题库</h1>
  <p class="lede">长文档会按标题和段落切片。过短和重复的段落丢掉，原文、元数据和 bge-m3 向量写入 PostgreSQL。</p>
  <form class="card stack" @submit.prevent="load">
    <div class="row">
      <label>公司<input v-model="form.company" /></label>
      <label>部门<input v-model="form.department" /></label>
      <label>岗位<input v-model="form.position" /></label>
    </div>
    <div class="row">
      <label>类型
        <select v-model="form.kind">
          <option value="position_material">岗位资料</option>
          <option value="question_bank">面试题库</option>
        </select>
      </label>
      <label>来源
        <select v-model="form.source_label">
          <option>本岗位</option>
          <option>岗位模板</option>
        </select>
      </label>
      <button type="submit">查看已入库</button>
      <label>上传文件<input type="file" @change="upload" /></label>
    </div>
  </form>
  <p v-if="error" class="error">{{ error }}</p>
  <p v-if="message" class="muted">{{ message }}</p>
  <div class="table-wrap" style="margin-top: 0.8rem">
    <table>
      <thead>
        <tr><th>文件</th><th>类型</th><th>来源</th><th>切片数</th><th>时间</th></tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.id">
          <td>{{ row.filename }}</td>
          <td>{{ row.kind === "question_bank" ? "题库" : "岗位资料" }}</td>
          <td>{{ row.source_label }}</td>
          <td>{{ row.chunk_count }}</td>
          <td>{{ row.created_at }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
