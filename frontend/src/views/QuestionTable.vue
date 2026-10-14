<script setup>
defineProps({
  title: String,
  rows: Array,
  showSource: Boolean,
});
const emit = defineEmits(["similar", "save-stem"]);
const open = defineModel("open", { default: "" });
</script>

<template>
  <div class="table-wrap">
    <p class="table-title">{{ title }}</p>
    <table>
      <thead>
        <tr>
          <th></th><th>类别</th><th>题干</th><th>难度</th><th>时长</th>
          <th v-if="showSource">来源</th><th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.id">
          <td><input v-model="row.selected" type="checkbox" /></td>
          <td><span class="tag">{{ row.category }}</span></td>
          <td>
            <textarea v-if="row.source === 'ai'" v-model="row.stem" />
            <span v-else>{{ row.stem }}</span>
            <p v-if="open === row.id" class="muted">
              <span v-for="point in row.rubric" :key="point.point">{{ point.point }}（{{ point.weight }}） </span>
              <span v-if="row.reference_answer">参考答案：{{ row.reference_answer }}</span>
            </p>
          </td>
          <td>{{ row.difficulty }}</td>
          <td>{{ row.minutes }} 分钟</td>
          <td v-if="showSource">{{ row.source === "bank" ? "题库" : "AI生成" }}</td>
          <td>
            <button class="secondary" type="button" @click="open = row.id">查看</button>
            <button class="secondary" type="button" @click="emit('similar', row)">替换</button>
            <button v-if="row.source === 'ai'" class="secondary" type="button" @click="emit('save-stem', row)">保存题干</button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
