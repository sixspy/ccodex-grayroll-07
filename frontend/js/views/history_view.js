import { api } from "../api.js";
const { ref, onMounted } = Vue;
export const HistoryView = {
  setup() {
    const items = ref([]); const contentions = ref([]); const err = ref("");
    async function reload() {
      try {
        const res = await api("/api/history");
        items.value = res.items || [];
        contentions.value = res.contentions || [];
      } catch (e) { err.value = e.message || String(e); }
    }
    onMounted(reload);
    return { items, contentions, err, reload };
  },
  template: `
  <div class="panel">
    <h2>变更历史</h2>
    <p class="hint">grayroll-07：命运取舍（正式变更）与争用核销（败方争用痕）分两段；被拒写的生产全量不产生正式变更。</p>
    <div class="err" v-if="err">{{ err }}</div>
    <h3 style="margin:0.4rem 0 0.3rem">正式变更（命运取舍）</h3>
    <table>
      <thead><tr><th>时间动作</th><th>开关</th><th>环境</th><th>详情</th><th>操作者</th></tr></thead>
      <tbody>
        <tr v-for="it in items" :key="it.id">
          <td>{{ it.action }}</td><td>{{ it.flag_key || '-' }}</td><td>{{ it.env_code || '-' }}</td>
          <td>{{ it.detail }}</td><td>{{ it.actor }}</td>
        </tr>
      </tbody>
    </table>

    <h3 style="margin:0.9rem 0 0.3rem">争用核销痕（败方零正式改）</h3>
    <table v-if="contentions.length">
      <thead><tr><th>锁键</th><th>败方</th><th>胜方</th></tr></thead>
      <tbody>
        <tr v-for="m in contentions" :key="m.id">
          <td><code>{{ m.lock_key }}</code></td><td>{{ m.loser }}</td><td>{{ m.winner }}</td>
        </tr>
      </tbody>
    </table>
    <p class="muted" v-else>无争用痕。</p>
    <button class="btn secondary" style="margin-top:0.7rem" @click="reload">刷新</button>
  </div>`
};
