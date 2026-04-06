<template>
  <div class="work-area">
    <header class="work-header">
      <div class="work-title-wrap">
        <h2 class="work-title">{{ bookTitle || slug }}</h2>
        <n-text depth="3" class="work-sub">{{ slug }}</n-text>
      </div>
      <n-space :size="8" align="center" wrap class="work-header-actions">
        <n-button type="primary" size="small" @click="showWorkflowModal = true" title="完整工作流：场景分析 + 流式生成 + 一致性检验，推荐">
          📖 工作流撰稿
        </n-button>
      </n-space>
    </header>

    <!-- 自动驾驶面板 -->
    <div class="autopilot-container">
      <AutopilotPanel :novel-id="slug" @status-change="handleAutopilotStatusChange" />
    </div>

    <header class="work-subheader">
    </header>

    <div class="work-main">
      <div v-if="currentChapter" class="chapter-editor">
        <div class="editor-header">
          <div class="editor-title">
            <h3>{{ currentChapter.title || `第${currentChapter.number}章` }}</h3>
            <n-tag size="small" :type="currentChapter.word_count > 0 ? 'success' : 'default'" round>
              {{ currentChapter.word_count > 0 ? '已收稿' : '未收稿' }}
            </n-tag>
          </div>
          <n-space :size="8">
            <n-button size="small" @click="handleReload" :disabled="loading">
              重新加载
            </n-button>
            <n-button size="small" type="primary" @click="handleSave" :disabled="!hasChanges" :loading="saving">
              保存
            </n-button>
          </n-space>
        </div>

        <div class="editor-body">
          <n-input
            v-model:value="chapterContent"
            type="textarea"
            placeholder="章节内容..."
            :autosize="{ minRows: 22 }"
            @update:value="handleContentChange"
          />
        </div>

        <div class="editor-footer">
          <n-space :size="8" align="center" justify="space-between" style="width: 100%">
            <n-text depth="3">字数: {{ wordCount }}</n-text>
            <n-space :size="8">
              <n-button size="small" secondary @click="handleGenerateChapter" :loading="generating">
                AI 生成本章
              </n-button>
              <n-tooltip trigger="hover" :disabled="wordCount > 0">
                <template #trigger>
                  <n-button size="small" @click="handleReviewChapter" :loading="reviewing" :disabled="wordCount === 0">
                    AI 审稿
                  </n-button>
                </template>
                <span>请先在编辑区写入内容或保存后再审稿</span>
              </n-tooltip>
              <n-button size="small" secondary @click="openTensionModal" title="卡关时分析张力缺口，获得突破建议">
                ⚡ 卡关突破
              </n-button>
              <n-button size="small" secondary @click="handleContinuePlanning" :disabled="!currentChapter" title="章节写完后检测当前幕进度，决定是否创建下一幕">
                🎭 续规划
              </n-button>
            </n-space>
          </n-space>
        </div>

        <!-- 续规划 badge -->
        <n-alert
          v-if="continuePlanBadge"
          type="success"
          :title="continuePlanBadge.message"
          closable
          @close="continuePlanBadge = null"
          style="margin-top: 8px; font-size: 13px"
        >
          <n-button size="tiny" type="primary" @click="handleContinuePlanning">
            打开续规划
          </n-button>
        </n-alert>

        <div v-if="reviewResult" class="review-result">
          <n-card title="审稿结果" size="small" :bordered="false">
            <template #header-extra>
              <n-button size="tiny" text @click="reviewResult = null">
                关闭
              </n-button>
            </template>
            <n-space vertical :size="12">
              <div class="review-score">
                <n-text strong>评分: </n-text>
                <n-tag :type="reviewResult.score >= 80 ? 'success' : reviewResult.score >= 60 ? 'warning' : 'error'" size="large">
                  {{ reviewResult.score }}/100
                </n-tag>
              </div>
              <n-divider style="margin: 8px 0" />
              <div v-if="reviewResult.suggestions && reviewResult.suggestions.length > 0">
                <n-text strong>改进建议:</n-text>
                <n-list bordered style="margin-top: 8px">
                  <n-list-item v-for="(suggestion, index) in reviewResult.suggestions" :key="index">
                    <n-thing>
                      <template #header>
                        <n-text>{{ index + 1 }}. {{ suggestion }}</n-text>
                      </template>
                    </n-thing>
                  </n-list-item>
                </n-list>
              </div>
              <div v-else>
                <n-text depth="3">暂无改进建议</n-text>
              </div>
            </n-space>
          </n-card>
        </div>
      </div>

      <n-empty v-else description="请从左侧选择章节，或使用顶部「托管连写」批量生成多章" class="work-empty" />
    </div>

    <!-- 托管连写弹窗 -->
    <n-modal
      v-model:show="showHostedModal"
      preset="card"
      title="托管连写"
      style="width: min(820px, 96vw); max-height: min(92vh, 900px)"
      :segmented="{ content: true, footer: 'soft' }"
      :mask-closable="!hostedRunning"
    >
      <template #header-extra>
        <n-text depth="3" style="font-size: 12px">自动生成多章，实时显示进度</n-text>
      </template>

      <n-scrollbar style="max-height: min(78vh, 760px)">
        <n-space vertical :size="20">
          <n-alert type="info" :show-icon="true">
            全自动区间生成：每章先用 AI 生成大纲，再流式生成正文。请确保章节已在书中存在，否则无法自动保存。
          </n-alert>

          <n-card title="配置" size="small" :bordered="false">
            <n-space vertical :size="16">
              <n-form-item label="章节范围" label-placement="left" label-width="80">
                <n-space :size="12" align="center">
                  <n-input-number v-model:value="hostedFrom" :min="1" :disabled="hostedRunning" placeholder="起始章" style="width: 100px" />
                  <n-text depth="3">至</n-text>
                  <n-input-number v-model:value="hostedTo" :min="1" :disabled="hostedRunning" placeholder="结束章" style="width: 100px" />
                </n-space>
              </n-form-item>

              <n-space vertical :size="8">
                <n-checkbox v-model:checked="hostedAutoOutline" :disabled="hostedRunning" size="small">
                  自动生成大纲（使用 AI 生成每章要点，推荐）
                </n-checkbox>
                <n-checkbox v-model:checked="hostedAutoSave" :disabled="hostedRunning" size="small">
                  自动保存（每章生成后自动写入章节正文）
                </n-checkbox>
              </n-space>

              <n-button
                type="primary"
                @click="handleStartHosted"
                :loading="hostedRunning"
                :disabled="hostedRunning"
                size="medium"
                block
              >
                {{ hostedRunning ? '生成中...' : '开始托管连写' }}
              </n-button>
            </n-space>
          </n-card>

          <n-card v-if="hostedRunning || hostedLog" title="生成日志" size="small" :bordered="false">
            <template #header-extra>
              <n-button size="tiny" @click="hostedLog = ''" :disabled="hostedRunning">清空</n-button>
            </template>
            <n-scrollbar style="max-height: 400px">
              <div class="output-area">
                <pre>{{ hostedLog }}</pre>
              </div>
            </n-scrollbar>
          </n-card>
        </n-space>
      </n-scrollbar>

      <template #footer>
        <n-space justify="end">
          <n-button @click="showHostedModal = false" :disabled="hostedRunning">关闭</n-button>
          <n-button v-if="hostedRunning" secondary @click="stopHosted">停止</n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- AI 生成本章弹窗 -->
    <n-modal
      v-model:show="showGenerateModal"
      preset="card"
      title="AI 生成本章"
      style="width: min(820px, 96vw); max-height: min(92vh, 900px)"
      :segmented="{ content: true, footer: 'soft' }"
      :mask-closable="!generating"
    >
      <template #header-extra>
        <n-text depth="3" style="font-size: 12px">流式生成，实时显示</n-text>
      </template>

      <n-scrollbar style="max-height: min(78vh, 760px)">
        <n-space vertical :size="20">
          <n-alert type="info" :show-icon="true">
            为当前章节生成内容，支持自定义大纲。生成完成后可编辑并保存。
          </n-alert>

          <n-card title="配置" size="small" :bordered="false">
            <n-space vertical :size="16">
              <n-form-item label="章节" label-placement="left" label-width="80">
                <n-text>第 {{ currentChapter?.number }} 章 - {{ currentChapter?.title }}</n-text>
              </n-form-item>

              <n-form-item label="大纲" label-placement="left" label-width="80">
                <n-input
                  v-model:value="generateOutline"
                  type="textarea"
                  placeholder="输入章节大纲（可选，留空则使用默认大纲）"
                  :autosize="{ minRows: 3, maxRows: 6 }"
                  :disabled="generating"
                />
              </n-form-item>

              <n-form-item label="场记分析" label-placement="left" label-width="80" :show-feedback="false">
                <n-space align="center" :size="8">
                  <n-switch v-model:value="useSceneDirector" :disabled="generating" size="small" />
                  <n-text depth="3" style="font-size: 12px">
                    生成前分析场景（精准过滤出场角色/地点，提升上下文质量）
                  </n-text>
                </n-space>
              </n-form-item>

              <n-alert v-if="sceneDirectorError" type="warning" :show-icon="true" style="font-size: 12px">
                场记分析失败（不影响生成）：{{ sceneDirectorError }}
              </n-alert>

              <n-button
                type="primary"
                @click="handleStartGenerate"
                :loading="generating"
                :disabled="generating"
                size="medium"
                block
              >
                {{ generating ? (analyzingScene ? '分析场景中...' : '生成中...') : '开始生成' }}
              </n-button>
            </n-space>
          </n-card>

          <!-- 上下文预览 -->
          <n-card size="small" :bordered="false">
            <template #header>
              <n-space align="center" justify="space-between" style="width:100%">
                <n-space align="center" :size="6">
                  <span style="font-size:13px;font-weight:600">上下文预览</span>
                  <n-text depth="3" style="font-size:11px">AI 实际接收到的三层信息</n-text>
                </n-space>
                <n-button
                  size="tiny"
                  secondary
                  :loading="loadingContext"
                  @click="previewContext"
                >
                  {{ contextPreview ? '重新获取' : '预览' }}
                </n-button>
              </n-space>
            </template>
            <template v-if="contextPreview">
              <!-- Token 分布 -->
              <n-space vertical :size="8">
                <n-space :size="6" wrap>
                  <n-tag size="small" type="info" round>
                    L1 核心 {{ contextPreview.token_usage.layer1 }} tok
                  </n-tag>
                  <n-tag size="small" type="success" round>
                    L2 检索 {{ contextPreview.token_usage.layer2 }} tok
                  </n-tag>
                  <n-tag size="small" type="warning" round>
                    L3 近期 {{ contextPreview.token_usage.layer3 }} tok
                  </n-tag>
                  <n-tag size="small" round>
                    合计 {{ contextPreview.token_usage.total }} / {{ contextPreview.token_usage.limit }}
                  </n-tag>
                </n-space>
                <n-progress
                  v-if="contextPreview.token_usage.limit > 0"
                  type="line"
                  :percentage="Math.min(100, Math.round(contextPreview.token_usage.total / contextPreview.token_usage.limit * 100))"
                  :height="6"
                  :border-radius="4"
                  :show-indicator="false"
                  :color="contextPreview.token_usage.total / contextPreview.token_usage.limit > 0.9 ? '#f0a020' : '#18a058'"
                />
                <n-collapse>
                  <n-collapse-item title="Layer 1 · 核心设定（Bible + 伏笔）" name="l1">
                    <n-code :code="contextPreview.layer1.content" word-wrap style="font-size:11px;max-height:200px;overflow:auto" />
                  </n-collapse-item>
                  <n-collapse-item title="Layer 2 · 智能检索（向量相关段落）" name="l2">
                    <n-code :code="contextPreview.layer2.content || '（向量检索未启用或无匹配）'" word-wrap style="font-size:11px;max-height:200px;overflow:auto" />
                  </n-collapse-item>
                  <n-collapse-item title="Layer 3 · 近期章节（滑动窗口）" name="l3">
                    <n-code :code="contextPreview.layer3.content" word-wrap style="font-size:11px;max-height:200px;overflow:auto" />
                  </n-collapse-item>
                </n-collapse>
              </n-space>
            </template>
            <n-text v-else depth="3" style="font-size:12px">
              点击「预览」查看 AI 生成时实际使用的上下文内容及 token 分布。
            </n-text>
          </n-card>

          <n-card v-if="generating || generatedContent" title="生成内容" size="small" :bordered="false">
            <template #header-extra>
              <n-space :size="8">
                <n-button v-if="generatedContent && !generating" size="tiny" type="primary" @click="handleSaveGenerated" :loading="saving">
                  保存到章节
                </n-button>
                <n-button size="tiny" @click="generatedContent = ''" :disabled="generating">清空</n-button>
              </n-space>
            </template>
            <n-scrollbar style="max-height: 500px">
              <n-input
                v-model:value="generatedContent"
                type="textarea"
                :autosize="{ minRows: 15, maxRows: 30 }"
                :readonly="generating"
                placeholder="生成的内容将在此显示..."
              />
            </n-scrollbar>
          </n-card>
        </n-space>
      </n-scrollbar>

      <template #footer>
        <n-space justify="end">
          <n-button @click="showGenerateModal = false" :disabled="generating">关闭</n-button>
          <n-button v-if="generating" secondary @click="stopGenerate">停止</n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- 张力弹弓弹窗 -->
    <n-modal
      v-model:show="showTensionModal"
      preset="card"
      title="⚡ 卡关突破 · 张力弹弓"
      style="width: min(560px, 96vw)"
    >
      <n-space vertical :size="16">
        <n-alert type="info" :show-icon="false" style="font-size:13px">
          描述卡关原因（可选），AI 会诊断当前章节张力缺口并给出突破建议。
        </n-alert>

        <n-form-item label="卡关原因" label-placement="top" :show-feedback="false">
          <n-input
            v-model:value="tensionStuckReason"
            type="textarea"
            placeholder="例：人物对话没有冲突，场景推进感觉平淡……（留空也可分析）"
            :autosize="{ minRows: 2, maxRows: 5 }"
          />
        </n-form-item>

        <n-button type="primary" block :loading="tensionLoading" @click="runTensionSlingshot">
          开始分析
        </n-button>

        <template v-if="tensionResult">
          <n-divider style="margin:4px 0" />
          <n-space vertical :size="10">
            <n-space align="center" :size="8">
              <n-text strong>张力等级</n-text>
              <n-tag
                :type="tensionResult.tension_level === 'high' ? 'success' : tensionResult.tension_level === 'medium' ? 'warning' : 'error'"
                round
              >
                {{ tensionResult.tension_level === 'high' ? '高张力' : tensionResult.tension_level === 'medium' ? '中等' : '低张力 ⚠' }}
              </n-tag>
            </n-space>

            <div>
              <n-text strong style="display:block;margin-bottom:6px">诊断</n-text>
              <n-text style="font-size:13px;line-height:1.7">{{ tensionResult.diagnosis }}</n-text>
            </div>

            <div v-if="tensionResult.missing_elements.length">
              <n-text strong style="display:block;margin-bottom:6px">缺失元素</n-text>
              <n-space wrap :size="6">
                <n-tag v-for="el in tensionResult.missing_elements" :key="el" type="warning" size="small" round>
                  {{ el }}
                </n-tag>
              </n-space>
            </div>

            <div v-if="tensionResult.suggestions.length">
              <n-text strong style="display:block;margin-bottom:6px">突破建议</n-text>
              <n-space vertical :size="6">
                <n-card
                  v-for="(s, i) in tensionResult.suggestions"
                  :key="i"
                  size="small"
                  :bordered="true"
                  style="font-size:13px;line-height:1.7"
                >
                  {{ i + 1 }}. {{ s }}
                </n-card>
              </n-space>
            </div>
          </n-space>
        </template>
      </n-space>
      <template #action>
        <n-space justify="end">
          <n-button @click="showTensionModal = false">关闭</n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- AI 续规划弹窗 -->
    <n-modal
      v-model:show="showContinueModal"
      preset="card"
      title="🎭 AI 续规划"
      style="width: min(520px, 96vw)"
      :segmented="{ content: true, footer: 'soft' }"
    >
      <template #header-extra>
        <n-text depth="3" style="font-size:12px">检测当前幕进度，决定是否需要创建下一幕</n-text>
      </template>

      <n-spin :show="continueLoading" description="正在分析幕结构…">
        <n-space v-if="continueResult" vertical :size="16">
          <!-- 幕进度 -->
          <n-card size="small" :bordered="false" style="background: var(--n-color-modal)">
            <n-space vertical :size="10">
              <n-space align="center" :size="8">
                <n-text strong>当前幕：</n-text>
                <n-text>{{ continueResult.current_act_title || continueResult.current_act_id || '未知' }}</n-text>
              </n-space>
              <n-space align="center" :size="8" v-if="continueResult.completed_chapters != null">
                <n-text depth="3">幕内进度：</n-text>
                <n-text>{{ continueResult.completed_chapters }} / {{ continueResult.total_chapters ?? '?' }} 章</n-text>
              </n-space>
              <n-text v-if="continueResult.progress_message" depth="3">{{ continueResult.progress_message }}</n-text>
              <n-text v-if="continueResult.message" depth="3">{{ continueResult.message }}</n-text>
            </n-space>
          </n-card>

          <!-- 状态徽章 -->
          <n-space :size="10">
            <n-tag :type="continueResult.is_act_complete ? 'success' : 'info'" round>
              {{ continueResult.is_act_complete ? '✅ 本幕已写完' : '⏳ 本幕尚未完成' }}
            </n-tag>
            <n-tag v-if="continueResult.needs_next_act" type="warning" round>
              🎬 建议创建下一幕
            </n-tag>
          </n-space>

          <!-- 创建下一幕 -->
          <n-alert v-if="continueResult.needs_next_act && continueResult.current_act_id" type="warning" :show-icon="true">
            AI 判断当前幕已完成，建议创建下一幕以继续故事规划。
            <template #action>
              <n-button
                type="warning"
                size="small"
                :loading="creatingNextAct"
                @click="handleCreateNextAct"
              >
                创建下一幕
              </n-button>
            </template>
          </n-alert>

          <n-alert v-else-if="!continueResult.needs_next_act" type="success" :show-icon="true">
            当前幕还有规划章节未写完，继续创作当前幕即可。
          </n-alert>
        </n-space>
        <n-empty v-else-if="!continueLoading" description="分析结果为空" />
      </n-spin>

      <template #action>
        <n-space justify="end">
          <n-button @click="showContinueModal = false">关闭</n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- 完整工作流撰稿弹窗（场景分析 + 流式 + 一致性报告） -->
    <GenerateChapterWorkflowModal
      v-model:show="showWorkflowModal"
      :slug="slug"
      :chapters="chapters"
      :default-chapter-id="currentChapterId"
      @saved="emit('chapterUpdated')"
      @plan-act="(_actId, _actTitle) => emit('setRightPanel', 'bible')"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useMessage } from 'naive-ui'
import {
  workflowApi,
  consumeGenerateChapterStream,
  consumeHostedWriteStream,
  analyzeScene,
  retrieveContext,
} from '../../api/workflow'
import type { ContextPreviewResult } from '../../api/workflow'
import { chapterApi } from '../../api/chapter'
import { tensionApi } from '../../api/tools'
import type { TensionDiagnosis } from '../../api/tools'
import { planningApi } from '../../api/planning'
import type { ContinuePlanResult } from '../../api/planning'
import GenerateChapterWorkflowModal from './GenerateChapterWorkflowModal.vue'

interface Chapter {
  id: number
  number: number
  title: string
  word_count: number
  content?: string
}

interface WorkAreaProps {
  slug: string
  bookTitle?: string
  chapters: Chapter[]
  currentChapterId?: number | null
  chapterContent?: string
  chapterLoading?: boolean
}

const props = withDefaults(defineProps<WorkAreaProps>(), {
  chapters: () => [],
  currentChapterId: null,
  chapterContent: '',
  chapterLoading: false
})

const emit = defineEmits<{
  setRightPanel: [panel: string]
  startWrite: []
  chapterUpdated: []
}>()

const message = useMessage()

const showHostedModal = ref(false)
const showWorkflowModal = ref(false)
const showGenerateModal = ref(false)
const generateOutline = ref('')
const generatedContent = ref('')

const openHostedWriteModal = () => {
  showHostedModal.value = true
}

// 章节编辑
const chapterContent = ref('')
const originalContent = ref('')
const loading = computed(() => props.chapterLoading)
const saving = ref(false)
const reviewing = ref(false)
const reviewResult = ref<{ score: number; suggestions: string[] } | null>(null)

// 续规划提示：保存后检查幕是否完成
const continuePlanBadge = ref<{ message: string; suggestCreate: boolean; actId: string } | null>(null)

// Scene Director 开关
const useSceneDirector = ref(false)
const analyzingScene = ref(false)
const sceneDirectorError = ref('')

// 张力弹弓
const showTensionModal = ref(false)
const tensionLoading = ref(false)
const tensionStuckReason = ref('')
const tensionResult = ref<TensionDiagnosis | null>(null)

// AI 续规划
const showContinueModal = ref(false)
const continueLoading = ref(false)
const continueResult = ref<ContinuePlanResult | null>(null)
const creatingNextAct = ref(false)

const handleContinuePlanning = async () => {
  if (!currentChapter.value) return
  continueLoading.value = true
  continueResult.value = null
  showContinueModal.value = true
  try {
    continueResult.value = await planningApi.continuePlanning(props.slug, {
      current_chapter: currentChapter.value.number,
    })
  } catch {
    message.error('续规划失败，请确认 AI 密钥已配置')
    showContinueModal.value = false
  } finally {
    continueLoading.value = false
  }
}

const handleCreateNextAct = async () => {
  if (!continueResult.value?.current_act_id) return
  creatingNextAct.value = true
  try {
    await planningApi.createNextAct(continueResult.value.current_act_id)
    message.success('下一幕已创建，请刷新结构树')
    showContinueModal.value = false
  } catch {
    message.error('创建下一幕失败')
  } finally {
    creatingNextAct.value = false
  }
}

const openTensionModal = () => {
  tensionResult.value = null
  tensionStuckReason.value = ''
  showTensionModal.value = true
}

const runTensionSlingshot = async () => {
  if (!currentChapter.value) return
  tensionLoading.value = true
  try {
    tensionResult.value = await tensionApi.slingshot(props.slug, {
      novel_id: props.slug,
      chapter_number: currentChapter.value.number,
      stuck_reason: tensionStuckReason.value || undefined,
    })
  } catch {
    message.error('分析失败，请稍后重试')
  } finally {
    tensionLoading.value = false
  }
}

// 上下文预览
const contextPreview = ref<ContextPreviewResult | null>(null)
const loadingContext = ref(false)

const previewContext = async () => {
  const chNum = currentChapter.value?.number
  if (!chNum) return
  loadingContext.value = true
  try {
    contextPreview.value = await retrieveContext(
      props.slug,
      chNum,
      generateOutline.value || `第${chNum}章：承接前情，推进主线`,
    )
  } catch {
    contextPreview.value = null
  } finally {
    loadingContext.value = false
  }
}

// AbortController：点「停止」时真正取消后端 SSE 流
const generateAbortCtrl = ref<AbortController | null>(null)
const hostedAbortCtrl = ref<AbortController | null>(null)

// 正在生成的章节 ID（null = 不在生成中）
// 与 currentChapterId 解耦：用户可以切换章节，生成仍在后台继续
const generatingChapterId = ref<number | null>(null)

/** 当前视图是否正处于生成中（需要显示生成状态 UI） */
const generating = computed(() =>
  generatingChapterId.value !== null &&
  generatingChapterId.value === props.currentChapterId
)

const currentChapter = computed(() => {
  if (!props.currentChapterId) return null
  return props.chapters.find(ch => ch.id === props.currentChapterId) || null
})

const hasChanges = computed(() => {
  return chapterContent.value !== originalContent.value
})

const wordCount = computed(() => {
  return chapterContent.value.length
})

// 监听传入的章节内容变化
watch(() => props.chapterContent, (newContent) => {
  chapterContent.value = newContent
  originalContent.value = newContent
}, { immediate: true })

// 切换回正在生成的章节时，自动打开生成弹窗（让用户看到进度）
watch(() => props.currentChapterId, (id) => {
  if (id !== null && id === generatingChapterId.value) {
    showGenerateModal.value = true
  }
  reviewResult.value = null
})

const handleContentChange = () => {
  // 内容变化
}

const handleSave = async () => {
  if (!currentChapter.value) return

  saving.value = true
  continuePlanBadge.value = null
  try {
    await chapterApi.updateChapter(props.slug, currentChapter.value.id, { content: chapterContent.value })
    originalContent.value = chapterContent.value
    message.success('保存成功')
    emit('chapterUpdated')
    // 后台检查幕进度（不阻塞保存流程）
    _checkActCompletionAfterSave(currentChapter.value.number)
  } catch (error) {
    message.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function _checkActCompletionAfterSave(chapterNumber: number) {
  try {
    const r = await planningApi.continuePlanning(props.slug, { current_chapter: chapterNumber })
    if (r.act_completed && r.suggest_create_next) {
      continuePlanBadge.value = {
        message: r.message || '本幕已完成，建议创建下一幕',
        suggestCreate: true,
        actId: r.current_act_id ?? '',
      }
    }
  } catch {
    // 失败静默
  }
}

const handleReload = async () => {
  if (!currentChapter.value) return
  try {
    const fresh = await chapterApi.getChapter(props.slug, currentChapter.value.number)
    chapterContent.value = fresh.content ?? ''
    originalContent.value = fresh.content ?? ''
    message.success('已重新加载')
  } catch {
    message.error('加载失败，请稍后重试')
  }
}

const handleGenerateChapter = async () => {
  if (!currentChapter.value) return

  generateOutline.value = `第${currentChapter.value.number}章：${currentChapter.value.title || ''}

承接前情，推进主线与人物节拍；保持人设与叙事节奏一致。`
  generatedContent.value = ''
  contextPreview.value = null
  showGenerateModal.value = true
}

const handleStartGenerate = async () => {
  if (!currentChapter.value) return

  const targetChapterId = currentChapter.value.id
  const targetChapterNumber = currentChapter.value.number
  generatingChapterId.value = targetChapterId
  generatedContent.value = ''
  sceneDirectorError.value = ''

  const ctrl = new AbortController()
  generateAbortCtrl.value = ctrl

  // 可选：Scene Director 分析（失败不阻断生成）
  let sceneDirectorResult: Record<string, unknown> | undefined
  if (useSceneDirector.value) {
    analyzingScene.value = true
    try {
      const outline = generateOutline.value || `第${targetChapterNumber}章：承接前情，推进主线`
      const analysis = await analyzeScene(props.slug, targetChapterNumber, outline)
      sceneDirectorResult = analysis as Record<string, unknown>
    } catch (e: unknown) {
      sceneDirectorError.value = e instanceof Error ? e.message : '分析失败'
    } finally {
      analyzingScene.value = false
    }
  }

  try {
    await consumeGenerateChapterStream(
      props.slug,
      {
        chapter_number: targetChapterNumber,
        outline: generateOutline.value || `第${targetChapterNumber}章：承接前情，推进主线`,
        scene_director_result: sceneDirectorResult,
      },
      {
        signal: ctrl.signal,
        onEvent: (event) => {
          if (event.type === 'phase') {
            generatedContent.value += `[阶段: ${event.phase}]\n`
          } else if (event.type === 'chunk') {
            generatedContent.value += event.text
          } else if (event.type === 'done') {
            generatedContent.value = event.content
            // 若用户当前就在这一章，弹窗已在显示；若不在则发消息通知
            if (props.currentChapterId === targetChapterId) {
              message.success('章节生成完成')
            } else {
              message.success(`第 ${targetChapterNumber} 章生成完成，切回该章可查看`)
            }
          } else if (event.type === 'error') {
            generatedContent.value += `\n\n[错误] ${event.message}\n`
            if (!ctrl.signal.aborted) message.error(`生成失败: ${event.message}`)
          }
        },
        onError: (err) => {
          if (!ctrl.signal.aborted) message.error(`生成失败: ${err}`)
        }
      }
    )
  } catch (error) {
    if (!ctrl.signal.aborted) message.error('生成失败')
  } finally {
    generatingChapterId.value = null
    generateAbortCtrl.value = null
  }
}

const handleSaveGenerated = async () => {
  if (!currentChapter.value || !generatedContent.value) return

  saving.value = true
  try {
    await chapterApi.updateChapter(props.slug, currentChapter.value.id, { content: generatedContent.value })
    chapterContent.value = generatedContent.value
    originalContent.value = generatedContent.value
    message.success('保存成功')
    emit('chapterUpdated')
    showGenerateModal.value = false
  } catch (error) {
    message.error('保存失败')
  } finally {
    saving.value = false
  }
}

const stopGenerate = () => {
  generateAbortCtrl.value?.abort()
  generateAbortCtrl.value = null
  generatingChapterId.value = null
  message.info('已停止生成')
}

const handleReviewChapter = async () => {
  if (!currentChapter.value) return

  reviewing.value = true
  try {
    const result = await workflowApi.reviewChapter(props.slug, currentChapter.value.id)
    reviewResult.value = {
      score: result.score,
      suggestions: result.suggestions || []
    }
    message.success(`审稿完成，评分: ${result.score}/100`)
  } catch (error: any) {
    if (error.response?.status === 501) {
      message.warning('审稿功能开发中')
    } else {
      message.error('审稿失败')
    }
  } finally {
    reviewing.value = false
  }
}

// 托管连写
const hostedFrom = ref(1)
const hostedTo = ref(5)
const hostedAutoSave = ref(true)
const hostedAutoOutline = ref(true)
const hostedRunning = ref(false)
const hostedLog = ref('')

const handleStartHosted = async () => {
  hostedRunning.value = true
  hostedLog.value = ''
  const ctrl = new AbortController()
  hostedAbortCtrl.value = ctrl

  try {
    await consumeHostedWriteStream(
      props.slug,
      {
        from_chapter: hostedFrom.value,
        to_chapter: hostedTo.value,
        auto_save: hostedAutoSave.value,
        auto_outline: hostedAutoOutline.value
      },
      {
        signal: ctrl.signal,
        onEvent: (event) => {
          if (event.type === 'session') {
            hostedLog.value += `[会话开始] 章节 ${event.from_chapter}-${event.to_chapter}，共 ${event.total} 章\n\n`
          } else if (event.type === 'chapter_start') {
            hostedLog.value += `\n[章节 ${event.chapter}] 开始生成 (${event.index}/${event.total})\n`
          } else if (event.type === 'outline') {
            hostedLog.value += `[大纲] ${event.text}\n\n`
          } else if (event.type === 'phase') {
            hostedLog.value += `[阶段: ${event.phase}]\n`
          } else if (event.type === 'done') {
            hostedLog.value += `[完成] 章节 ${event.chapter} 生成完成，${typeof event.content === 'string' ? event.content.length : 0} 字符\n`
          } else if (event.type === 'saved') {
            if (event.ok) {
              hostedLog.value += `[保存] 章节 ${event.chapter} 已保存${event.created ? '（新建）' : ''}\n`
            } else {
              hostedLog.value += `[保存失败] 章节 ${event.chapter}: ${event.message}\n`
            }
          } else if (event.type === 'session_done') {
            hostedLog.value += `\n[会话完成] 所有章节生成完毕\n`
            message.success('托管连写完成')
            emit('chapterUpdated')
          } else if (event.type === 'error') {
            hostedLog.value += `\n[错误] ${event.message}\n`
            if (!ctrl.signal.aborted) message.error(`生成失败: ${event.message}`)
          }
        },
        onError: (err) => {
          hostedLog.value += `\n[连接错误] ${err}\n`
          if (!ctrl.signal.aborted) message.error(`托管连写失败: ${err}`)
        }
      }
    )
  } catch (error) {
    if (!ctrl.signal.aborted) message.error('托管连写失败')
  } finally {
    hostedRunning.value = false
    hostedAbortCtrl.value = null
  }
}

const stopHosted = () => {
  hostedAbortCtrl.value?.abort()
  hostedAbortCtrl.value = null
  hostedRunning.value = false
  message.info('已停止托管连写')
}
</script>

<style scoped>
.work-area {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--app-surface);
}

.work-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--aitext-split-border);
}

.work-title-wrap {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.work-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.work-sub {
  font-size: 13px;
}

.work-main {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 16px 20px 20px;
  overflow: hidden;
}

.work-empty {
  margin-top: 80px;
}

.write-modal-body {
  padding-right: 6px;
}

.output-area {
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  color: var(--text-color-2);
}

.write-modal-body :deep(.n-card) {
  background: var(--card-color);
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.write-modal-body :deep(.n-card__header) {
  padding: 12px 16px;
  font-weight: 600;
  font-size: 14px;
}

.write-modal-body :deep(.n-card__content) {
  padding: 16px;
}

.write-modal-body :deep(.n-form-item) {
  margin-bottom: 0;
}

.chapter-editor {
  display: flex;
  flex-direction: column;
  gap: 16px;
  flex: 1;
  min-height: 0;
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border-color);
}

.editor-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.editor-title h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.editor-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.editor-body :deep(.n-input) {
  height: 100%;
}

.editor-body :deep(.n-input__textarea-el) {
  font-family: var(--font-mono);
  font-size: 14px;
  line-height: 1.8;
}

.editor-footer {
  padding-top: 12px;
  border-top: 1px solid var(--border-color);
}
</style>
