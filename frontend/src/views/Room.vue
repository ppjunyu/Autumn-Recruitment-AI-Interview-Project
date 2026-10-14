<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { api } from "../api";

const props = defineProps({ id: String });
const router = useRouter();
const interview = ref(null);
const answer = ref("");
const error = ref("");
const pending = ref(false);
const recording = ref(false);
let recorder = null;
let chunks = [];

const current = computed(() => {
  if (!interview.value) return null;
  return interview.value.questions[interview.value.q_index] || null;
});

onMounted(async () => {
  interview.value = await api(`/api/interviews/${props.id}`);
  if (interview.value.status === "planned") {
    interview.value = await api(`/api/interviews/${props.id}/start`, { method: "POST" });
  }
});

async function submit() {
  error.value = "";
  pending.value = true;
  try {
    interview.value = await api(`/api/interviews/${props.id}/answers`, {
      method: "POST",
      body: JSON.stringify({ answer: answer.value }),
    });
    answer.value = "";
  } catch (err) {
    error.value = err.message;
  } finally {
    pending.value = false;
  }
}

async function checkAsr(blob) {
  const body = new FormData();
  body.append("file", blob, "clip.webm");
  try {
    await api("/api/asr", { method: "POST", body });
  } catch (err) {
    error.value = err.message;
  }
}

async function toggleRecord() {
  error.value = "";
  if (!recording.value) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      chunks = [];
      recorder = new MediaRecorder(stream);
      recorder.ondataavailable = (event) => chunks.push(event.data);
      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        await checkAsr(new Blob(chunks, { type: "audio/webm" }));
      };
      recorder.start();
      recording.value = true;
    } catch {
      error.value = "浏览器没有拿到麦克风。语音识别服务也没有配置，请用文字作答。";
    }
    return;
  }
  recorder.stop();
  recording.value = false;
}

async function probeAsr() {
  await checkAsr(new Blob(["probe"], { type: "audio/webm" }));
}

function openReport() {
  router.push(`/interviews/${props.id}/report`);
}
</script>

<template>
  <div v-if="interview">
    <h1>{{ interview.candidate_name }} · 初试</h1>
    <p class="lede">
      {{ interview.position }}。追问会引用你刚说的原话。评分是规则分：完整度、证据贴合、相关性，满分 5。
    </p>
    <div class="room">
      <section class="panel stack">
        <div class="transcript">
          <article
            v-for="(turn, index) in interview.turns"
            :key="index"
            class="bubble"
            :class="turn.role"
          >
            <strong>{{ turn.role === "interviewer" ? "面试官" : "候选人" }}</strong>
            <p>{{ turn.content }}</p>
            <p v-if="turn.reason" class="meta">
              判定：{{ turn.reason }}
              <span v-if="turn.trace"> · 节点 {{ turn.trace.join(" → ") }}</span>
              <span v-if="turn.score"> · 规则分 {{ turn.score.total }}/5</span>
            </p>
            <p v-if="turn.llm_note" class="meta">{{ turn.llm_note }}</p>
          </article>
        </div>
        <form v-if="interview.status === 'in_progress'" class="stack" @submit.prevent="submit">
          <textarea v-model="answer" placeholder="用文字回答。短回答或偏离材料时，会先追问一次。" />
          <p v-if="error" class="error">{{ error }}</p>
          <div class="row">
            <button type="submit" :disabled="pending || !answer.trim()">提交回答</button>
            <button type="button" class="secondary" @click="toggleRecord">
              {{ recording ? "停止并检测识别" : "录音" }}
            </button>
            <button type="button" class="secondary" @click="probeAsr">检测语音识别</button>
          </div>
        </form>
        <div v-else class="stack">
          <p>题目已经问完。</p>
          <button @click="openReport">生成初试记录</button>
        </div>
      </section>
      <aside class="panel stack">
        <h2 style="margin: 0; font-size: 1rem">本题材料</h2>
        <template v-if="current">
          <span class="tag">{{ current.intent }} · 第 {{ interview.q_index + 1 }} / {{ interview.questions.length }} 题</span>
          <p class="muted">已追问 {{ current.followups_used }} 次，每题最多 1 次。</p>
          <p class="evidence">{{ current.evidence.text }}</p>
        </template>
        <p v-else class="muted">全部题目已评分。</p>
      </aside>
    </div>
  </div>
</template>
