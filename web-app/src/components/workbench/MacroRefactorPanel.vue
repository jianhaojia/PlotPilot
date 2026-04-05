<template>
  <div class="refactor-panel">
    <header class="panel-header">
      <div class="header-main">
        <div class="title-row">
          <h3 class="panel-title">宏观重构</h3>
          <n-tag size="small" round :bordered="false">Macro Refactor</n-tag>
        </div>
        <p class="panel-lead">
          扫描人设冲突断点 → 生成重构提案 → 应用修改，<strong>系统性修复全书人设一致性</strong>。
        </p>
      </div>
    </header>

    <!-- Step 1：扫描断点 -->
    <div class="step-block">
      <div class="step-title">
        <n-tag type="info" round size="small">Step 1</n-tag>
        <span>扫描人设冲突断点</span>
      </div>
      <n-space :size="10" align="flex-end" wrap>
        <n-form-item label="目标人设标签" label-placement="top" :show-feedback="false" style="flex:1;min-width:120px">
          <n-input v-model:value="scanTrait" placeholder="如：冷酷、理性、忠诚…" size="small" />
        </n-form-item>
        <n-form-item label="冲突标签（逗号分隔，可选）" label-placement="top" :show-feedback="false" style="flex:2;min-width:180px">
          <n-input v-model:value="scanConflictTags" placeholder="如：动机:冲动,情绪:崩溃" size="small" />
        </n-form-item>
        <n-button type="primary" size="small" :loading="scanning" @click="doScan">扫描</n-button>
      </n-space>

      <template v-if="breakpoints.length > 0">
        <n-divider style="margin:10px 0 6px" />
        <n-text depth="3" style="font-size:12px;margin-bottom:6px;display:block">
          找到 {{ breakpoints.length }} 个冲突断点，点击任意一个生成重构提案：
        </n-text>
        <n-space vertical :size="6">
          <n-card
            v-for="bp in breakpoints"
            :key="bp.event_id"
            size="small"
            hoverable
            :bordered="true"
            class="bp-card"
            :class="{ 'bp-card--active': selectedBreakpoint?.event_id === bp.event_id }"
            @click="selectBreakpoint(bp)"
          >
            <n-space align="center" justify="space-between">
              <n-space align="center" :size="8">
                <n-tag type="warning" size="tiny" round>第 {{ bp.chapter }} 章</n-tag>
                <n-text style="font-size:13px">{{ bp.reason }}</n-text>
              </n-space>
              <n-space :size="4" wrap>
                <n-tag v-for="t in bp.tags" :key="t" size="tiny" round type="error">{{ t }}</n-tag>
              </n-space>
            </n-space>
          </n-card>
        </n-space>
      </template>

      <n-empty v-else-if="scanned && breakpoints.length === 0" description="未发现冲突断点，人设一致性良好">
        <template #icon><span style="font-size:32px">✅</span></template>
      </n-empty>
    </div>

    <!-- Step 2：生成重构提案 -->
    <div v-if="selectedBreakpoint" class="step-block">
      <div class="step-title">
        <n-tag type="warning" round size="small">Step 2</n-tag>
        <span>生成重构提案</span>
        <n-text depth="3" style="font-size:12px">事件 {{ selectedBreakpoint.event_id }} · 第 {{ selectedBreakpoint.chapter }} 章</n-text>
      </div>

      <n-space vertical :size="10">
        <n-form-item label="当前事件摘要" label-placement="top" :show-feedback="false">
          <n-input
            v-model:value="proposalForm.current_event_summary"
            type="textarea"
            placeholder="当前章节发生了什么（从原文提取）"
            :autosize="{ minRows: 2, maxRows: 5 }"
            size="small"
          />
        </n-form-item>
        <n-form-item label="作者意图" label-placement="top" :show-feedback="false">
          <n-input
            v-model:value="proposalForm.author_intent"
            type="textarea"
            placeholder="你希望这个事件达到什么叙事目标？改动的核心是什么？"
            :autosize="{ minRows: 2, maxRows: 4 }"
            size="small"
          />
        </n-form-item>
        <n-button type="warning" size="small" :loading="proposalLoading" :disabled="!proposalForm.author_intent || !proposalForm.current_event_summary" @click="doGenerateProposal">
          生成重构提案
        </n-button>
      </n-space>

      <template v-if="proposal">
        <n-divider style="margin:10px 0 6px" />
        <n-space vertical :size="10">
          <div>
            <n-text strong style="font-size:13px;display:block;margin-bottom:6px">自然语言建议</n-text>
            <n-text style="font-size:13px;line-height:1.7">{{ proposal.natural_language_suggestion }}</n-text>
          </div>
          <div>
            <n-text strong style="font-size:13px;display:block;margin-bottom:6px">推理过程</n-text>
            <n-text depth="3" style="font-size:12px;line-height:1.6">{{ proposal.reasoning }}</n-text>
          </div>
          <div v-if="proposal.suggested_tags.length">
            <n-text strong style="font-size:13px;display:block;margin-bottom:6px">建议标签</n-text>
            <n-space :size="4" wrap>
              <n-tag v-for="t in proposal.suggested_tags" :key="t" size="small" round type="success">{{ t }}</n-tag>
            </n-space>
          </div>
          <div v-if="proposal.suggested_mutations.length">
            <n-text strong style="font-size:13px;display:block;margin-bottom:4px">
              建议的 Mutations（{{ proposal.suggested_mutations.length }} 个）
            </n-text>
            <n-code
              :code="JSON.stringify(proposal.suggested_mutations, null, 2)"
              language="json"
              word-wrap
              style="font-size:11px;max-height:160px;overflow:auto"
            />
          </div>
        </n-space>
      </template>
    </div>

    <!-- Step 3：应用修改 -->
    <div v-if="proposal && selectedBreakpoint" class="step-block">
      <div class="step-title">
        <n-tag type="success" round size="small">Step 3</n-tag>
        <span>应用修改</span>
      </div>

      <n-space vertical :size="10">
        <n-form-item label="修改原因（可选）" label-placement="top" :show-feedback="false">
          <n-input
            v-model:value="applyReason"
            placeholder="记录本次修改的决策原因（便于后续追溯）"
            size="small"
          />
        </n-form-item>

        <n-space :size="8">
          <n-button
            type="success"
            size="small"
            :loading="applyLoading"
            @click="doApply"
          >
            应用建议的全部 Mutations
          </n-button>
          <n-button secondary size="small" @click="resetAll">重新开始</n-button>
        </n-space>

        <template v-if="applyResult">
          <n-alert :type="applyResult.success ? 'success' : 'error'" :show-icon="true" style="font-size:13px">
            {{ applyResult.success
              ? `✓ 已成功应用 ${applyResult.applied_mutations.length} 个 Mutation`
              : '应用失败，请检查事件 ID 是否有效'
            }}
          </n-alert>
        </template>
      </n-space>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useMessage } from 'naive-ui'
import { macroRefactorApi } from '../../api/tools'
import type { LogicBreakpoint, RefactorProposal, ApplyMutationResponse } from '../../api/tools'

interface Props { slug: string }
const props = defineProps<Props>()
const message = useMessage()

// Step 1 — 扫描
const scanTrait = ref('')
const scanConflictTags = ref('')
const scanning = ref(false)
const scanned = ref(false)
const breakpoints = ref<LogicBreakpoint[]>([])
const selectedBreakpoint = ref<LogicBreakpoint | null>(null)

const doScan = async () => {
  if (!scanTrait.value.trim()) { message.warning('请输入目标人设标签'); return }
  scanning.value = true
  scanned.value = false
  breakpoints.value = []
  selectedBreakpoint.value = null
  proposal.value = null
  applyResult.value = null
  try {
    breakpoints.value = await macroRefactorApi.scanBreakpoints(
      props.slug,
      scanTrait.value.trim(),
      scanConflictTags.value.trim() || undefined
    )
    scanned.value = true
    if (breakpoints.value.length === 0) message.success('未发现冲突断点')
    else message.warning(`发现 ${breakpoints.value.length} 个冲突断点`)
  } catch {
    message.error('扫描失败')
  } finally {
    scanning.value = false
  }
}

const selectBreakpoint = (bp: LogicBreakpoint) => {
  selectedBreakpoint.value = bp
  proposal.value = null
  applyResult.value = null
  proposalForm.value = {
    current_event_summary: '',
    author_intent: '',
  }
}

// Step 2 — 生成提案
const proposalForm = ref({ current_event_summary: '', author_intent: '' })
const proposalLoading = ref(false)
const proposal = ref<RefactorProposal | null>(null)

const doGenerateProposal = async () => {
  if (!selectedBreakpoint.value) return
  proposalLoading.value = true
  try {
    proposal.value = await macroRefactorApi.generateProposal(props.slug, {
      event_id: selectedBreakpoint.value.event_id,
      author_intent: proposalForm.value.author_intent,
      current_event_summary: proposalForm.value.current_event_summary,
      current_tags: selectedBreakpoint.value.tags,
    })
  } catch {
    message.error('生成提案失败')
  } finally {
    proposalLoading.value = false
  }
}

// Step 3 — 应用
const applyReason = ref('')
const applyLoading = ref(false)
const applyResult = ref<ApplyMutationResponse | null>(null)

const doApply = async () => {
  if (!selectedBreakpoint.value || !proposal.value) return
  applyLoading.value = true
  try {
    applyResult.value = await macroRefactorApi.applyMutations(props.slug, {
      event_id: selectedBreakpoint.value.event_id,
      mutations: proposal.value.suggested_mutations,
      reason: applyReason.value || undefined,
    })
    if (applyResult.value.success) message.success('Mutations 已成功应用')
    else message.error('应用失败')
  } catch {
    message.error('应用失败，请检查事件数据')
  } finally {
    applyLoading.value = false
  }
}

const resetAll = () => {
  selectedBreakpoint.value = null
  proposal.value = null
  applyResult.value = null
  applyReason.value = ''
}
</script>

<style scoped>
.refactor-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  background: var(--aitext-panel-muted);
  gap: 0;
}

.panel-header {
  padding: 14px 16px 12px;
  border-bottom: 1px solid var(--aitext-split-border);
  background: var(--app-surface);
  flex-shrink: 0;
}
.title-row { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.panel-title { margin: 0; font-size: 15px; font-weight: 600; }
.panel-lead { margin: 0; font-size: 12px; line-height: 1.5; color: var(--text-color-3); }

.step-block {
  padding: 14px 16px;
  border-bottom: 1px solid var(--aitext-split-border);
  background: var(--app-surface);
  flex-shrink: 0;
}
.step-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 12px;
  color: var(--text-color-1);
}

.bp-card {
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.bp-card--active {
  border-color: var(--primary-color) !important;
  box-shadow: 0 0 0 2px rgba(79,70,229,0.15);
}
</style>
