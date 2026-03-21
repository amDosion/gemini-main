#!/usr/bin/env node

/**
 * Agent Workflow E2E Script
 *
 * 覆盖链路：
 * 1) 认证（token / login / register）
 * 2) Agent CRUD
 * 3) Workflow Template CRUD
 * 4) Workflow 历史与加载
 *
 * 使用示例：
 *   E2E_ACCESS_TOKEN=xxx node scripts/e2e/agent_workflow_e2e.mjs
 *   E2E_EMAIL=a@b.com E2E_PASSWORD=12345678 node scripts/e2e/agent_workflow_e2e.mjs
 */

const args = new Set(process.argv.slice(2));
if (args.has('--help') || args.has('-h')) {
  console.log(`
Agent Workflow E2E

Env:
  E2E_BASE_URL            API base URL (default: http://127.0.0.1:21574)
  E2E_ACCESS_TOKEN        Optional access token
  E2E_EMAIL               Optional login/register email
  E2E_PASSWORD            Optional login/register password (>=8)
  E2E_NAME                Optional register display name

Examples:
  E2E_ACCESS_TOKEN=xxx node scripts/e2e/agent_workflow_e2e.mjs
  E2E_EMAIL=u@e2e.local E2E_PASSWORD=12345678 node scripts/e2e/agent_workflow_e2e.mjs
`);
  process.exit(0);
}

const BASE_URL = process.env.E2E_BASE_URL || 'http://127.0.0.1:21574';
const suffix = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;

const state = {
  token: process.env.E2E_ACCESS_TOKEN || '',
  createdAgentId: null,
  createdTemplateId: null,
  createdExecutionId: null,
};

function info(message) {
  console.log(`ℹ️  ${message}`);
}

function success(message) {
  console.log(`✅ ${message}`);
}

function fail(message) {
  throw new Error(message);
}

function assert(condition, message) {
  if (!condition) {
    fail(message);
  }
}

function joinUrl(path) {
  if (path.startsWith('http://') || path.startsWith('https://')) return path;
  const base = BASE_URL.endsWith('/') ? BASE_URL.slice(0, -1) : BASE_URL;
  return `${base}${path.startsWith('/') ? path : `/${path}`}`;
}

async function api(path, options = {}) {
  const {
    method = 'GET',
    body = undefined,
    auth = true,
    expectedStatus = null,
  } = options;

  const headers = { Accept: 'application/json' };
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
  }
  if (auth && state.token) {
    headers.Authorization = `Bearer ${state.token}`;
  }

  const response = await fetch(joinUrl(path), {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  const raw = await response.text();
  let data = null;
  try {
    data = raw ? JSON.parse(raw) : null;
  } catch {
    data = raw || null;
  }

  if (expectedStatus !== null && response.status !== expectedStatus) {
    fail(`[${method} ${path}] expected ${expectedStatus}, got ${response.status}: ${JSON.stringify(data)}`);
  }

  return { response, data };
}

async function resolveToken() {
  if (state.token) {
    success('Using E2E_ACCESS_TOKEN');
    return;
  }

  const envEmail = process.env.E2E_EMAIL;
  const envPassword = process.env.E2E_PASSWORD;
  const email = envEmail || `agent-e2e-${suffix}@example.com`;
  const password = envPassword || 'e2e-password-123';
  const name = process.env.E2E_NAME || 'Agent E2E User';

  info(`No token provided, trying login/register with ${email}`);

  const login = await api('/api/auth/login', {
    method: 'POST',
    auth: false,
    body: { email, password },
  });

  if (login.response.ok && login.data?.accessToken) {
    state.token = login.data.accessToken;
    success('Login success');
    return;
  }

  const config = await api('/api/auth/config', { auth: false });
  const allowRegistration = Boolean(config.data?.allowRegistration);
  if (!allowRegistration) {
    fail('Auth failed and registration is disabled. Please provide E2E_ACCESS_TOKEN or valid E2E_EMAIL/E2E_PASSWORD.');
  }

  const register = await api('/api/auth/register', {
    method: 'POST',
    auth: false,
    body: {
      email,
      password,
      confirmPassword: password,
      name,
    },
  });

  if (!register.response.ok || !register.data?.accessToken) {
    fail(`Register failed: ${JSON.stringify(register.data)}`);
  }

  state.token = register.data.accessToken;
  success('Register success');
}

async function testAgentCrud() {
  info('Running Agent CRUD E2E...');
  const agentName = `E2E Agent ${suffix}`;
  const encodedAgentName = encodeURIComponent(agentName);

  const create = await api('/api/agents', {
    method: 'POST',
    body: {
      name: agentName,
      description: 'E2E created agent',
      providerId: 'e2e-provider',
      modelId: 'e2e-model',
      systemPrompt: 'You are e2e test agent',
      temperature: 0.2,
      maxTokens: 256,
      icon: '🧪',
      color: '#22c55e',
    },
  });
  assert(create.response.ok, `Create agent failed: ${JSON.stringify(create.data)}`);
  assert(create.data?.id, 'Create agent response missing id');
  state.createdAgentId = create.data.id;
  success(`Agent created: ${state.createdAgentId}`);

  const searchActive = await api(`/api/agents?search=${encodedAgentName}`);
  assert(searchActive.response.ok, `Search agents failed: ${JSON.stringify(searchActive.data)}`);
  assert(typeof searchActive.data?.activeCount === 'number', 'Agent list missing activeCount');
  assert(typeof searchActive.data?.inactiveCount === 'number', 'Agent list missing inactiveCount');
  const searchedActive = Array.isArray(searchActive.data?.agents)
    ? searchActive.data.agents.some((item) => item.id === state.createdAgentId)
    : false;
  assert(searchedActive, 'Created agent not found by search');
  success('Agent search and counters verified');

  const duplicate = await api('/api/agents', {
    method: 'POST',
    body: {
      name: agentName,
      description: 'E2E duplicate agent',
      providerId: 'e2e-provider',
      modelId: 'e2e-model',
    },
  });
  assert(duplicate.response.status === 409, 'Duplicate agent name should return 409');
  success('Agent duplicate name validation verified');

  const detail = await api(`/api/agents/${state.createdAgentId}`);
  assert(detail.response.ok, `Get agent detail failed: ${JSON.stringify(detail.data)}`);
  assert(detail.data?.id === state.createdAgentId, 'Agent detail returned wrong id');
  success('Agent detail fetched');

  const list1 = await api('/api/agents');
  assert(list1.response.ok, 'List agents failed');
  const foundCreated = Array.isArray(list1.data?.agents)
    && list1.data.agents.some((item) => item.id === state.createdAgentId);
  assert(foundCreated, 'Created agent not found in list');
  success('Agent listed');

  const update = await api(`/api/agents/${state.createdAgentId}`, {
    method: 'PUT',
    body: {
      description: 'E2E updated description',
      temperature: 0.4,
    },
  });
  assert(update.response.ok, `Update agent failed: ${JSON.stringify(update.data)}`);
  assert(update.data?.description === 'E2E updated description', 'Agent description was not updated');
  success('Agent updated');

  const remove = await api(`/api/agents/${state.createdAgentId}`, {
    method: 'DELETE',
  });
  assert(remove.response.ok, `Delete agent failed: ${JSON.stringify(remove.data)}`);
  success('Agent soft deleted');

  const list2 = await api('/api/agents');
  assert(list2.response.ok, 'List agents failed after delete');
  const stillExists = Array.isArray(list2.data?.agents)
    && list2.data.agents.some((item) => item.id === state.createdAgentId);
  assert(!stillExists, 'Deleted agent still appears in active list');
  success('Agent active list filter verified');

  const listWithInactive = await api('/api/agents?include_inactive=true');
  assert(listWithInactive.response.ok, 'List agents with include_inactive failed');
  const inactiveAgent = Array.isArray(listWithInactive.data?.agents)
    ? listWithInactive.data.agents.find((item) => item.id === state.createdAgentId)
    : null;
  assert(Boolean(inactiveAgent), 'Inactive agent not found when include_inactive=true');
  assert(inactiveAgent?.status === 'inactive', 'Inactive agent should have status=inactive');
  success('Agent inactive list verified');

  const searchInactive = await api(`/api/agents?include_inactive=true&search=${encodedAgentName}`);
  assert(searchInactive.response.ok, 'Search inactive agents failed');
  const searchedInactive = Array.isArray(searchInactive.data?.agents)
    ? searchInactive.data.agents.find((item) => item.id === state.createdAgentId)
    : null;
  assert(Boolean(searchedInactive), 'Inactive agent not found by search');
  assert(searchedInactive?.status === 'inactive', 'Searched inactive agent should have status=inactive');
  success('Agent inactive search verified');

  const restore = await api(`/api/agents/${state.createdAgentId}/restore`, {
    method: 'POST',
    body: {},
  });
  assert(restore.response.ok, `Restore agent failed: ${JSON.stringify(restore.data)}`);
  success('Agent restore verified');

  const searchRestored = await api(`/api/agents?search=${encodedAgentName}`);
  assert(searchRestored.response.ok, 'Search restored agents failed');
  const restoredAgent = Array.isArray(searchRestored.data?.agents)
    ? searchRestored.data.agents.find((item) => item.id === state.createdAgentId)
    : null;
  assert(Boolean(restoredAgent), 'Restored agent not found in active search list');
  assert(restoredAgent?.status === 'active', 'Restored agent should have status=active');
  success('Agent restore search verified');

  const hardDelete = await api(`/api/agents/${state.createdAgentId}?hard_delete=true`, {
    method: 'DELETE',
  });
  assert(hardDelete.response.ok, `Hard delete agent failed: ${JSON.stringify(hardDelete.data)}`);
  success('Agent hard delete verified');

  const searchAfterHardDelete = await api(`/api/agents?include_inactive=true&search=${encodedAgentName}`);
  assert(searchAfterHardDelete.response.ok, 'Search after hard delete failed');
  const hardDeletedStillListed = Array.isArray(searchAfterHardDelete.data?.agents)
    && searchAfterHardDelete.data.agents.some((item) => item.id === state.createdAgentId);
  assert(!hardDeletedStillListed, 'Hard deleted agent should not appear in list');
  success('Agent hard delete list removal verified');

  const missing = await api(`/api/agents/${state.createdAgentId}`);
  assert(missing.response.status === 404, 'Hard deleted agent should return 404 on detail');
  success('Agent hard delete result verified');
  state.createdAgentId = null;
}

async function testTemplateCrud() {
  info('Running Workflow Template CRUD E2E...');

  const templateName = `E2E Template ${suffix}`;
  const payload = {
    name: templateName,
    description: 'E2E template for workflow',
    category: 'E2E',
    workflowType: 'graph',
    tags: ['e2e', 'agent'],
    config: {
      schemaVersion: 2,
      nodes: [
        {
          id: 'start-node',
          type: 'start',
          position: { x: 80, y: 120 },
          data: { type: 'start', label: '开始', description: 'start' },
        },
        {
          id: 'agent-node',
          type: 'agent',
          position: { x: 300, y: 120 },
          data: {
            type: 'agent',
            label: 'Agent',
            description: 'agent',
            instructions: 'return hello',
            inputMapping: '',
          },
        },
        {
          id: 'end-node',
          type: 'end',
          position: { x: 520, y: 120 },
          data: { type: 'end', label: '结束', description: 'end' },
        },
      ],
      edges: [
        { id: 'edge-1', source: 'start-node', target: 'agent-node' },
        { id: 'edge-2', source: 'agent-node', target: 'end-node' },
      ],
    },
    isPublic: false,
  };

  const create = await api('/api/workflows/templates', {
    method: 'POST',
    body: payload,
  });
  assert(create.response.ok, `Create template failed: ${JSON.stringify(create.data)}`);
  assert(create.data?.id, 'Create template response missing id');
  state.createdTemplateId = create.data.id;
  success(`Template created: ${state.createdTemplateId}`);

  const list = await api('/api/workflows/templates');
  assert(list.response.ok, 'List templates failed');
  const found = Array.isArray(list.data?.templates)
    && list.data.templates.some((item) => item.id === state.createdTemplateId);
  assert(found, 'Created template not found in list');
  success('Template listed');

  const getOne = await api(`/api/workflows/templates/${state.createdTemplateId}`);
  assert(getOne.response.ok, 'Get template by id failed');
  assert(getOne.data?.id === state.createdTemplateId, 'Get template returned wrong id');
  success('Template fetched by id');

  const update = await api(`/api/workflows/templates/${state.createdTemplateId}`, {
    method: 'PUT',
    body: {
      name: `${templateName} Updated`,
      tags: ['e2e', 'updated'],
    },
  });
  assert(update.response.ok, `Update template failed: ${JSON.stringify(update.data)}`);
  assert(update.data?.name === `${templateName} Updated`, 'Template name was not updated');
  success('Template updated');

  const remove = await api(`/api/workflows/templates/${state.createdTemplateId}`, {
    method: 'DELETE',
  });
  assert(remove.response.ok, `Delete template failed: ${JSON.stringify(remove.data)}`);
  success('Template deleted');

  const missing = await api(`/api/workflows/templates/${state.createdTemplateId}`);
  assert(missing.response.status === 404, 'Deleted template should return 404 on get');
  success('Template delete verified');
}

async function testStarterTemplates() {
  info('Running Starter Template E2E...');

  const seed = await api('/api/workflows/templates/seed', {
    method: 'POST',
    body: {},
  });
  assert(seed.response.ok, `Seed starter templates failed: ${JSON.stringify(seed.data)}`);
  success(`Starter templates seeded: ${seed.data?.createdCount ?? seed.data?.created_count ?? 0}`);

  const list = await api('/api/workflows/templates');
  assert(list.response.ok, 'List templates failed for starter check');

  const templates = Array.isArray(list.data?.templates) ? list.data.templates : [];
  const starterNames = new Set(templates.map((item) => item?.name));
  assert(starterNames.has('工作流 · 图片生成'), 'Missing starter template: 工作流 · 图片生成');
  assert(starterNames.has('工作流 · 图片编辑'), 'Missing starter template: 工作流 · 图片编辑');
  assert(starterNames.has('工作流 · 表格分析'), 'Missing starter template: 工作流 · 表格分析');
  success('Starter templates verified');
}

async function testWorkflowHistory() {
  info('Running Workflow History E2E...');

  const execute = await api('/api/workflows/execute', {
    method: 'POST',
    body: {
      nodes: [
        {
          id: 'start-node',
          type: 'start',
          position: { x: 100, y: 160 },
          data: { type: 'start', label: '开始', description: 'start' },
        },
        {
          id: 'tool-node',
          type: 'tool',
          position: { x: 320, y: 160 },
          data: {
            type: 'tool',
            label: '表格分析',
            description: 'tool',
            toolName: 'table_analyze',
            toolArgsTemplate: '{"table":"a,b\\n1,2\\n3,4","analysisType":"quick"}',
          },
        },
        {
          id: 'end-node',
          type: 'end',
          position: { x: 540, y: 160 },
          data: { type: 'end', label: '结束', description: 'end' },
        },
      ],
      edges: [
        { id: 'edge-1', source: 'start-node', target: 'tool-node' },
        { id: 'edge-2', source: 'tool-node', target: 'end-node' },
      ],
      input: { task: 'E2E 历史记录测试' },
      meta: { title: `E2E History ${suffix}` },
      asyncMode: false,
    },
  });
  assert(execute.response.ok, `Execute workflow failed: ${JSON.stringify(execute.data)}`);
  const executionId = execute.data?.executionId || execute.data?.execution_id;
  assert(executionId, 'Execute workflow missing executionId');
  state.createdExecutionId = executionId;
  success(`Workflow executed: ${executionId}`);

  const list = await api('/api/workflows/history?limit=20');
  assert(list.response.ok, `List workflow history failed: ${JSON.stringify(list.data)}`);
  const executions = Array.isArray(list.data?.executions) ? list.data.executions : [];
  const matched = executions.find((item) => item?.id === executionId);
  assert(Boolean(matched), 'Created execution not found in history list');
  success('Workflow history listed');

  const detail = await api(`/api/workflows/history/${executionId}`);
  assert(detail.response.ok, `Get workflow history detail failed: ${JSON.stringify(detail.data)}`);
  assert(Array.isArray(detail.data?.workflow?.nodes), 'History detail missing workflow.nodes');
  assert(Array.isArray(detail.data?.workflow?.edges), 'History detail missing workflow.edges');
  success('Workflow history detail fetched');

  const remove = await api(`/api/workflows/history/${executionId}`, { method: 'DELETE' });
  assert(remove.response.ok, `Delete workflow history failed: ${JSON.stringify(remove.data)}`);
  state.createdExecutionId = null;
  success('Workflow history deleted');
}

async function testWorkflowResetApi() {
  info('Running Workflow Reset E2E...');

  const createTemplate = await api('/api/workflows/templates', {
    method: 'POST',
    body: {
      name: `E2E Reset Template ${suffix}`,
      description: 'temporary template before reset',
      category: 'E2E',
      workflowType: 'graph',
      config: {
        schemaVersion: 2,
        nodes: [
          { id: 'start-reset', type: 'start', position: { x: 100, y: 100 }, data: { type: 'start', label: '开始' } },
          { id: 'end-reset', type: 'end', position: { x: 320, y: 100 }, data: { type: 'end', label: '结束' } },
        ],
        edges: [{ id: 'edge-reset', source: 'start-reset', target: 'end-reset' }],
      },
      isPublic: false,
    },
  });
  assert(createTemplate.response.ok, `Create reset template failed: ${JSON.stringify(createTemplate.data)}`);
  state.createdTemplateId = createTemplate.data?.id || null;

  const execute = await api('/api/workflows/execute', {
    method: 'POST',
    body: {
      nodes: [
        { id: 'start-reset-run', type: 'start', position: { x: 100, y: 160 }, data: { type: 'start', label: '开始' } },
        { id: 'end-reset-run', type: 'end', position: { x: 360, y: 160 }, data: { type: 'end', label: '结束' } },
      ],
      edges: [{ id: 'edge-reset-run', source: 'start-reset-run', target: 'end-reset-run' }],
      input: { task: 'E2E workflow reset test' },
      asyncMode: false,
    },
  });
  assert(execute.response.ok, `Execute before reset failed: ${JSON.stringify(execute.data)}`);
  state.createdExecutionId = execute.data?.executionId || execute.data?.execution_id || null;

  const reset = await api('/api/workflows/reset', {
    method: 'POST',
    body: { recreateStarters: true },
  });
  assert(reset.response.ok, `Workflow reset failed: ${JSON.stringify(reset.data)}`);
  success('Workflow reset endpoint passed');

  state.createdTemplateId = null;
  state.createdExecutionId = null;

  const history = await api('/api/workflows/history?limit=5');
  assert(history.response.ok, `History list after reset failed: ${JSON.stringify(history.data)}`);
  const total = Number(history.data?.total ?? 0);
  assert(total === 0, `History should be empty after reset, got total=${total}`);
  success('Workflow history clear verified');

  const list = await api('/api/workflows/templates');
  assert(list.response.ok, `Template list after reset failed: ${JSON.stringify(list.data)}`);
  const templates = Array.isArray(list.data?.templates) ? list.data.templates : [];
  const starterNames = new Set(templates.map((item) => item?.name));
  assert(starterNames.has('工作流 · 图片生成'), 'Reset missing starter template: 工作流 · 图片生成');
  assert(starterNames.has('工作流 · 图片编辑'), 'Reset missing starter template: 工作流 · 图片编辑');
  assert(starterNames.has('工作流 · 表格分析'), 'Reset missing starter template: 工作流 · 表格分析');
  success('Workflow template rebuild verified');
}

async function cleanup() {
  if (state.createdExecutionId) {
    await api(`/api/workflows/history/${state.createdExecutionId}`, {
      method: 'DELETE',
    });
  }
  if (state.createdTemplateId) {
    await api(`/api/workflows/templates/${state.createdTemplateId}`, {
      method: 'DELETE',
    });
  }
  if (state.createdAgentId) {
    await api(`/api/agents/${state.createdAgentId}`, {
      method: 'DELETE',
    });
    await api(`/api/agents/${state.createdAgentId}?hard_delete=true`, {
      method: 'DELETE',
    });
  }
}

async function main() {
  info(`Base URL: ${BASE_URL}`);
  await resolveToken();
  await testAgentCrud();
  await testStarterTemplates();
  await testTemplateCrud();
  await testWorkflowHistory();
  await testWorkflowResetApi();
  success('All E2E checks passed');
}

main().catch(async (error) => {
  console.error(`❌ E2E failed: ${error?.message || String(error)}`);
  await cleanup();
  process.exit(1);
});
