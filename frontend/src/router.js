import { createRouter, createWebHistory } from "vue-router";
import Home from "./views/Home.vue";
import Create from "./views/Create.vue";
import Questions from "./views/Questions.vue";
import Room from "./views/Room.vue";
import Report from "./views/Report.vue";
import Status from "./views/Status.vue";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", component: Home },
    { path: "/new", component: Create },
    { path: "/interviews/:id/questions", component: Questions, props: true },
    { path: "/interviews/:id/room", component: Room, props: true },
    { path: "/interviews/:id/report", component: Report, props: true },
    { path: "/status", component: Status },
  ],
});
