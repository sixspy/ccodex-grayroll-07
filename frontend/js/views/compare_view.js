import { api } from "../api.js";
const { ref, onMounted } = Vue;
export const CompareView = {
  setup() {
    const flagId = ref(1); const envId = ref(3);
    const detail = ref(null); const matrix = ref(null); const err = ref("");
    async function reload() {
      err.value = "";
      try {
        detail.value = await api(`/api/compare/flag/${flagId.value}/env/${envId.value}`);
        matrix.value = await api("/api/compare/matrix");
      } catch (e) { err.value = e.message || String(e); }
    }
    onMounted(reload);
    return { flagId, envId, detail, matrix, err, reload };
  },
  template: `
  <div class="grid">
    <div class="panel span-5">
      <h2>正式 vs 影子</h2>
      <p class="hint">grayroll-07：影子行带分步确认痕；未确认全量影子与正式规则的差异显式可见，正式零改。</p>
      <div class="field"><label>开关ID</label><input type="number" v-model.number="flagId" /></div>
      <div class="field"><label>环境ID</label><input type="number" v-model.number="envId" /></div>
      <button class="btn secondary" @click="reload">对比</button>
      <div class="err" v-if="err">{{ err }}</div>

      <div v-if="detail" style="margin-top:0.8rem">
        <div v-if="detail.confirmation && detail.confirmation.awaiting_second_confirmation">
          <span class="pill warn">存在待二次确认影子（confirmed=false，正式零改）</span>
        </div>
        <h3 style="margin:0.6rem 0 0.3rem">待确认发布影子</h3>
        <table v-if="detail.open_release_shadows.length">
          <thead><tr><th>ID</th><th>比例</th><th>确认态</th><th>正式改动</th></tr></thead>
          <tbody><tr v-for="s in detail.open_release_shadows" :key="s.id">
            <td>{{ s.id }}</td><td>{{ s.percent }}%</td>
            <td><span class="pill warn" v-if="!s.confirmed">待确认</span></td>
            <td>{{ s.official_changed ? '已改' : '零改' }}</td>
          </tr></tbody>
        </table>
        <p class="muted" v-else>无待确认发布影子。</p>
        <h3 style="margin:0.6rem 0 0.3rem">差异（未确认以 official 为准）</h3>
        <table v-if="detail.diffs.length">
          <thead><tr><th>字段</th><th>正式</th><th>影子</th><th>说明</th></tr></thead>
          <tbody><tr v-for="(d,i) in detail.diffs" :key="i">
            <td>{{ d.field }}</td><td>{{ d.official }}</td><td>{{ d.shadow }}</td>
            <td class="muted">{{ d.note }}</td>
          </tr></tbody>
        </table>
        <p class="muted" v-else>无差异。</p>
      </div>
    </div>
    <div class="panel span-7">
      <h2>环境矩阵</h2>
      <div v-if="matrix">
        <table>
          <thead>
            <tr>
              <th>开关</th>
              <th v-for="e in matrix.envs" :key="e.id">{{ e.code }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in matrix.matrix" :key="row.flag_id">
              <td>{{ row.flag_key }}</td>
              <td v-for="c in row.cells" :key="c.env_id">
                <span v-if="c.has_rule">{{ c.percent }}% v{{ c.version }}</span>
                <span v-else class="muted">—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>`
};
