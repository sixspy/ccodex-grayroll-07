import { api } from "../api.js";
const { ref, onMounted } = Vue;
export const EnvsView = {
  setup() {
    const items = ref([]); const guard = ref(null); const err = ref("");
    async function reload() {
      try {
        const res = await api("/api/envs");
        items.value = res.items || [];
        guard.value = res.prod_full_rollout_guard || null;
      } catch (e) { err.value = e.message || String(e); }
    }
    onMounted(reload);
    return { items, guard, err, reload };
  },
  template: `
  <div class="panel">
    <h2>环境</h2>
    <p class="hint">风险等级越高，发布与熔断越敏感；生产环境默认需更谨慎的发布说明。</p>
    <div class="err" v-if="err">{{ err }}</div>
    <table>
      <thead><tr><th>代码</th><th>名称</th><th>风险等级</th></tr></thead>
      <tbody><tr v-for="it in items" :key="it.id">
        <td>{{ it.code }}
          <span class="pill danger" v-if="it.code==='prod'">禁一键全量</span>
        </td>
        <td>{{ it.title }}</td><td>{{ it.risk_level }}</td>
      </tr></tbody>
    </table>

    <div v-if="guard" style="margin-top:1.2rem">
      <h2 style="margin-top:0.5rem">生产全量与环境风险联查（跨表）</h2>
      <p class="hint">
        grayroll-07：{{ guard.env_code }} 环境 percent={{ guard.full_rollout_percent }} 的正式发布已被后端封死
        （forbid_official_full={{ guard.forbid_official_full }}）。全量只许落影子草案，二次确认后原子升正。
      </p>
      <h3 style="margin:0.6rem 0 0.3rem">正式全量规则（应仅来自二次确认升正）</h3>
      <table v-if="guard.official_full_rows && guard.official_full_rows.length">
        <thead><tr><th>开关</th><th>环境</th><th>风险级</th><th>比例</th><th>版本</th><th>来源</th></tr></thead>
        <tbody><tr v-for="(r,i) in guard.official_full_rows" :key="'of'+i">
          <td>{{ r.flag_key }}</td><td>{{ r.env_code }}</td><td>{{ r.risk_level }}</td>
          <td>{{ r.percent }}%</td><td>v{{ r.version }}</td><td>{{ r.source }}</td>
        </tr></tbody>
      </table>
      <p class="muted" v-else>无正式全量规则。</p>

      <h3 style="margin:0.6rem 0 0.3rem">待确认全量影子（未确认不得全开）</h3>
      <table v-if="guard.pending_full_shadows && guard.pending_full_shadows.length">
        <thead><tr><th>影子ID</th><th>开关</th><th>环境</th><th>比例</th><th>状态</th><th>来源</th></tr></thead>
        <tbody><tr v-for="(s,i) in guard.pending_full_shadows" :key="'ps'+i">
          <td>{{ s.shadow_id }}</td><td>{{ s.flag_key }}</td><td>{{ s.env_code }}</td>
          <td>{{ s.percent }}%</td>
          <td><span class="pill warn">待确认（正式零改）</span></td>
          <td>{{ s.source }}</td>
        </tr></tbody>
      </table>
      <p class="muted" v-else>无待确认全量影子。</p>
    </div>
  </div>`
};
