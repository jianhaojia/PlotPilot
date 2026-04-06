<template>
  <div class="autopilot-panel">
    <!-- 状态头 -->
    <div class="ap-header">
      <span class="ap-dot" :class="dotClass"></span>
      <span class="ap-title">全托管驾驶</span>
      <span class="ap-stage-tag" :class="stageTagClass">{{ stageLabel }}</span>
    </div>

    <!-- 进度条 -->
    <n-progress
      type="line"
      :percentage="progressPct"
      :color="progressColor"
      indicator-placement="inside"
      :height="14"
      style="margin: 4px 0"
    />

    <!-- 数据格 -->
    <div class="ap-grid">
      <div class="ap-cell">
        <div class="label">已写章节</div>
        <div class="value">{{ status?.completed_chapters || 0 }} / {{ status?.target_chapters || '-' }}</div>
      </div>
      <div class="ap-cell">
        <div class="label">总字数</div>
        <div class="value">{{ formatWords(status?.total_words) }}</div>
      </div>
      <div class="ap-cell">
        <div class="label">当前幕 / 节拍</div>
        <div class="value">
          第 {{ (status?.current_act || 0) + 1 }} 幕
          <span v-if="isWriting">· {{ beatLabel }}</span>
        </div>
      </div>
      <div class="ap-cell">
        <div class="label">上章张力</div>
        <div class="value" :style="{ color: tensionColor }">{{ tensionLabel }}</div>
      </div>
    </div>

    <!-- 熔断警告 -->
    <n-alert v-if="hasErrors" type="error" :show-icon="true" style="margin: 4px 0; font-size: 12px">
      连续失败 {{ status.consecutive_error_count }} 次，守护进程可能已熔断
    </n-alert>

    <!-- 审阅等待提示 -->
    <n-alert v-if="needsReview" type="warning" style="margin: 4px 0; font-size: 12px">
      ✍️ 大纲已生成，请确认后继续写作
    </n-alert>

    <!-- 操作按钮 -->
    <n-space justify="end" size="small">
      <n-button v-if="needsReview" type="warning" size="small" :loading="toggling" @click="resume">
        确认大纲，继续写作
      </n-button>
      <n-button v-if="!isRunning && !needsReview" type="primary" size="small" :loading="toggling" @click="openStartModal">
        🚀 启动全托管
      </n-button>
      <n-button v-if="isRunning" type="error" ghost size="small" :loading="toggling" @click="stop">
        ⏹ 停止
      </n-button>
    </n-space>

    <!-- 启动配置弹窗 -->
    <n-modal v-model:show="showStartModal" title="自动驾驶配置" preset="dialog" positive-text="启动" @positive-click="start">
      <n-form>
        <n-form-item label="本次最多生成章节数（成本控制）">
          <n-input-number v-model:value="startConfig.max_auto_chapters" :min="1" :max="200" />
        </n-form-item>
      </n-form>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useMessage } from 'naive-ui'

const props = defineProps({ novelId: String })
const emit = defineEmits(['status-change'])
const message = useMessage()

const status = ref(null)
const toggling = ref(false)
const showStartModal = ref(false)
const startConfig = ref({ max_auto_chapters: 50 })
let eventSource = null

// 计算属性
const isRunning  = computed(() => status.value?.autopilot_status === 'running')
const needsReview = computed(() => status.value?.needs_review === true)
const isWriting  = computed(() => status.value?.current_stage === 'writing')
const hasErrors  = computed(() => (status.value?.consecutive_error_count || 0) >= 3)
const progressPct = computed(() => status.value?.progress_pct || 0)
const progressColor = computed(() => {
  if (hasErrors.value) return '#d03050'
  if (needsReview.value) return '#f0a020'
  return '#18a058'
})

const dotClass = computed(() => ({
  'dot-running': isRunning.value && !needsReview.value,
  'dot-review':  needsReview.value,
  'dot-error':   status.value?.autopilot_status === 'error',
  'dot-stopped': !isRunning.value && !needsReview.value,
}))

const stageLabel = computed(() => {
  const m = {
    macro_planning: '宏观规划', act_planning: '幕级规划',
    writing: '撰写中', auditing: '审计中',
    paused_for_review: '待审阅', completed: '已完成',
  }
  return m[status.value?.current_stage] || '待机'
})

const stageTagClass = computed(() => ({
  'tag-active':  isRunning.value && !needsReview.value,
  'tag-review':  needsReview.value,
  'tag-idle':    !isRunning.value && !needsReview.value,
}))

const beatLabel = computed(() => {
  const b = status.value?.current_beat_index || 0
  return b === 0 ? '准备' : `节拍 ${b}`
})

const tensionLabel = computed(() => {
  const t = status.value?.last_chapter_tension || 0
  if (t >= 8) return `🔥 高潮 (${t}/10)`
  if (t >= 5) return `⚡ 冲突 (${t}/10)`
  return `🌊 平缓 (${t}/10)`
})

const tensionColor = computed(() => {
  const t = status.value?.last_chapter_tension || 0
  return t >= 8 ? '#d03050' : t >= 5 ? '#f0a020' : '#18a058'
})

// 格式化
function formatWords(n) {
  if (!n) return '0'
  return n >= 10000 ? `${(n / 10000).toFixed(1)}万` : String(n)
}

// API 调用
const base = () => `/api/v1/autopilot/${props.novelId}`

async function fetchStatus() {
  const res = await fetch(`${base()}/status`)
  if (res.ok) {
    status.value = await res.json()
    emit('status-change', status.value)
  }
}

function connectSSE() {
  if (eventSource) eventSource.close()
  eventSource = new EventSource(`${base()}/events`)
  eventSource.onmessage = (e) => {
    status.value = JSON.parse(e.data)
    emit('status-change', status.value)
  }
  eventSource.onerror = () => {
    eventSource.close()
    setTimeout(connectSSE, 5000)
  }
}

function openStartModal() { showStartModal.value = true }

async function start() {
  toggling.value = true
  const res = await fetch(`${base()}/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(startConfig.value)
  })
  if (res.ok) message.success('自动驾驶已启动')
  else message.error('启动失败')
  await fetchStatus()
  toggling.value = false
}

async function stop() {
  toggling.value = true
  await fetch(`${base()}/stop`, { method: 'POST' })
  message.info('已停止')
  await fetchStatus()
  toggling.value = false
}

async function resume() {
  toggling.value = true
  const res = await fetch(`${base()}/resume`, { method: 'POST' })
  if (res.ok) message.success('已确认大纲，开始写作')
  else { const e = await res.json(); message.error(e.detail || '恢复失败') }
  await fetchStatus()
  toggling.value = false
}

onMounted(() => { fetchStatus(); connectSSE() })
onUnmounted(() => eventSource?.close())
</script>

<style scoped>
.autopilot-panel {
  background: #18181c;
  border: 1px solid #2d2d30;
  border-radius: 10px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 280px;
}
.ap-header { display: flex; align-items: center; gap: 8px; }
.ap-dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }
.dot-running { background: #18a058; animation: pulse 1.4s ease-in-out infinite; }
.dot-review  { background: #f0a020; animation: pulse 0.8s ease-in-out infinite; }
.dot-error   { background: #d03050; }
.dot-stopped { background: #555; }
@keyframes pulse { 0%,100% { opacity:1; transform:scale(1); } 50% { opacity:.4; transform:scale(.85); } }

.ap-title { font-weight: 600; color: #eee; font-size: 14px; }
.ap-stage-tag {
  margin-left: auto; font-size: 11px; padding: 2px 8px;
  border-radius: 10px; font-weight: 500;
}
.tag-active  { background: rgba(24,160,88,.2); color: #18a058; }
.tag-review  { background: rgba(240,160,32,.2); color: #f0a020; }
.tag-idle    { background: rgba(100,100,100,.2); color: #888; }

.ap-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px 12px; }
.ap-cell { text-align: center; }
.ap-cell .label { font-size: 10px; color: #666; margin-bottom: 2px; }
.ap-cell .value { font-size: 14px; font-weight: 600; color: #ddd; }
</style>
