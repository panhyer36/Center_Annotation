import { createRouter, createWebHistory } from 'vue-router'
import SetupPage from '../views/SetupPage.vue'
import AnnotatePage from '../views/AnnotatePage.vue'

const routes = [
  {
    path: '/',
    name: 'Setup',
    component: SetupPage
  },
  {
    path: '/annotate',
    name: 'Annotate',
    component: AnnotatePage
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
