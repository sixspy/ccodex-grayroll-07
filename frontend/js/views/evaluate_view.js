import { api } from "../api.js";
const { ref, onMounted } = Vue;
export const EvaluateView = {
  setup() {
    const form = ref({ flag_key: "checkout.new_pay", env_code: "prod", subject_key: "u-1001" });
    const result = ref(null); const board = ref(null); const err = ref("");
    async function reloadBoard() { board.value = await api("/api/evaluate/board"); }
    async function run() {
      err.value = "";
      try { result.value = await api("/api/evaluate", { method: "POST", body: JSON.stringify(form.value) }); }
      catch (e) { err.value = e.message || String(e); }
    }
    onMounted(reloadBoard);
    return { form, result, board, err, run, reloadBoard };
  },
  template: `
  <div class="grid">
    <div class="panel span-5">
      <h2>在线求值</h2>
      <p class="hint">grayroll-07：求值只认真式规则；未确认影子草案永不参与命中，仅作待确认痕展示，禁止假绿。</p>
      <div class="field"><label>开关键</label><input v-model="form.flag_key" /></div>
      <div class="field"><label>环境</label>
        <select v-model="form.env_code"><option>dev</option><option>staging</option><option>prod</option></select>
      </div>
      <div class="field"><label>主体键</label><input v-model="form.subject_key" /></div>
      <button class="btn" @click="run">求值</button>
      <div class="err" v-if="err">{{ err }}</div>
      <pre v-if="result" style="margin-top:0.8rem">{{ result }}</pre>
      <div v-if="result && result.pending_shadow" style="margin-top:0.6rem">
        <span class="pill warn">待确认影子 #{{ result.pending_shadow.shadow_id }}：{{ result.pending_shadow.percent }}% 未二次确认，正式口径不命中（{{ result.reason }}）</span>
      </div>
      <div v-else-if="result" class="muted" style="margin-top:0.6rem">无待确认影子，求值结果即正式口径。</div>
    </div>
    <div class="panel span-7">
      <h2>正式规则板</h2>
      <table v-if="board">
        <thead><tr><th>开关</th><th>环境</th><th>类型</th><th>%</th><th>版本</th></tr></thead>
        <tbody>
          <tr v-for="(r,i) in board.rules" :key="i">
            <td>{{ r.flag_key }}</td><td>{{ r.env_code }}</td><td>{{ r.kind }}</td><td>{{ r.percent }}</td><td>v{{ r.version }}</td>
          </tr>
        </tbody>
      </table>
      <h2 style="margin-top:1rem">待确认影子（未确认不得当全量）</h2>
      <table v-if="board && board.pending_shadows && board.pending_shadows.length">
        <thead><tr><th>影子ID</th><th>开关</th><th>环境</th><th>比例</th><th>确认态</th></tr></thead>
        <tbody>
          <tr v-for="(p,i) in board.pending_shadows" :key="'p'+i">
            <td>{{ p.shadow_id }}</td><td>{{ p.flag_key }}</td><td>{{ p.env_code }}</td>
            <td>{{ p.percent }}%</td>
            <td><span class="pill warn">待确认（正式零改）</span></td>
          </tr>
        </tbody>
      </table>
      <p class="muted" v-else>无待确认影子。</p>
      <button class="btn secondary" style="margin-top:0.7rem" @click="reloadBoard">刷新</button>
    </div>
  </div>`
};
