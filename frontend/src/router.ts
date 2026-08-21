import { createRouter, createWebHistory } from 'vue-router'
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: () => import('./views/NotesView.vue') },
    { path: '/search', component: () => import('./views/SearchView.vue') },
    { path: '/chat', component: () => import('./views/ChatView.vue') },
  ],
})
export { router }
