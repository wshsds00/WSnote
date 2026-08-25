import { ref } from 'vue'

const KEY = 'wsnote-theme'

/** 当前是否为深色主题（ref，供组件响应式使用） */
const isDark = ref(typeof document !== 'undefined' && document.documentElement.classList.contains('dark'))

function apply(v: boolean) {
  document.documentElement.classList.toggle('dark', v)
  try {
    localStorage.setItem(KEY, v ? 'dark' : 'light')
  } catch {
    /* localStorage 不可用时静默忽略 */
  }
}

export function useTheme() {
  function toggle() {
    isDark.value = !isDark.value
    apply(isDark.value)
  }
  function set(v: boolean) {
    isDark.value = v
    apply(v)
  }
  return { isDark, toggle, set }
}
