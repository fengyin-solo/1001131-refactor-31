<template>
  <section class="page" data-module="gate">
    <header class="page-head">
      <div>
        <h2>闸口通行管理</h2>
        <p class="page-desc">维护通行记录，围绕通行编号、车牌号码、关联箱号、进出方向做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记通行记录</button>
        <button class="btn" type="button" @click="exportRows">导出闸口通行清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>放行结果</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td>
            <button class="link verdict-link" type="button" @click="openDetail(row)">
              {{ row['放行结果'] ?? '—' }}
            </button>
          </td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 2" class="empty-state">暂无闸口通行数据，可先登记通行记录</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条闸口通行记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="createVisible" class="modal-mask" @click.self="closeCreate">
      <form class="modal-card" @submit.prevent="submitCreate">
        <h3 class="modal-title">登记通行记录</h3>
        <label v-for="field in createFields" :key="field" class="modal-field">
          <span>{{ field }}<em v-if="requiredFields.includes(field)">*</em></span>
          <input v-model="createForm[field]" :placeholder="`请输入${field}`" />
        </label>
        <p class="modal-hint">放行结果以车牌号码与关联箱号为唯一判据，登记、放行确认、复核结论一致。</p>
        <p v-if="createMessage" :class="createOk ? 'ok-text' : 'error-text'">{{ createMessage }}</p>
        <div class="modal-actions">
          <button class="btn" type="button" @click="closeCreate">取消</button>
          <button class="btn primary" type="submit">提交登记</button>
        </div>
      </form>
    </div>

    <div v-if="detail" class="modal-mask" @click.self="detail = null">
      <div class="modal-card">
        <h3 class="modal-title">通行记录详情 · {{ detail['通行编号'] }}</h3>
        <dl class="detail-grid">
          <template v-for="column in columns" :key="column">
            <dt>{{ column }}</dt>
            <dd>{{ detail[column] ?? '—' }}</dd>
          </template>
          <dt>放行结果</dt>
          <dd>{{ detail['放行结果'] }}</dd>
          <dt>放行说明</dt>
          <dd>{{ detail['放行说明'] }}</dd>
          <dt v-if="detail['复核结果']">复核结果</dt>
          <dd v-if="detail['复核结果']">{{ detail['复核结果'] }}</dd>
        </dl>
        <div class="modal-actions">
          <button class="btn primary" type="button" @click="detail = null">关闭</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

interface ActionResponse {
  ok: boolean
  message: string
  entry?: Row
}

const ENDPOINT = '/api/gate'
const columns = ["通行编号", "车牌号码", "关联箱号", "进出方向", "通行时间", "道口编号", "值守人员", "通行状态"]
const actions = ["确认放行", "拦截车辆", "复核通行"]
const statuses = ["待放行", "已放行", "已拦截", "已复核"]
const stats = [{"label": "今日进闸车次", "value": 0}, {"label": "今日出闸车次", "value": 0}, {"label": "拦截车次", "value": 0}]

const createFields = ["通行编号", "车牌号码", "关联箱号", "进出方向", "通行时间", "道口编号", "值守人员"]
const requiredFields = ["通行编号", "车牌号码", "关联箱号"]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

const createVisible = ref(false)
const createForm = reactive<Record<string, string>>({})
const createMessage = ref('')
const createOk = ref(false)

const detail = ref<Row | null>(null)

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  for (const field of createFields) {
    createForm[field] = ''
  }
  createMessage.value = ''
  createOk.value = false
  createVisible.value = true
}

function closeCreate() {
  createVisible.value = false
}

async function submitCreate() {
  createMessage.value = ''
  const values: Record<string, string> = {}
  for (const field of createFields) {
    values[field] = createForm[field]?.trim() ?? ''
  }
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values }),
    })
    const payload = (await response.json()) as ActionResponse
    if (!payload.ok) {
      createOk.value = false
      createMessage.value = payload.message
      return
    }
    createOk.value = true
    createMessage.value = `${payload.message}：${payload.entry?.['放行结果'] ?? ''}`
    createVisible.value = false
    await reload()
  } catch (error) {
    createOk.value = false
    createMessage.value = error instanceof Error ? error.message : '通行记录登记失败'
  }
}

async function openDetail(row: Row) {
  detail.value = row
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) {
      throw new Error('通行记录详情读取失败')
    }
    detail.value = (await response.json()) as Row
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '通行记录详情读取失败'
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = (await response.json()) as ActionResponse
    if (!payload.ok) {
      errorMessage.value = payload.message
      return
    }
    errorMessage.value = payload.message
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '闸口通行操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('通行记录列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '闸口通行列表读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.verdict-link {
  white-space: nowrap;
}
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
}
.modal-card {
  width: 480px;
  max-height: 80vh;
  overflow-y: auto;
  background: #fff;
  border-radius: 8px;
  padding: 18px 20px;
  border: 1px solid var(--border);
}
.modal-title {
  margin: 0 0 14px;
  font-size: 15px;
}
.modal-field {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  font-size: 13px;
}
.modal-field span {
  width: 84px;
  color: var(--muted);
  flex-shrink: 0;
}
.modal-field em {
  color: #b42318;
  font-style: normal;
  margin-left: 2px;
}
.modal-field input {
  flex: 1;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
}
.modal-hint {
  font-size: 12px;
  color: var(--muted);
  margin: 4px 0 10px;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 12px;
}
.detail-grid {
  display: grid;
  grid-template-columns: 96px 1fr;
  gap: 6px 12px;
  margin: 0;
  font-size: 13px;
}
.detail-grid dt {
  color: var(--muted);
}
.detail-grid dd {
  margin: 0;
}
.ok-text {
  color: #067647;
}
</style>
