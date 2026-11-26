import { api } from "../api.js";
const { ref, computed, onMounted } = Vue;
export const ReleasesView = {
  setup() {
    const official = ref([]); const shadows = ref([]);
    const form = ref({
      flag_id: 3, env_id: 1, kind: "percent", percent: 30, cohort_id: null,
      summary: "开发环境三成灰度试跑", use_shadow: false,
    });
    const envs = ref([]);
    const err = ref(""); const msg = ref("");
    // grayroll-07：prod 全量禁令前端同源提示（以后端 /api/envs 风险口径为准）
    const guard = ref(null);
    const prodEnv = computed(() => envs.value.find(e => e.code === "prod"));
    const willBlock = computed(() => {
      const env = envs.value.find(e => e.id === form.value.env_id);
      return Boolean(env && env.code === "prod" && Number(form.value.percent) >= 100 && !form.value.use_shadow);
    });
    const blockHint = computed(() => {
      if (!willBlock.value) return "";
      return "生产环境禁止一键全量（100%）正式发布：请改走分步爬坡，或勾选影子草案经二次确认后升正。";
    });
    async function reload() {
      const [res, envRes] = await Promise.all([api("/api/releases"), api("/api/envs")]);
      official.value = res.official || []; shadows.value = res.shadows || [];
      envs.value = envRes.items || [];
      guard.value = envRes.prod_full_rollout_guard || null;
    }
    async function publish() {
      err.value = ""; msg.value = "";
      try {
        const body = { ...form.value, cohort_id: form.value.cohort_id || null };
        const res = await api("/api/releases/publish", { method: "POST", body: JSON.stringify(body) });
        msg.value = res.mode === "shadow"
          ? "已落影子草案：正式零改，须在对比/发布页二次确认升正后才生效"
          : `已提交：${res.mode}`;
        await reload();
      } catch (e) { err.value = e.message || String(e); }
    }
    async function promote(id) {
      err.value = "";
      try { await api(`/api/releases/shadow/${id}/promote`, { method: "POST", body: "{}" }); await reload(); }
      catch (e) { err.value = e.message || String(e); }
    }
    onMounted(reload);
    return { official, shadows, form, envs, err, msg, guard, willBlock, blockHint, publish, promote, reload };
  },
  template: `
  <div class="grid">
    <div class="panel span-5">
      <h2>发布生效</h2>
      <p class="hint">默认甲路径：同事务写正式配置并升版本。勾选影子则走乙路径。</p>
      <div class="pill danger" style="display:inline-block;margin-bottom:0.6rem">
        grayroll-07 禁令：生产（prod）禁止一键全量 100% 正式发布，须分步或影子二次确认
      </div>
      <div class="field"><label>开关ID</label><input type="number" v-model.number="form.flag_id" /></div>
      <div class="field"><label>环境ID</label><input type="number" v-model.number="form.env_id" /></div>
      <div class="field"><label>类型</label>
        <select v-model="form.kind"><option>percent</option><option>cohort</option><option>percent_and_cohort</option></select>
      </div>
      <div class="field"><label>比例</label><input type="number" v-model.number="form.percent" /></div>
      <div class="field"><label>说明</label><textarea v-model="form.summary" rows="2"></textarea></div>
      <div class="field"><label><input type="checkbox" v-model="form.use_shadow" /> 使用影子草案（乙路径，正式零改）</label></div>
      <div class="err" v-if="blockHint" style="margin:0.3rem 0 0.6rem">{{ blockHint }}</div>
      <button class="btn" :disabled="willBlock" @click="publish">提交发布</button>
      <p class="muted" v-if="willBlock">该提交会被后端整笔拒写（正式零增），按钮已禁用。</p>
      <p class="muted" v-if="msg">{{ msg }}</p>
      <div class="err" v-if="err">{{ err }}</div>
    </div>
    <div class="panel span-7">
      <h2>正式发布</h2>
      <table><thead><tr><th>开关</th><th>环境</th><th>版本</th><th>说明</th></tr></thead>
      <tbody>
        <tr v-for="r in official" :key="r.id">
          <td>{{ r.flag_key }}</td><td>{{ r.env_code }}</td><td>v{{ r.version }}</td><td>{{ r.summary }}</td>
        </tr>
      </tbody></table>
      <h2 style="margin-top:1rem">影子发布（待二次确认）</h2>
      <p class="hint">open = 未确认，正式区零改、求值不命中；promoted = 已原子升正。</p>
      <table><thead><tr><th>ID</th><th>开关</th><th>比例</th><th>确认态</th><th></th></tr></thead>
        <tbody>
        <tr v-for="s in shadows" :key="'s'+s.id">
          <td>{{ s.id }}</td><td>{{ s.flag_id }}</td><td>{{ s.percent }}%</td>
          <td>
            <span class="pill warn" v-if="s.status==='open'">待确认（正式零改）</span>
            <span class="pill" v-else>{{ s.status }}</span>
          </td>
          <td><button class="btn secondary" v-if="s.status==='open'" @click="promote(s.id)">二次确认升正</button></td>
        </tr>
      </tbody></table>
      <div v-if="guard && guard.pending_full_shadows && guard.pending_full_shadows.length" style="margin-top:0.8rem">
        <span class="pill warn">生产全量待确认影子 {{ guard.pending_full_shadows.length }} 条（未确认不得全开）</span>
      </div>
    </div>
  </div>`
};
