import { createRouter, createWebHistory } from "vue-router";
import People from "./views/People.vue";
import QuestionDesk from "./views/QuestionDesk.vue";
import Materials from "./views/Materials.vue";
import Exam from "./views/Exam.vue";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/people" },
    { path: "/people", component: People },
    { path: "/questions", component: QuestionDesk },
    { path: "/materials", component: Materials },
    { path: "/exam/:id", component: Exam, props: true },
  ],
});
