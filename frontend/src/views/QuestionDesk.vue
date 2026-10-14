<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api, role } from "../api";
import QuestionTable from "./QuestionTable.vue";

const route = useRoute();
const router = useRouter();
const invitations = ref([]);
const person = ref(null);
const docs = ref([]);
const selectedDocs = ref([]);
const config = ref({
  basic_minutes: 10,
  skill_minutes: 30,
  basic_count: 5,
  skill_count: 10,
  easy_count: 5,
  medium_count: 5,
  hard_count: 5,
  focus: "",
});
const invitation = ref(null);
const error = ref("");
const pending = ref(false);
const steps = ref([]);
const lookupId = ref("");
const similar = ref([]);
const activeQuestion = ref("");
const credential = ref(null);

const totalCount = computed(() => config.value.basic_count + config.value.skill_count);
const totalMinutes = computed(() => config.value.basic_minutes + config.value.skill_minutes);
const canGenerate = computed(() => Boolean(person.value) && role() !== "leader");

function splitDifficulty() {
  const total = totalCount.value;
  const base = Math.floor(total / 3);
  const rest = total - base * 3;
  config.value.easy_count = base + (rest > 0 ? 1 : 0);
  config.value.medium_count = base + (rest > 1 ? 1 : 0);
  config.value.hard_count = base;
}

watch(() => [config.value.basic_count, config.value.skill_count], splitDifficulty);

async function loadInvitations() {
  invitations.value = await api("/api/recruit/invitations");
}

async function loadPerson(id) {
  person.value = await api(`/api/recruit/candidates/${id}`);
  docs.value = await api(
    `/api/recruit/documents?company=${encodeURIComponent(person.value.company)}&department=${encodeURIComponent(person.value.department)}&position=${encodeURIComponent(person.value.position)}`,
  );
  selectedDocs.value = [];
}

onMounted(async () => {
  try {
    await loadInvitations();
    if (route.query.candidate) await loadPerson(route.query.candidate);
  } catch (err) {
    error.value = err.message;
  }
});

async function findPerson() {
  error.value = "";
  try {
    await loadPerson(lookupId.value.trim());
    router.replace({ path: "/questions", query: { candidate: person.value.id } });
  } catch (err) {
    error.value = err.message;
  }
}

async function generate() {
  error.value = "";
  pending.value = true;
  steps.value = ["解析 JD 与简历"];
  try {
    const result = await api("/api/recruit/generate", {
      method: "POST",
      body: JSON.stringify({
        candidate_id: person.value.id,
        ...config.value,
        selected_document_ids: selectedDocs.value,
        invitation_id: invitation.value?.id || null,
      }),
    });
    steps.value = result.steps;
    invitation.value = result.invitation;
    await loadInvitations();
  } catch (err) {
    error.value = err.message;
  } finally {
    pending.value = false;
  }
}

function chosenIds() {
  const rows = [...invitation.value.basic_questions, ...invitation.value.skill_questions];
  return rows.filter((item) => item.selected).map((item) => item.id);
}

async function launch() {
  error.value = "";
  try {
    const result = await api(`/api/recruit/invitations/${invitation.value.id}/launch`, {
      method: "POST",
      body: JSON.stringify({ question_ids: chosenIds() }),
    });
    invitation.value = result;
    credential.value = result;
  } catch (err) {
    error.value = err.message;
  }
}

async function saveBank() {
  error.value = "";
  try {
    const result = await api(`/api/recruit/invitations/${invitation.value.id}/save-bank`, {
      method: "POST",
      body: JSON.stringify({ question_ids: chosenIds() }),
    });
    error.value = "";
    credential.value = null;
    steps.value = [`已保存 ${result.saved} 道题到题库，面试状态未改变`];
  } catch (err) {
    error.value = err.message;
  }
}

async function openSimilar(question) {
  activeQuestion.value = question.id;
  similar.value = await api(`/api/recruit/questions/${question.id}/similar`);
}

async function replace(bankId) {
  const updated = await api(`/api/recruit/questions/${activeQuestion.value}/replace`, {
    method: "POST",
    body: JSON.stringify({ bank_id: bankId }),
  });
  invitation.value = await api(`/api/recruit/invitations/${invitation.value.id}`);
  activeQuestion.value = updated.id;
  similar.value = [];
}

async function saveStem(question) {
  try {
    await api(`/api/recruit/questions/${question.id}`, {
      method: "PATCH",
      body: JSON.stringify({ stem: question.stem }),
    });
    invitation.value = await api(`/api/recruit/invitations/${invitation.value.id}`);
  } catch (err) {
    error.value = err.message;
  }
}

async function openExisting(row) {
  error.value = "";
  try {
    await loadPerson(row.candidate.id);
    invitation.value = await api(`/api/recruit/invitations/${row.id}`);
    router.replace({ path: "/questions", query: { candidate: row.candidate.id } });
  } catch (err) {
    error.value = err.message;
  }
}

async function reset(row, mode) {
  if (role() === "leader") {
    error.value = "团队负责人不能重置";
    return;
  }
  await api(`/api/recruit/invitations/${row.id}/reset?mode=${mode}`, { method: "POST" });
  if (invitation.value?.id === row.id && mode === "full") invitation.value = null;
  await loadInvitations();
}

function exportRow(row) {
  const lines = ["姓名 " + row.candidate.name, "岗位 " + row.candidate.position, ""];
  for (const item of [...row.basic_questions, ...row.skill_questions]) {
    lines.push(`[${item.kind}] ${item.category} ${item.difficulty} ${item.minutes}分钟`);
    lines.push(item.stem);
    lines.push("");
  }
  const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `${row.candidate.name}-题单.txt`;
  link.click();
  URL.revokeObjectURL(link.href);
}

function statusLabel(status) {
  if (status === "confirmed") return "待面试";
  if (status === "completed") return "已完成";
  return "已生成";
}
</script>

<template>
  <h1>面试题生成</h1>
  <p class="lede">选中人员后配置时长、题量和难度。出题只走关键词召回，再按岗位过滤，不在这里计算召回率。</p>
  <p v-if="error" class="error">{{ error }}</p>

  <section v-if="!person" class="stack">
    <div class="card row">
      <label>评估 ID<input v-model="lookupId" placeholder="例如 cand-zhou" /></label>
      <button @click="findPerson">查询</button>
      <RouterLink to="/people">去人员列表选人</RouterLink>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr><th>姓名</th><th>职位</th><th>状态</th><th>时间</th><th>基础/专业</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="row in invitations" :key="row.id">
            <td>{{ row.candidate.name }}</td>
            <td>{{ row.candidate.company }} / {{ row.candidate.department }} / {{ row.candidate.position }}</td>
            <td><span class="tag">{{ statusLabel(row.status) }}</span></td>
            <td>{{ row.created_at }}</td>
            <td>{{ row.basic_count }} / {{ row.skill_count }}</td>
            <td>
              <button class="secondary" @click="openExisting(row)">查看</button>
              <button class="secondary" @click="exportRow(row)">导出</button>
              <button v-if="row.account" class="secondary" @click="credential = row">复制</button>
              <button class="secondary" @click="reset(row, 'status')">重置状态</button>
              <button class="secondary" @click="reset(row, 'full')">完整重置</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>

  <section v-else class="stack">
    <div class="card">
      <strong>{{ person.name }}</strong>
      <span class="muted"> {{ person.company }} · {{ person.department }} · {{ person.position }} · {{ person.jd_code }}</span>
    </div>
    <div class="grid">
      <form class="card stack" @submit.prevent="generate">
        <div class="row">
          <label>基本信息时长<input v-model.number="config.basic_minutes" type="number" min="0" max="120" step="5" /></label>
          <label>专业技能时长<input v-model.number="config.skill_minutes" type="number" min="10" max="180" step="5" /></label>
          <label>基础题量<input v-model.number="config.basic_count" type="number" min="0" max="30" /></label>
          <label>专业题量<input v-model.number="config.skill_count" type="number" min="0" max="30" /></label>
        </div>
        <p class="muted">总时长 {{ totalMinutes }} 分钟，共 {{ totalCount }} 道。</p>
        <div class="bars">
          <label class="bar">初级<input v-model.number="config.easy_count" type="number" min="0" /><strong>{{ config.easy_count }}</strong></label>
          <label class="bar">中级<input v-model.number="config.medium_count" type="number" min="0" /><strong>{{ config.medium_count }}</strong></label>
          <label class="bar">高级<input v-model.number="config.hard_count" type="number" min="0" /><strong>{{ config.hard_count }}</strong></label>
        </div>
        <label>考察重点<textarea v-model="config.focus" placeholder="例如：稳定性、对账、幂等" /></label>
        <div>
          <p class="muted">岗位资料默认不勾选。勾选后才会进入本次检索。</p>
          <label v-for="doc in docs.filter((item) => item.kind === 'position_material')" :key="doc.id">
            <span><input v-model="selectedDocs" type="checkbox" :value="doc.id" /> {{ doc.filename }} · {{ doc.chunk_count }} 段 · {{ doc.source_label }}</span>
          </label>
        </div>
        <button :disabled="!canGenerate || pending || totalCount < 1">{{ pending ? "正在生成" : "生成面试题" }}</button>
        <p v-if="role() === 'leader'" class="muted">团队负责人不能生成或发起面试。</p>
      </form>
      <div class="card">
        <p class="muted">简历摘要</p>
        <p>{{ person.resume_text }}</p>
      </div>
    </div>
    <div v-if="steps.length" class="steps">
      <span v-for="step in steps" :key="step" class="step done">{{ step }}</span>
    </div>

    <template v-if="invitation">
      <QuestionTable title="基本信息面试题" :rows="invitation.basic_questions" @similar="openSimilar" @save-stem="saveStem" />
      <QuestionTable title="专业技能面试题" :rows="invitation.skill_questions" show-source @similar="openSimilar" @save-stem="saveStem" />
      <div v-if="similar.length" class="card">
        <p>相似题</p>
        <button v-for="item in similar" :key="item.id" class="secondary" @click="replace(item.id)">
          {{ item.stem }} · 相似度 {{ item.similarity }} · 使用 {{ item.use_count }} 次
        </button>
      </div>
      <div class="row">
        <button class="secondary" @click="person = null">取消</button>
        <button class="secondary" :disabled="!chosenIds().length" @click="saveBank">保存到知识库</button>
        <button :disabled="!chosenIds().length || role() === 'leader'" @click="launch">发起面试</button>
      </div>
      <div v-if="credential?.account" class="card">
        <p>请当场复制。密码只在发起时明文展示，列表里仍可再次复制。</p>
        <p>姓名 {{ credential.candidate.name }} · 岗位 {{ credential.candidate.position }}</p>
        <p>账号 {{ credential.account }} · 密码 {{ credential.password_code }}</p>
        <p>登录地址 {{ credential.login_path }}</p>
      </div>
    </template>
  </section>
</template>
