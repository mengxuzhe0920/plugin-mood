<script setup lang="ts">
import { onMounted } from "vue";

/**
 * 小窝心情在 UC 里不再用 iframe 内嵌，进来直接整页跳转到 /mood/ 独立页面。
 */
onMounted(() => {
  window.location.replace("/mood/");
});
</script>

<template>
  <div class="mood-view">
    <div class="mood-jump">正在打开小窝心情…</div>
  </div>
</template>

<style scoped>
.mood-view {
  height: calc(100vh - 64px);
  margin: -16px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fafafa;
}
.mood-jump {
  font-size: 14px;
  color: #8c8c8c;
}
</style>
