(function () {
const $ = selector => document.querySelector(selector);
const state = { actor: "", showArchivedPrograms: false, program: null, programs: [], project: null, projects: [], templates: [], selectedTasks: new Set(), openTaskEditors: new Set(), calendarDate: new Date(), selectedDate: null, requirementsProgramId: null, referencePrices: [], budgetSheets: [], materials: [], publicity: [] };
const dateFmt = new Intl.DateTimeFormat("zh-CN", { month: "short", day: "numeric" });
const rangeDateFmt = new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "short", day: "numeric" });
const fullDateFmt = new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric", weekday: "short" });

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[c]);
}

function loadStoredActor() {
  try { return window.localStorage.getItem("training-copilot-actor") || ""; }
  catch (_) { return ""; }
}

function storeActor(value) {
  try {
    if (value) window.localStorage.setItem("training-copilot-actor", value);
    else window.localStorage.removeItem("training-copilot-actor");
  } catch (_) { /* Browsing contexts without storage still support this session. */ }
}

async function api(path, options = {}) {
  const actor = state.actor;
  const { headers: optionHeaders = {}, ...requestOptions } = options;
  const response = await fetch(path, { ...requestOptions, headers: { "Content-Type": "application/json", ...(actor ? { "X-Actor-Name": encodeURIComponent(actor) } : {}), ...optionHeaders } });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "请求失败");
  }
  return response.status === 204 ? null : response.json();
}

function notify(text, ok = false) {
  const el = $("#global-message");
  el.textContent = text;
  el.style.color = ok ? "#199d87" : "";
  window.clearTimeout(notify.timer);
  notify.timer = window.setTimeout(() => { el.textContent = ""; el.style.color = ""; }, 3500);
}

function requirementNotify(text, ok = true) {
  let el = $("#requirement-message");
  if (!el) {
    el = document.createElement("p"); el.id = "requirement-message"; el.className = "requirement-message"; el.setAttribute("role", "status");
    $("#requirements-section .panel-title").after(el);
  }
  el.textContent = text; el.classList.toggle("success", ok);
  window.clearTimeout(requirementNotify.timer);
  requirementNotify.timer = window.setTimeout(() => { el.textContent = ""; }, 4500);
}

function isoDate(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatDate(value) { return value ? dateFmt.format(new Date(`${value}T00:00:00`)) : "未设置"; }
function formatRangeDate(value) { return value ? rangeDateFmt.format(new Date(`${value}T00:00:00`)) : "未设置"; }
function activityTypeLabel(value) { return ({ offline_training: "线下培训", online_training: "线上学习", online_learning: "线上学习", assignment: "作业", practice: "实践", research: "调研", certification: "认证", opening: "开营", closing: "结营" })[value] || "培养活动"; }
function moneyLabel(value) { return `¥${Number(value || 0).toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`; }
function budgetStatusLabel(value) { return ({ pending_confirmation: "待申请", pending_submission: "待申请", submitted: "审批中", in_review: "审批中", approved: "已通过" })[value] || value; }
function materialStatusLabel(value) { return ({ pending_confirmation: "未完成", pending: "未完成", in_progress: "制作中", blocked: "未完成", done: "已完成", cancelled: "未完成" })[value] || value; }
function publicityStatusLabel(value) { return ({ requirement_confirmation: "未完成", pending_confirmation: "未完成", pending: "未完成", material_preparation: "制作中", in_production: "制作中", in_progress: "制作中", done: "已完成", published: "已完成" })[value] || value; }
function statusTone(value) { return value === "approved" || value === "done" ? "tone-done" : value === "in_review" || value === "in_progress" ? "tone-progress" : "tone-pending"; }
function optionalNumber(value) { return value === "" || value == null ? null : Number(value); }

async function loadTemplates() {
  state.templates = await api("/templates");
}

async function loadProjects(selectedId) {
  state.projects = state.program ? state.program.activities.filter(item => item.status !== "archived") : [];
  $("#project-total").textContent = state.projects.length;
  $("#project-list").innerHTML = state.projects.length ? state.projects.map(item => `
    <div class="project-card ${item.id === selectedId ? "active" : ""}">
      <button class="project-select" data-project-id="${item.id}"><strong>${escapeHtml(item.name)}</strong><span>${activityTypeLabel(item.activity_type || item.type)} · ${formatDate(item.event_date || item.start_date)}</span></button>
    </div>`).join("") : `<div class="empty-mini">暂无项目<br>点击右上角开始创建</div>`;
  document.querySelectorAll("[data-project-id]").forEach(button => button.onclick = () => showProject(button.dataset.projectId));
}

async function loadPrograms(selectedId) {
  state.programs = await api(`/api/v2/programs?include_archived=${state.showArchivedPrograms}`);
  const dashboardRows = state.showArchivedPrograms ? [] : await api("/api/v2/dashboard/programs");
  const dashboards = new Map(dashboardRows.map(item => [item.id, item]));
  if (!state.showArchivedPrograms) {
    const activeCount = state.programs.filter(item => item.status !== "archived").length;
    const followupCount = dashboardRows.filter(item => item.next_item).length;
    const riskCount = dashboardRows.reduce((total, item) => total + Number(item.health?.open_alert_count || 0), 0);
    $("#copilot-active-count").textContent = activeCount;
    $("#copilot-followup-count").textContent = followupCount;
    $("#copilot-risk-count").textContent = riskCount;
    $("#copilot-summary-text").textContent = `今天有 ${activeCount} 个项目推进，${followupCount} 个近期事项需要跟进，${riskCount} 个风险建议关注。`;
    $("#copilot-welcome").classList.toggle("has-risk", riskCount > 0);
  }
  $("#program-total").textContent = state.programs.length;
  $("#program-list").innerHTML = state.programs.length ? state.programs.map(item => { const d=dashboards.get(item.id); const healthCode = ["normal", "attention", "risk"].includes(d?.health?.code) ? d.health.code : "normal"; return `<div class="project-card ${item.id === selectedId ? "active" : ""}"><button class="project-select" data-program-id="${item.id}"><span class="program-card-head"><strong>${escapeHtml(item.name)}</strong>${d ? `<em class="health-chip health-${healthCode}">${escapeHtml(d.health.label)}</em>` : ""}</span><span class="program-date">${formatRangeDate(item.start_date)}—${formatRangeDate(item.end_date)}${item.status === "archived" ? " · 已归档" : ""}</span>${d ? `<span class="program-progress-row"><span>项目进度</span><strong>${d.progress}%</strong></span><progress class="program-progress" max="100" value="${Number(d.progress) || 0}">${d.progress}%</progress><small>${escapeHtml(d.owner_name || "未填写负责人")} · ${d.current_phase ? escapeHtml(d.current_phase) : "未设置阶段"}${d.next_item ? ` · 下一节点 ${formatDate(d.next_item.date)}` : ""}</small>` : ""}</button></div>`; }).join("") : `<div class="empty-mini">${state.showArchivedPrograms ? "暂无项目记录" : "暂无进行中的培养项目"}<br>${state.showArchivedPrograms ? "" : "可以查看已归档项目"}</div>`;
  document.querySelectorAll("[data-program-id]").forEach(button => button.onclick = () => showProgram(button.dataset.programId));
}

async function showProgram(id) {
  try {
    if (state.program?.id !== id) { state.project = null; state.selectedTasks.clear(); }
    const program = await api(`/api/v2/programs/${id}`); state.program = program; state.requirementsProgramId = program.id;
    $("#program-detail").hidden = false; $("#program-name").textContent = program.name;
    $("#archive-program").textContent = program.status === "archived" ? "恢复项目" : "归档项目";
    $("#program-meta").textContent = `${formatRangeDate(program.start_date)}—${formatRangeDate(program.end_date)} · ${program.owner_name || "未填写负责人"}`;
    $("#cohort-management").hidden = program.program_type !== "multi_cohort";
    $("#cohort-list").innerHTML = program.cohorts.length ? program.cohorts.map(item => `<div class="entity-chip"><span><strong>${escapeHtml(item.name)}</strong><br><small>${item.participant_count}人 · ${formatDate(item.start_date)}—${formatDate(item.end_date)}</small></span></div>`).join("") : `<div class="empty-mini">本项目不强制设置届别</div>`;
    const cohortSelect = $('#activity-form select[name="cohort_id"]');
    cohortSelect.innerHTML = `<option value="">不关联届别</option>` + program.cohorts.map(item => `<option value="${item.id}">${escapeHtml(item.name)}</option>`).join("");
    const activeActivities = program.activities.filter(item => item.status !== "archived");
    $("#activity-list").innerHTML = activeActivities.length ? activeActivities.map(item => `<div class="entity-chip"><button class="entity-main" data-open-activity="${item.id}">${escapeHtml(item.name)}<br><small>${activityTypeLabel(item.activity_type || item.type)} · ${formatDate(item.start_date)}—${formatDate(item.end_date)}</small></button><span class="entity-actions"><button type="button" data-edit-activity="${item.id}">编辑</button><button type="button" class="danger" data-delete-activity="${item.id}">删除</button></span></div>`).join("") : `<div class="empty-mini">暂无培养活动</div>`;
    $("#class-list").innerHTML = program.classes.length ? program.classes.map(item => `<div class="entity-chip"><span><strong>${escapeHtml(item.name)}</strong><br><small>${item.participant_count}人 · ${formatDate(item.start_date)}—${formatDate(item.end_date)}${item.business_unit ? ` · ${escapeHtml(item.business_unit)}` : ""}</small></span><span class="entity-actions"><button type="button" data-edit-class="${item.id}">编辑</button><button type="button" class="danger" data-delete-class="${item.id}">删除</button></span></div>`).join("") : '<div class="empty-mini">暂无班级</div>';
    const classForm=$("#class-form"); classForm.querySelector('[name="start_date"]').placeholder=program.start_date; classForm.querySelector('[name="end_date"]').placeholder=program.end_date;
    document.querySelectorAll("[data-open-activity]").forEach(button => button.onclick = () => showProject(button.dataset.openActivity));
    document.querySelectorAll("[data-edit-activity]").forEach(button => button.onclick = () => editActivity(activeActivities.find(item => item.id === button.dataset.editActivity)));
    document.querySelectorAll("[data-delete-activity]").forEach(button => button.onclick = async () => { const item=activeActivities.find(row=>row.id===button.dataset.deleteActivity);if(!item||!confirm(`删除培养活动“${item.name}”？该活动将从项目中移除，原节点、任务和历史数据会安全保留。`))return;button.disabled=true;try{await api(`/api/v2/activities/${item.id}`,{method:"DELETE"});if(state.project?.id===item.id){state.project=null;state.selectedTasks.clear();$("#project-detail").hidden=true;}await showProgram(program.id);notify("培养活动已删除",true);}catch(error){button.disabled=false;notify(`培养活动删除失败：${error.message}`);} });
    document.querySelectorAll("[data-edit-class]").forEach(button => button.onclick = () => editClass(program.classes.find(item => item.id === button.dataset.editClass)));
    document.querySelectorAll("[data-delete-class]").forEach(button => button.onclick = async () => { const item=program.classes.find(row=>row.id===button.dataset.deleteClass); if(!item||!confirm(`删除班级“${item.name}”？删除后无法恢复。`))return; button.disabled=true; try{await api(`/api/v2/classes/${item.id}`,{method:"DELETE"});await showProgram(program.id);notify("班级已删除",true);}catch(error){button.disabled=false;notify(`班级删除失败：${error.message}`);} });
    await Promise.all([loadPrograms(id), loadActivityLogs(id)]); await loadProjects();
    if (program.activities.length && !state.project) await showProject(program.activities[0].id);
    if (!$("#requirements-section").hidden) await loadRequirements();
    if (!$("#operations-section").hidden) await showOperations(program.id);
    if (!$("#alerts-section").hidden) await showAlerts(false, program.id);
    if (!$("#resources-section").hidden) await showResources(program.id);
  } catch (error) { notify(`项目加载失败：${error.message}`); }
}

async function loadActivityLogs(programId) {
  const logs = await api(`/api/v2/programs/${programId}/activity-logs`);
  $("#activity-log-list").innerHTML = logs.length ? logs.slice(0, 20).map(item => `<div class="log-item">${escapeHtml(item.summary)}<small>${escapeHtml(item.actor_name)} · ${new Date(item.occurred_at).toLocaleString("zh-CN")}</small></div>`).join("") : `<div class="empty-mini">暂无项目动态</div>`;
}

function requirementProgram() { return state.programs.find(item => item.id === state.requirementsProgramId); }

function requirementActivityOptions(includeProgramLevel = true) {
  const program = requirementProgram();
  const activities = program?.activities || state.program?.id === program?.id ? state.program?.activities || [] : [];
  return `${includeProgramLevel ? '<option value="">项目级/不指定活动</option>' : '<option value="">全部活动及项目级需求</option>'}${activities.filter(item => item.status !== "archived").map(item => `<option value="${item.id}">${escapeHtml(item.name)}</option>`).join("")}`;
}

async function ensureRequirementProgramDetail() {
  const summary = state.programs.find(item => item.id === state.requirementsProgramId);
  if (!summary) return null;
  if (state.program?.id === summary.id) return state.program;
  return api(`/api/v2/programs/${summary.id}`);
}

async function openRequirements(programId = state.program?.id || state.programs[0]?.id) {
  if (!programId) return notify("请先创建培养项目");
  state.requirementsProgramId = programId;
  $("#requirements-section").hidden = false;
  await loadRequirements();
  $("#requirements-section").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function loadRequirements() {
  const programDetail = await ensureRequirementProgramDetail();
  if (!programDetail) return;
  const programSelect = $("#requirements-program");
  programSelect.innerHTML = state.programs.filter(item => item.status !== "archived").map(item => `<option value="${item.id}" ${item.id === state.requirementsProgramId ? "selected" : ""}>${escapeHtml(item.name)}</option>`).join("");
  const activities = programDetail.activities.filter(item => item.status !== "archived");
  const filterActivity = $("#requirements-activity");
  const previousActivity = filterActivity.value;
  const activityOptions = `<option value="">全部活动及项目级需求</option>${activities.map(item => `<option value="${item.id}">${escapeHtml(item.name)}</option>`).join("")}`;
  filterActivity.innerHTML = activityOptions;
  if ([...filterActivity.options].some(item => item.value === previousActivity)) filterActivity.value = previousActivity;
  document.querySelectorAll('#budget-sheet-form select[name="activity_id"], #material-form select[name="activity_id"], #publicity-form select[name="activity_id"]').forEach(select => { select.innerHTML = `<option value="">项目级/不指定活动</option>${activities.map(item => `<option value="${item.id}">${escapeHtml(item.name)}</option>`).join("")}`; });
  if (filterActivity.value) document.querySelectorAll('#budget-sheet-form select[name="activity_id"], #material-form select[name="activity_id"], #publicity-form select[name="activity_id"]').forEach(select => { select.value = filterActivity.value; });
  const query = new URLSearchParams({ program_id: state.requirementsProgramId });
  if (filterActivity.value) query.set("activity_id", filterActivity.value);
  const owner = $("#requirements-owner").value.trim(); if (owner) query.set("owner", owner);
  const requirementStatus = $("#requirements-status").value; if (requirementStatus) query.set("status", requirementStatus);
  const [summary, sheets, materials, publicity, prices] = await Promise.all([
    api(`/api/v2/programs/${state.requirementsProgramId}/requirements/summary`),
    api(`/api/v2/budget-sheets?program_id=${state.requirementsProgramId}${filterActivity.value ? `&activity_id=${filterActivity.value}` : ""}`),
    api(`/api/v2/material-requirements?${query}`),
    api(`/api/v2/publicity-requirements?${query}`),
    api("/api/v2/reference-prices"),
  ]);
  state.budgetSheets = sheets; state.referencePrices = prices; state.materials = materials; state.publicity = publicity;
  const budgetItemOptions = `<option value="">不关联预算项</option>${sheets.flatMap(sheet => sheet.items.map(item => `<option value="${item.id}">${escapeHtml(item.expense_name)} · ${moneyLabel(item.estimated_amount)}</option>`)).join("")}`;
  [$("#material-form"), $("#publicity-form")].forEach(form => {
    let select = form.querySelector('[name="budget_item_id"]');
    if (!select) {
      const label = document.createElement("label");
      label.textContent = "关联预算项（可选）";
      select = document.createElement("select");
      select.name = "budget_item_id";
      label.append(select);
      form.querySelector('[name="activity_id"]').closest("label").after(label);
    }
    select.innerHTML = budgetItemOptions;
  });
  $("#requirement-budget-total").textContent = moneyLabel(summary.budget_total);
  $("#requirement-budget-sheets").textContent = summary.budget_sheet_count;
  $("#requirement-material-open").textContent = `${summary.material_done}/${summary.material_total}`;
  $("#requirement-publicity-open").textContent = `${summary.publicity_done}/${summary.publicity_total}`;
  renderBudgetSheets(sheets, activities); renderMaterials(materials, activities); renderPublicity(publicity, activities); renderReferencePrices(prices);
  const sheetSelect = $('#budget-item-form select[name="budget_sheet_id"]');
  sheetSelect.innerHTML = sheets.map(sheet => `<option value="${sheet.id}">${escapeHtml(activities.find(item => item.id === sheet.activity_id)?.name || "项目级预算")} · ${budgetStatusLabel(sheet.status)}</option>`).join("");
  const priceSelect = $('#budget-item-form select[name="reference_price_id"]');
  priceSelect.innerHTML = `<option value="">不引用</option>${prices.map(item => `<option value="${item.id}">${escapeHtml(item.expense_name)}${item.unit ? ` / ${escapeHtml(item.unit)}` : ""}</option>`).join("")}`;
}

function renderBudgetSheets(sheets, activities) {
  $("#budget-sheet-list").innerHTML = sheets.length ? sheets.map(sheet => `<article class="requirement-card status-card ${statusTone(sheet.status)}"><div><strong>${escapeHtml(activities.find(item => item.id === sheet.activity_id)?.name || "项目级预算")}</strong><span>${budgetStatusLabel(sheet.status)} · ${sheet.owner_name || "未填写负责人"}</span><small>${sheet.planned_apply_date ? `计划申请 ${formatDate(sheet.planned_apply_date)}` : "未设置申请日期"}</small></div><b>${moneyLabel(sheet.estimated_total)}</b><div class="requirement-actions"><select data-budget-status="${sheet.id}">${["pending_submission","in_review","approved"].map(value => `<option value="${value}" ${sheet.status === value ? "selected" : ""}>${budgetStatusLabel(value)}</option>`).join("")}</select><button class="text-button edit-budget-sheet" data-sheet-id="${sheet.id}">编辑表头</button><button class="text-button add-budget-item" data-sheet-id="${sheet.id}">＋费用项</button><button class="text-button danger delete-budget-sheet" data-sheet-id="${sheet.id}">删除预算表</button></div><div class="budget-items">${sheet.items.length ? sheet.items.map(item => `<div class="budget-dot ${statusTone(item.status)}"><span>• ${escapeHtml(item.expense_name)} · ${item.quantity}${item.unit || ""}</span><strong>${moneyLabel(item.estimated_amount)}</strong><select data-budget-item-status="${item.id}">${["pending_submission","in_review","approved"].map(value=>`<option value="${value}" ${item.status===value?"selected":""}>${budgetStatusLabel(value)}</option>`).join("")}</select><small>${item.reference_price_id ? "已保存参考价格快照" : "人工估算"}</small></div>`).join("") : '<small>暂无费用项</small>'}</div></article>`).join("") : `<div class="empty-mini">当前范围暂无预算表</div>`;
  document.querySelectorAll("[data-budget-status]").forEach(select => select.onchange = async () => { await api(`/api/v2/budget-sheets/${select.dataset.budgetStatus}`, { method: "PATCH", body: JSON.stringify({ status: select.value, actual_apply_date: select.value === "in_review" ? isoDate(new Date()) : undefined }) }); await loadRequirements(); notify("预算申请进度已更新", true); });
  document.querySelectorAll("[data-budget-item-status]").forEach(select => select.onchange = async () => { await api(`/api/v2/budget-items/${select.dataset.budgetItemStatus}`,{method:"PATCH",body:JSON.stringify({status:select.value})}); await loadRequirements(); notify("费用项状态已更新",true); });
  document.querySelectorAll(".add-budget-item").forEach(button => button.onclick = () => { const form = $("#budget-item-form"); form.hidden = false; form.querySelector('[name="budget_sheet_id"]').value = button.dataset.sheetId; form.scrollIntoView({ behavior: "smooth", block: "center" }); });
  document.querySelectorAll(".edit-budget-sheet").forEach(button => button.onclick = () => { const sheet=sheets.find(item=>item.id===button.dataset.sheetId),form=$("#budget-edit-form"); form.elements.id.value=sheet.id; form.elements.owner_name.value=sheet.owner_name||""; form.elements.planned_apply_date.value=sheet.planned_apply_date||""; form.elements.status.value=sheet.status; form.elements.notes.value=sheet.notes||""; $("#budget-edit-dialog").showModal(); });
  document.querySelectorAll(".delete-budget-sheet").forEach(button => button.onclick = async () => { if (!confirm("删除这张预算表及其中所有费用项？此操作无法撤销。")) return; try { await api(`/api/v2/budget-sheets/${button.dataset.sheetId}`, { method: "DELETE" }); await loadRequirements(); requirementNotify("预算表已删除"); } catch (error) { requirementNotify(`预算表删除失败：${error.message}`, false); } });
}

function renderMaterials(items, activities) {
  $("#material-list").innerHTML = items.length ? `<div class="requirement-bulk"><label><input type="checkbox" data-select-all-requirements="material">全选当前物料</label><select data-bulk-status="material"><option value="pending">未完成</option><option value="in_progress">制作中</option><option value="done">已完成</option></select><button type="button" class="text-button apply-requirement-bulk" data-kind="material">批量调整状态</button><span data-selected-count="material">已选 0 项</span></div>${items.map(item => `<article class="requirement-card status-card ${statusTone(item.status)}"><input class="requirement-select" data-select-material="${item.id}" type="checkbox" aria-label="选择${escapeHtml(item.name)}"><div><strong>• ${escapeHtml(item.name)}</strong><span>${escapeHtml(activities.find(activity => activity.id === item.activity_id)?.name || "项目级")} · ${item.owner_name || "未填写负责人"}</span><small>${item.quantity ?? "数量未定"}${item.specification ? ` · ${escapeHtml(item.specification)}` : ""}${item.content_due_date ? ` · 内容截止 ${formatDate(item.content_due_date)}` : ""}${item.expected_delivery_date ? ` · 交付 ${formatDate(item.expected_delivery_date)}` : ""}</small></div><select data-material-status="${item.id}">${["pending","in_progress","done"].map(value => `<option value="${value}" ${item.status === value ? "selected" : ""}>${materialStatusLabel(value)}</option>`).join("")}</select><div class="requirement-actions"><button type="button" class="text-button edit-material" data-edit-material="${item.id}">编辑</button><button type="button" class="text-button danger delete-material" data-delete-material="${item.id}">删除</button></div></article>`).join("")}` : `<div class="empty-mini">当前筛选下暂无物料需求</div>`;
  document.querySelectorAll("[data-material-status]").forEach(select => select.onchange = async () => { await api(`/api/v2/material-requirements/${select.dataset.materialStatus}`, { method: "PATCH", body: JSON.stringify({ status: select.value }) }); await loadRequirements(); notify("物料状态已更新", true); });
  bindRequirementActions("material", items);
}

function renderPublicity(items, activities) {
  $("#publicity-list").innerHTML = items.length ? `<div class="requirement-bulk"><label><input type="checkbox" data-select-all-requirements="publicity">全选当前宣传</label><select data-bulk-status="publicity"><option value="pending">未完成</option><option value="in_progress">制作中</option><option value="done">已完成</option></select><button type="button" class="text-button apply-requirement-bulk" data-kind="publicity">批量调整状态</button><span data-selected-count="publicity">已选 0 项</span></div>${items.map(item => `<article class="requirement-card status-card ${statusTone(item.status)}"><input class="requirement-select" data-select-publicity="${item.id}" type="checkbox" aria-label="选择${escapeHtml(item.content_type)}"><div><strong>• ${escapeHtml(item.content_type)} ×${item.quantity}</strong><span>${escapeHtml(activities.find(activity => activity.id === item.activity_id)?.name || "项目级")} · ${item.owner_name || "未填写负责人"}</span><small>${item.format ? `${escapeHtml(item.format)} · ` : ""}${item.start_date ? `开始 ${formatDate(item.start_date)} · ` : ""}${item.expected_completion_date ? `制作截止 ${formatDate(item.expected_completion_date)}` : "未设置制作截止"}${item.publish_date ? ` · 发布 ${formatDate(item.publish_date)}` : ""}</small></div><select data-publicity-status="${item.id}">${["pending","in_progress","done"].map(value => `<option value="${value}" ${item.status === value ? "selected" : ""}>${publicityStatusLabel(value)}</option>`).join("")}</select><div class="requirement-actions"><button type="button" class="text-button edit-publicity" data-edit-publicity="${item.id}">编辑</button><button type="button" class="text-button danger delete-publicity" data-delete-publicity="${item.id}">删除</button></div></article>`).join("")}` : `<div class="empty-mini">当前筛选下暂无宣传需求</div>`;
  document.querySelectorAll("[data-publicity-status]").forEach(select => select.onchange = async () => { await api(`/api/v2/publicity-requirements/${select.dataset.publicityStatus}`, { method: "PATCH", body: JSON.stringify({ status: select.value }) }); await loadRequirements(); notify("宣传状态已更新", true); });
  bindRequirementActions("publicity", items);
}

function bindRequirementActions(kind, items) {
  const selectKey = kind === "material" ? "selectMaterial" : "selectPublicity";
  const boxes = [...document.querySelectorAll(`[data-select-${kind}]`)], all = document.querySelector(`[data-select-all-requirements="${kind}"]`), count = document.querySelector(`[data-selected-count="${kind}"]`);
  const update = () => { const n=boxes.filter(item=>item.checked).length; if(count)count.textContent=`已选 ${n} 项`; if(all){all.checked=n===boxes.length&&n>0;all.indeterminate=n>0&&n<boxes.length;} };
  boxes.forEach(box=>box.onchange=update); if(all)all.onchange=()=>{boxes.forEach(box=>box.checked=all.checked);update();};
  document.querySelector(`.apply-requirement-bulk[data-kind="${kind}"]`)?.addEventListener("click",async()=>{const ids=boxes.filter(box=>box.checked).map(box=>box.dataset[selectKey]);if(!ids.length)return notify("请先勾选需要调整的需求");const status=document.querySelector(`[data-bulk-status="${kind}"]`).value,base=kind==="material"?"material-requirements":"publicity-requirements";await Promise.all(ids.map(id=>api(`/api/v2/${base}/${id}`,{method:"PATCH",body:JSON.stringify({status})})));await loadRequirements();if(kind==="publicity"&&!$("#publicity-calendar").hidden)await showPublicityCalendar();notify(`已批量更新 ${ids.length} 项`,true);});
  document.querySelectorAll(`[data-edit-${kind}]`).forEach(button=>button.onclick=()=>openRequirementEditor(kind,items.find(item=>item.id===button.dataset[kind==="material"?"editMaterial":"editPublicity"])));
  document.querySelectorAll(`[data-delete-${kind}]`).forEach(button=>button.onclick=async()=>{const id=button.dataset[kind==="material"?"deleteMaterial":"deletePublicity"],item=items.find(row=>row.id===id),name=kind==="material"?item.name:item.content_type;if(!confirm(`删除“${name}”？此操作无法撤销。`))return;await api(`/api/v2/${kind==="material"?"material-requirements":"publicity-requirements"}/${id}`,{method:"DELETE"});await loadRequirements();if(kind==="publicity"&&!$("#publicity-calendar").hidden)await showPublicityCalendar();notify("需求已删除",true);});
}

function openRequirementEditor(kind, item) {
  const dialog=$("#requirement-edit-dialog"),form=$("#requirement-edit-form"),activities=state.program?.id===state.requirementsProgramId?state.program.activities:[];
  $("#requirement-edit-title").textContent=kind==="material"?`编辑物料｜${item.name}`:`编辑宣传｜${item.content_type}`;
  form.dataset.kind=kind;form.dataset.itemId=item.id;
  const activityOptions=`<option value="">项目级/不指定活动</option>${activities.filter(x=>x.status!=="archived").map(x=>`<option value="${x.id}" ${item.activity_id===x.id?"selected":""}>${escapeHtml(x.name)}</option>`).join("")}`;
  form.innerHTML=kind==="material"?`<label>关联活动<select name="activity_id">${activityOptions}</select></label><label>物料名称<input name="name" value="${escapeHtml(item.name)}" required></label><label>数量<input name="quantity" type="number" min="0" step="0.01" value="${item.quantity??""}"></label><label>尺寸/规格<input name="specification" value="${escapeHtml(item.specification||"")}"></label><label>负责人<input name="owner_name" value="${escapeHtml(item.owner_name||"")}"></label><label>内容提供截止<input name="content_due_date" type="date" value="${item.content_due_date||""}"></label><label>预计交付<input name="expected_delivery_date" type="date" value="${item.expected_delivery_date||""}"></label><label>状态<select name="status">${["pending","in_progress","done"].map(x=>`<option value="${x}" ${item.status===x?"selected":""}>${materialStatusLabel(x)}</option>`).join("")}</select></label><label class="check-label"><input name="include_in_budget" type="checkbox" ${item.include_in_budget?"checked":""}>计入预算</label><label class="full">备注<textarea name="notes">${escapeHtml(item.notes||"")}</textarea></label><div class="dialog-actions full"><button class="primary-button">保存修改</button><button type="button" class="text-button close-dialog">取消</button></div>`:`<label>关联活动<select name="activity_id">${activityOptions}</select></label><label>内容类型<input name="content_type" value="${escapeHtml(item.content_type)}" required></label><label>形式<input name="format" value="${escapeHtml(item.format||"")}"></label><label>数量<input name="quantity" type="number" min="1" value="${item.quantity}"></label><label>负责人<input name="owner_name" value="${escapeHtml(item.owner_name||"")}"></label><label>开始日期<input name="start_date" type="date" value="${item.start_date||""}"></label><label>制作截止日期<input name="expected_completion_date" type="date" value="${item.expected_completion_date||""}"></label><label>预计发布日期<input name="publish_date" type="date" value="${item.publish_date||""}"></label><label>状态<select name="status">${["pending","in_progress","done"].map(x=>`<option value="${x}" ${item.status===x?"selected":""}>${publicityStatusLabel(x)}</option>`).join("")}</select></label><label class="full">备注<textarea name="notes">${escapeHtml(item.notes||"")}</textarea></label><div class="dialog-actions full"><button class="primary-button">保存修改</button><button type="button" class="text-button close-dialog">取消</button></div>`;
  form.querySelectorAll(".close-dialog").forEach(button=>button.onclick=()=>dialog.close());dialog.showModal();form.querySelector("input,select")?.focus();
}

function renderReferencePrices(prices) {
  $("#reference-price-list").innerHTML = prices.map(item => `<form class="price-row" data-price-id="${item.id}"><strong>${escapeHtml(item.expense_name)}</strong><select name="price_type"><option value="unit" ${item.price_type === "unit" ? "selected" : ""}>单价</option><option value="range" ${item.price_type === "range" ? "selected" : ""}>区间</option></select><input name="unit_price" type="number" min="0" step="0.01" value="${item.unit_price ?? ""}" placeholder="单价"><input name="min_price" type="number" min="0" step="0.01" value="${item.min_price ?? ""}" placeholder="最低价"><input name="max_price" type="number" min="0" step="0.01" value="${item.max_price ?? ""}" placeholder="最高价"><input name="unit" value="${escapeHtml(item.unit || "")}" placeholder="单位"><button class="text-button">保存</button><button type="button" class="price-delete" data-delete-price="${item.id}" aria-label="删除${escapeHtml(item.expense_name)}">×</button></form>`).join("");
  document.querySelectorAll("[data-price-id]").forEach(form => form.onsubmit = async event => { event.preventDefault(); const data = new FormData(form), button = form.querySelector("button"); try { await api(`/api/v2/reference-prices/${form.dataset.priceId}`, { method: "PATCH", body: JSON.stringify({ price_type: data.get("price_type"), unit_price: optionalNumber(data.get("unit_price")), min_price: optionalNumber(data.get("min_price")), max_price: optionalNumber(data.get("max_price")), unit: data.get("unit").trim() || null }) }); button.textContent = "已保存 ✓"; button.classList.add("saved"); requirementNotify(`“${form.querySelector("strong").textContent}”参考价格已保存，历史预算不受影响`); window.setTimeout(() => { button.textContent = "保存"; button.classList.remove("saved"); }, 2200); } catch (error) { requirementNotify(`参考价格保存失败：${error.message}`, false); } });
  document.querySelectorAll("[data-delete-price]").forEach(button => button.onclick = async () => { const name=button.closest("form").querySelector("strong").textContent; if(!confirm(`删除参考价格“${name}”？已创建预算中的价格快照不会受到影响。`)) return; try { await api(`/api/v2/reference-prices/${button.dataset.deletePrice}`,{method:"DELETE"}); await loadRequirements(); requirementNotify(`参考价格“${name}”已删除`); } catch(error){requirementNotify(`参考价格删除失败：${error.message}`,false);} });
}

function statusLabel(value) { return ({ todo: "未开始", in_progress: "进行中", blocked: "阻塞", done: "已完成", cancelled: "已取消" })[value] || value; }

async function deleteProject(id, name) {
  if (!window.confirm(`确定永久删除项目“${name}”吗？\n\n该项目的所有节点和任务都会一并删除，无法撤销。`)) return;
  try {
    await api(`/projects/${id}`, { method: "DELETE" });
    if (state.project?.id === id) state.project = null;
    await loadProjects();
    if (state.projects.length) await showProject(state.projects[0].id);
    else {
      $("#project-detail").hidden = true;
      updateMetrics(null); renderCalendar();
      $("#day-items").innerHTML = `<div class="empty-mini">暂无项目数据</div>`;
    }
    notify("项目已删除", true);
  } catch (error) { notify(`删除失败：${error.message}`); }
}

function updateMetrics(project) {
  const tasks = project ? project.tasks.filter(t => t.status !== "cancelled") : [];
  const done = tasks.filter(t => t.status === "done").length;
  const todo = tasks.length - done;
  const rate = tasks.length ? Math.round(done / tasks.length * 100) : 0;
  const today = isoDate(new Date());
  const overdue = tasks.filter(t => t.status !== "done" && t.deadline < today).length;
  const milestones = project ? project.milestones.filter(m => m.status === "active") : [];
  const next = milestones.filter(m => m.deadline >= today).sort((a, b) => a.deadline.localeCompare(b.deadline))[0];
  $("#completion-rate").textContent = `${rate}%`;
  $("#progress-bar").style.width = `${rate}%`;
  $("#progress-caption").textContent = tasks.length ? `${done} / ${tasks.length} 项任务已完成` : "暂无任务数据";
  $("#done-count").textContent = done;
  $("#todo-count").textContent = todo;
  $("#overdue-caption").textContent = `${overdue} 项已逾期`;
  $("#milestone-count").textContent = milestones.length;
  $("#next-milestone").textContent = next ? `下一节点：${formatDate(next.deadline)}` : "暂无后续节点";
}

function itemsForDate(date) {
  if (!state.project) return [];
  const milestones = state.project.milestones.filter(m => m.status === "active" && m.deadline === date)
    .map(m => ({ kind: "milestone", label: m.code || "M", title: m.name, done: false, meta: m.required ? "关键" : "普通" }));
  const tasks = state.project.tasks.filter(t => t.status !== "cancelled" && t.deadline === date)
    .map(t => ({ kind: "task", label: "任务", title: t.title, done: t.status === "done", meta: t.owner ? `负责人：${t.owner}` : "未分配负责人" }));
  return [...milestones, ...tasks];
}

function selectDate(date) {
  state.selectedDate = date;
  const items = itemsForDate(date);
  $("#selected-date-title").textContent = fullDateFmt.format(new Date(`${date}T00:00:00`));
  $("#day-items").innerHTML = items.length ? items.map(item => `
    <article class="day-item ${item.done ? "done" : ""}"><small>${escapeHtml(item.label)}${item.kind === "milestone" ? ` · ${escapeHtml(item.meta)}` : ""}${item.done ? " · 已完成" : ""}</small><strong>${escapeHtml(item.title)}</strong>${item.kind === "task" ? `<span>${escapeHtml(item.meta)}</span>` : ""}</article>`).join("")
    : `<div class="empty-mini">当天没有安排<br>可以在下方新增节点或任务</div>`;
  renderCalendar();
}

function renderCalendar() {
  const anchor = state.calendarDate;
  const year = anchor.getFullYear(), month = anchor.getMonth();
  $("#calendar-title").textContent = `${year} 年 ${month + 1} 月`;
  const first = new Date(year, month, 1);
  const mondayOffset = (first.getDay() + 6) % 7;
  const gridStart = new Date(year, month, 1 - mondayOffset);
  const today = isoDate(new Date());
  const cells = [];
  for (let i = 0; i < 42; i++) {
    const date = new Date(gridStart); date.setDate(gridStart.getDate() + i);
    const key = isoDate(date), items = itemsForDate(key);
    const hasMilestone = items.some(item => item.kind === "milestone");
    const hasOpenTask = items.some(item => item.kind === "task" && !item.done);
    const hasDone = items.some(item => item.kind === "task" && item.done);
    cells.push(`<button class="calendar-day ${date.getMonth() !== month ? "outside" : ""} ${key === today ? "today" : ""} ${key === state.selectedDate ? "selected" : ""}" data-date="${key}">
      <span class="day-number">${date.getDate()}</span><span class="day-markers">${hasMilestone ? '<i class="marker milestone"></i>' : ""}${hasOpenTask ? '<i class="marker task"></i>' : ""}${hasDone ? '<i class="marker done"></i>' : ""}</span>
    </button>`);
  }
  $("#calendar-grid").innerHTML = cells.join("");
  document.querySelectorAll("[data-date]").forEach(button => button.onclick = () => selectDate(button.dataset.date));
}

function renderSubtasks(task) {
  const subtasks = task.subtasks.filter(item => item.status !== "cancelled");
  const weight = subtasks.length ? 100 / subtasks.length : 0;
  return subtasks.map(subtask => `<div class="subtask-item" data-subtask-item="${subtask.id}"><label class="subtask-check"><input data-subtask-id="${subtask.id}" type="checkbox" ${subtask.status === "done" ? "checked" : ""}><span>• ${escapeHtml(subtask.title)}</span></label><span class="subtask-weight">等权 ${Number.isInteger(weight) ? weight : weight.toFixed(2)}%</span><label>开始<input data-subtask-start="${subtask.id}" type="date" value="${subtask.start_date}"></label><label>截止<input data-subtask-deadline="${subtask.id}" type="date" value="${subtask.deadline}"></label><label>进度<input data-subtask-progress="${subtask.id}" type="number" min="0" max="100" value="${subtask.progress_percent}"></label></div>`).join("");
}

function renderTimeline(project) {
  const tasks = project.tasks.filter(t => t.status !== "cancelled");
  const groups = project.milestones.filter(m => m.status === "active").map(milestone => ({
    milestone, tasks: tasks.filter(task => task.project_milestone_id === milestone.id),
  })).sort((a, b) => a.milestone.deadline.localeCompare(b.milestone.deadline) || a.milestone.sort_order - b.milestone.sort_order);
  $("#timeline").innerHTML = groups.map(({ milestone, tasks: grouped }) => {
    const done = grouped.filter(t => t.status === "done").length;
    return `<article class="milestone">
      <div><span class="milestone-ddl-label">${escapeHtml(milestone.code)} · ${escapeHtml(milestone.phase)}</span><div class="milestone-range"><span>开始 <strong>${escapeHtml((milestone.start_date || "").replaceAll("-", "/"))}</strong></span><i>→</i><span>截止 <strong>${escapeHtml((milestone.deadline || "").replaceAll("-", "/"))}</strong></span></div></div>
      <div><div class="milestone-top"><input class="milestone-name-input" data-mid="${milestone.id}" value="${escapeHtml(milestone.name)}" maxlength="200"><div class="milestone-controls"><span>${done}/${grouped.length} 已完成</span><label class="milestone-select"><input type="checkbox" data-select-milestone="${milestone.id}">全选本节点</label><button class="link-button complete-milestone-tasks" data-mid="${milestone.id}">批量标记完成</button><a class="link-button" href="/api/v2/milestones/${milestone.id}/calendar.ics">导出本节点日历</a><button class="link-button milestone-required ${milestone.required ? "accent" : ""}" data-mid="${milestone.id}" data-value="${Boolean(milestone.required)}">${milestone.required ? "◆ 关键节点" : "◇ 设为关键"}</button><button class="link-button accent add-task" data-mid="${milestone.id}">＋任务</button><button class="link-button danger remove-milestone" data-mid="${milestone.id}">移除</button></div></div>
      <form class="inline-task-form" data-task-form="${milestone.id}" hidden><input name="title" maxlength="300" required placeholder="任务名称"><input name="owner" maxlength="200" placeholder="负责人（选填）"><label class="check-label"><input name="required" type="checkbox">关键</label><button class="primary-button">保存</button><button type="button" class="text-button cancel-task">取消</button></form>
      <div class="task-list">${grouped.map(task => `<div class="task ${task.status === "done" ? "done" : ""}"><label class="task-main"><input class="task-select" data-select-task="${task.id}" type="checkbox" ${state.selectedTasks.has(task.id) ? "checked" : ""}><span>${escapeHtml(task.title)}</span></label><div class="task-tools"><span class="status-pill">${statusLabel(task.status)} · ${task.effective_progress_percent}%</span><button class="link-button task-required ${task.required ? "accent" : ""}" data-tid="${task.id}" data-value="${Boolean(task.required)}">${task.required ? "◆ 关键" : "◇ 设为关键"}</button><button class="link-button danger remove-task" data-tid="${task.id}">移除</button></div><form class="task-editor" data-edit-task="${task.id}"><label>负责人<input name="owner" maxlength="500" value="${escapeHtml(task.owner || "")}" placeholder="可填写多人"></label><label>状态<select name="status">${["todo","in_progress","blocked","done","cancelled"].map(value => `<option value="${value}" ${task.status === value ? "selected" : ""}>${statusLabel(value)}</option>`).join("")}</select></label><label>开始日期<input name="start_date" type="date" value="${task.start_date}"></label><label>截止日期<input name="deadline" type="date" value="${task.deadline}"></label><label>进度模式<select name="progress_mode"><option value="manual" ${task.progress_mode === "manual" ? "selected" : ""}>人工</option><option value="auto" ${task.progress_mode === "auto" ? "selected" : ""}>子任务自动</option></select></label><label>人工进度<input name="progress_percent" type="number" min="0" max="100" value="${task.progress_percent}"></label><label class="full">进度备注<textarea name="progress_note">${escapeHtml(task.progress_note || "")}</textarea></label><label class="full">完成标准<textarea name="completion_criteria">${escapeHtml(task.completion_criteria || "")}</textarea></label><label class="full">普通备注<textarea name="notes">${escapeHtml(task.notes || "")}</textarea></label>${task.status === "done" ? `<label>质量评分（1–5）<input name="quality_score" type="number" min="1" max="5" value="${task.quality_score || ""}"></label><label class="full">复盘反馈<textarea name="retrospective_note">${escapeHtml(task.retrospective_note || "")}</textarea></label>` : ""}<div class="task-editor-actions"><button class="text-button">保存任务</button><span class="progress-note">子任务计算 ${task.auto_progress_percent}% · 当前有效 ${task.effective_progress_percent}%</span></div><div class="subtask-list">${renderSubtasks(task)}</div>${task.subtasks.some(item => item.status !== "cancelled") ? `<button type="button" class="text-button save-all-subtasks">保存全部小任务</button>` : ""}<div class="subtask-form" data-subtask-form="${task.id}"><label class="subtask-title-field">子任务名称<input name="subtask_title" maxlength="300" placeholder="输入子任务名称"></label><label>开始日期<input name="subtask_start" type="date" value="${task.start_date}"></label><label>截止日期<input name="subtask_deadline" type="date" value="${task.deadline}"></label><button type="button" class="text-button add-subtask">添加</button></div></form></div>`).join("")}</div></div>
    </article>`;
  }).join("") || `<div class="empty-mini">暂无节点</div>`;
  document.querySelectorAll(".task").forEach(card => {
    const editor = card.querySelector(".task-editor");
    const tools = card.querySelector(".task-tools");
    if (!editor || !tools) return;
    const task = project.tasks.find(item => item.id === editor.dataset.editTask);
    const title = card.querySelector(".task-main span");
    if (title && task.deadline) title.insertAdjacentHTML("beforeend", `<small class="task-ddl">截止日期：${escapeHtml(task.deadline.replaceAll("-", "/"))}</small>`);
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "link-button toggle-task-editor";
    toggle.textContent = "编辑节点详情";
    toggle.onclick = () => openTaskDialog(task);
    const branch = document.createElement("button");
    branch.type = "button";
    branch.className = "link-button branch-task-button";
    branch.textContent = "新增分支任务";
    branch.onclick = () => openSubtaskDialog(task);
    if (task.resource_count) {
      const resource = document.createElement("button");
      resource.type = "button"; resource.className = "link-button task-resource-indicator";
      resource.textContent = `📃 ${task.resource_count}`;
      resource.title = "查看关联资料";
      resource.onclick = () => openTaskDialog(task);
      tools.prepend(resource);
    }
    tools.prepend(branch);
    tools.prepend(toggle);
  });
  bindSubtaskEvents(project.id);
  bindTimelineEvents(project.id);
}

async function openTaskDialog(task) {
  const dialog = $("#task-detail-dialog"), form = $("#task-detail-form");
  const resources = await api(`/api/v2/tasks/${task.id}/resources`);
  $("#task-dialog-title").textContent = `编辑节点详情｜${task.title}`;
  form.dataset.taskId = task.id;
  form.innerHTML = `<label>负责人<input name="owner" maxlength="500" value="${escapeHtml(task.owner || "")}" placeholder="可填写多人"></label><label>状态<select name="status">${["todo","in_progress","blocked","done","cancelled"].map(value => `<option value="${value}" ${task.status === value ? "selected" : ""}>${statusLabel(value)}</option>`).join("")}</select></label><label>开始日期<input name="start_date" type="date" value="${task.start_date}"></label><label>截止日期<input name="deadline" type="date" value="${task.deadline}"></label><label>进度模式<select name="progress_mode"><option value="manual" ${task.progress_mode === "manual" ? "selected" : ""}>人工</option><option value="auto" ${task.progress_mode === "auto" ? "selected" : ""}>分支任务自动</option></select></label><label>人工进度<input name="progress_percent" type="number" min="0" max="100" value="${task.progress_percent}"></label><label class="full">进度备注<textarea name="progress_note">${escapeHtml(task.progress_note || "")}</textarea></label><label class="full">完成标准<textarea name="completion_criteria">${escapeHtml(task.completion_criteria || "")}</textarea></label><label class="full">普通备注<textarea name="notes">${escapeHtml(task.notes || "")}</textarea></label><label>质量评分（完成后1–5）<input name="quality_score" type="number" min="1" max="5" value="${task.quality_score || ""}"></label><label class="full">复盘反馈<textarea name="retrospective_note">${escapeHtml(task.retrospective_note || "")}</textarea></label><section class="task-dialog-resources full"><h3>关联资料 ${resources.length ? `(${resources.length})` : ""}</h3>${resources.length ? resources.map(item => `<a href="${escapeHtml(item.url)}" target="_blank" rel="noopener">📃 ${escapeHtml(item.title)} · ${item.relation_type === "deliverable" ? "交付物" : "参考资料"}</a>`).join("") : '<span>暂无关联资料，可在“SOP 与资料”中建立关联。</span>'}</section><p class="dialog-hint full">分支任务计算进度 ${task.auto_progress_percent}% · 当前有效进度 ${task.effective_progress_percent}%</p><div class="dialog-actions full"><button class="primary-button">保存节点详情</button><button type="button" class="text-button close-dialog">取消</button></div>`;
  dialog.showModal();
  form.querySelector("input,select")?.focus();
}

function renderSubtaskDialog(task) {
  const active = task.subtasks.filter(item => item.status !== "cancelled"), weight = active.length ? 100 / active.length : 0;
  $("#subtask-dialog-title").textContent = `分支任务｜${task.title}`;
  $("#subtask-dialog-list").innerHTML = active.length ? active.map(item => `<form class="branch-task-row" data-branch-id="${item.id}"><div class="branch-task-heading"><strong>• ${escapeHtml(item.title)}</strong><span>等权 ${Number.isInteger(weight) ? weight : weight.toFixed(2)}%</span></div><label>名称<input name="title" value="${escapeHtml(item.title)}" required></label><label>负责人<input name="owner" value="${escapeHtml(item.owner || "")}"></label><label>开始日期<input name="start_date" type="date" value="${item.start_date}" required></label><label>截止日期<input name="deadline" type="date" value="${item.deadline}" required></label><label>进度<input name="progress_percent" type="number" min="0" max="100" value="${item.progress_percent}"></label><label>状态<select name="status">${["todo","in_progress","blocked","done"].map(value => `<option value="${value}" ${item.status === value ? "selected" : ""}>${statusLabel(value)}</option>`).join("")}</select></label><label class="full">备注<textarea name="notes">${escapeHtml(item.notes || "")}</textarea></label><button class="text-button">保存该分支</button></form>`).join("") : '<div class="empty-mini">暂无分支任务，可在下方添加。</div>';
  document.querySelectorAll(".branch-task-row").forEach(form => form.onsubmit = async event => { event.preventDefault(); const data=new FormData(form); try { await api(`/api/v2/subtasks/${form.dataset.branchId}`,{method:"PATCH",body:JSON.stringify({title:data.get("title").trim(),owner:data.get("owner").trim()||null,start_date:data.get("start_date"),deadline:data.get("deadline"),progress_percent:Number(data.get("progress_percent")||0),status:data.get("status"),notes:data.get("notes").trim()||null})}); await showProject(state.project.id); renderSubtaskDialog(state.project.tasks.find(x=>x.id===task.id)); notify("分支任务已保存",true); } catch(error){notify(`分支任务保存失败：${error.message}`);} });
}

function openSubtaskDialog(task) {
  const dialog=$("#subtask-dialog"), form=$("#subtask-dialog-form");
  form.reset(); form.querySelector('[name="task_id"]').value=task.id;
  form.querySelector('[name="start_date"]').value=task.start_date;
  form.querySelector('[name="deadline"]').value=task.deadline;
  renderSubtaskDialog(task); dialog.showModal();
  form.querySelector('[name="title"]').focus();
}

async function showProject(id) {
  try {
    if (state.project?.id !== id) state.selectedTasks.clear();
    const project = await api(`/projects/${id}`); state.project = project;
    $("#project-detail").hidden = false; $("#detail-name").textContent = project.name;
    $("#detail-meta").textContent = `${formatDate(project.start_date)}—${formatDate(project.end_date || project.event_date)} · ${project.owner_name || "未填写负责人"}`;
    updateMetrics(project); renderCalendar(); renderTimeline(project); updateBulkCount(); await loadProjects(id); if (state.program) await loadActivityLogs(state.program.id);
  } catch (error) { notify(error.message); }
}

function updateBulkCount() {
  document.querySelectorAll("[data-select-milestone]").forEach(control => {
    const tasks = [...control.closest("article").querySelectorAll("[data-select-task]")];
    control.checked = tasks.length > 0 && tasks.every(task => state.selectedTasks.has(task.dataset.selectTask));
    control.indeterminate = tasks.some(task => state.selectedTasks.has(task.dataset.selectTask)) && !control.checked;
  });
}

function bindTimelineEvents(projectId) {
  document.querySelectorAll(".milestone-name-input").forEach(el => el.onblur = async () => { const name = el.value.trim(); if (name && name !== el.defaultValue) { await api(`/project-milestones/${el.dataset.mid}`, { method: "PATCH", body: JSON.stringify({ name }) }); el.defaultValue = name; } });
  document.querySelectorAll(".milestone-required").forEach(el => el.onclick = async () => { await api(`/project-milestones/${el.dataset.mid}`, { method: "PATCH", body: JSON.stringify({ required: el.dataset.value !== "true" }) }); await showProject(projectId); });
  document.querySelectorAll(".remove-milestone").forEach(el => el.onclick = async () => { if (confirm("移除这个节点及其任务？标准模板不会受到影响。")) { await api(`/project-milestones/${el.dataset.mid}`, { method: "DELETE" }); await showProject(projectId); } });
  document.querySelectorAll("[data-select-task]").forEach(el => el.onchange = () => { el.checked ? state.selectedTasks.add(el.dataset.selectTask) : state.selectedTasks.delete(el.dataset.selectTask); updateBulkCount(); });
  document.querySelectorAll("[data-select-milestone]").forEach(control => control.onchange = () => {
    control.closest("article").querySelectorAll("[data-select-task]").forEach(task => {
      task.checked = control.checked;
      control.checked ? state.selectedTasks.add(task.dataset.selectTask) : state.selectedTasks.delete(task.dataset.selectTask);
    });
    updateBulkCount();
  });
  document.querySelectorAll(".complete-milestone-tasks").forEach(button => button.onclick = async () => {
    const selected = [...button.closest("article").querySelectorAll("[data-select-task]:checked")].map(task => task.dataset.selectTask);
    if (!selected.length) return notify("请先勾选本节点中的任务");
    await api("/api/v2/tasks/bulk", { method: "POST", body: JSON.stringify({ task_ids: selected, action: "complete" }) });
    selected.forEach(id => state.selectedTasks.delete(id));
    await showProject(projectId);
    notify(`已完成本节点所选的 ${selected.length} 项任务`, true);
  });
  document.querySelectorAll(".task-required").forEach(el => el.onclick = async () => { await api(`/tasks/${el.dataset.tid}/required`, { method: "PATCH", body: JSON.stringify({ required: el.dataset.value !== "true" }) }); await showProject(projectId); });
  document.querySelectorAll(".remove-task").forEach(el => el.onclick = async () => { if (confirm("移除这项任务？标准模板不会受到影响。")) { await api(`/tasks/${el.dataset.tid}`, { method: "DELETE" }); await showProject(projectId); } });
  document.querySelectorAll("[data-edit-task]").forEach(form => form.onsubmit = async event => { event.preventDefault(); const data = new FormData(form); const payload = { owner: data.get("owner").trim() || null, status: data.get("status"), start_date: data.get("start_date"), deadline: data.get("deadline"), progress_mode: data.get("progress_mode"), progress_percent: Number(data.get("progress_percent") || 0), progress_note: data.get("progress_note").trim() || null, completion_criteria: data.get("completion_criteria").trim() || null, notes: data.get("notes").trim() || null }; if (data.has("quality_score")) payload.quality_score = data.get("quality_score") ? Number(data.get("quality_score")) : null; if (data.has("retrospective_note")) payload.retrospective_note = data.get("retrospective_note").trim() || null; try { await api(`/api/v2/tasks/${form.dataset.editTask}`, { method: "PATCH", body: JSON.stringify(payload) }); await showProject(projectId); notify("任务已保存", true); } catch (error) { notify(error.message); } });
  document.querySelectorAll(".add-task").forEach(el => el.onclick = () => { $(`[data-task-form="${el.dataset.mid}"]`).hidden = false; el.hidden = true; });
  document.querySelectorAll(".cancel-task").forEach(el => el.onclick = () => { const taskForm = el.closest("form"); taskForm.hidden = true; $(`.add-task[data-mid="${taskForm.dataset.taskForm}"]`).hidden = false; });
  document.querySelectorAll("[data-task-form]").forEach(taskForm => taskForm.onsubmit = async event => { event.preventDefault(); const data = new FormData(taskForm); await api(`/projects/${projectId}/tasks`, { method: "POST", body: JSON.stringify({ title: data.get("title").trim(), owner: data.get("owner").trim() || null, required: data.get("required") === "on", project_milestone_id: taskForm.dataset.taskForm }) }); await showProject(projectId); });
}

function bindSubtaskEvents(projectId) {
  document.querySelectorAll(".save-all-subtasks").forEach(button => button.onclick = () => saveAllSubtasks(button, projectId));
  document.querySelectorAll("[data-subtask-id]").forEach(checkbox => checkbox.onchange = async () => {
    const taskEditor = checkbox.closest("[data-edit-task]");
    if (taskEditor) state.openTaskEditors.add(taskEditor.dataset.editTask);
    try {
      await api(`/api/v2/subtasks/${checkbox.dataset.subtaskId}`, { method: "PATCH", body: JSON.stringify({ status: checkbox.checked ? "done" : "todo" }) });
      await showProject(projectId);
    } catch (error) { notify(`小任务更新失败：${error.message}`); }
  });
  document.querySelectorAll(".add-subtask").forEach(addButton => addButton.onclick = async () => {
    const wrapper = addButton.closest("[data-subtask-form]");
    const taskId = wrapper.dataset.subtaskForm;
    const title = wrapper.querySelector('[name="subtask_title"]').value.trim();
    const startDate = wrapper.querySelector('[name="subtask_start"]').value;
    const deadline = wrapper.querySelector('[name="subtask_deadline"]').value;
    if (!title) return notify("请填写子任务名称");
    if (!startDate || !deadline) return notify("请填写子任务开始和截止日期");
    try {
      addButton.disabled = true; addButton.textContent = "添加中…";
      state.openTaskEditors.add(taskId);
      await api(`/api/v2/tasks/${taskId}/subtasks`, { method: "POST", body: JSON.stringify({ title, start_date: startDate, deadline }) });
      await showProject(projectId);
      notify(`子任务“${title}”已添加，可以继续添加`, true);
    } catch (error) {
      addButton.disabled = false; addButton.textContent = "＋ 添加子任务";
      notify(`子任务添加失败：${error.message}`);
    }
  });
}

async function saveSubtask(saveButton, projectId) {
  try {
    const id = saveButton.dataset.subtaskSave;
    const taskEditor = saveButton.closest("[data-edit-task]");
    const item = saveButton.closest(".subtask-item");
    const progress = Number(item.querySelector("[data-subtask-progress]").value || 0);
    const startDate = item.querySelector("[data-subtask-start]").value;
    const deadline = item.querySelector("[data-subtask-deadline]").value;
    if (!startDate || !deadline) return notify("请填写小任务开始和截止日期");
    if (taskEditor) state.openTaskEditors.add(taskEditor.dataset.editTask);
    const label = saveButton.closest(".subtask-save-control");
    saveButton.disabled = true; label.querySelector("span").textContent = "保存中…";
    await api(`/api/v2/subtasks/${id}`, { method: "PATCH", body: JSON.stringify({ start_date: startDate, deadline, progress_percent: progress, status: progress >= 100 ? "done" : progress > 0 ? "in_progress" : "todo" }) });
    await showProject(projectId);
    notify("小任务已保存，主任务进度已自动更新", true);
  } catch (error) {
    saveButton.disabled = false; saveButton.checked = false; saveButton.closest(".subtask-save-control").querySelector("span").textContent = "保存小任务";
    notify(`小任务保存失败：${error.message}`);
  }
}

async function saveAllSubtasks(button, projectId) {
  const taskEditor = button.closest("[data-edit-task]");
  const items = [...taskEditor.querySelectorAll("[data-subtask-item]")];
  if (!items.length) return;
  state.openTaskEditors.add(taskEditor.dataset.editTask);
  try {
    button.disabled = true; button.textContent = "保存中…";
    await Promise.all(items.map(item => {
      const id = item.dataset.subtaskItem;
      const progress = Number(item.querySelector("[data-subtask-progress]").value || 0);
      const startDate = item.querySelector("[data-subtask-start]").value;
      const deadline = item.querySelector("[data-subtask-deadline]").value;
      if (!startDate || !deadline) throw new Error("请填写所有小任务的开始和截止日期");
      return api(`/api/v2/subtasks/${id}`, { method: "PATCH", body: JSON.stringify({ start_date: startDate, deadline, progress_percent: progress, status: progress >= 100 ? "done" : progress > 0 ? "in_progress" : "todo" }) });
    }));
    await showProject(projectId);
    notify(`已保存 ${items.length} 个小任务，主任务进度已自动更新`, true);
  } catch (error) {
    button.disabled = false; button.textContent = "保存全部小任务";
    notify(`小任务保存失败：${error.message}`);
  }
}

function hideOperationSections(exceptId) {
  ["operations-section", "training-map-section", "alerts-section", "resources-section"].forEach(id => { if (id !== exceptId) $(`#${id}`).hidden = true; });
}

function arrangeWorkspaceSections() {
  const main = $(".main-content");
  const firstDialog = main.querySelector("dialog");
  const orderedSections = [
    $("#training-map-section"),
    $("#create-section"),
    $(".program-layout"),
    $(".metrics-grid"),
    $(".dashboard-grid"),
    $("#operations-section"),
    $("#alerts-section"),
    $("#project-detail"),
    $("#requirements-section"),
    $("#resources-section"),
  ];
  orderedSections.forEach(section => main.insertBefore(section, firstDialog));
}

function programSelectorOptions(selectedId) {
  return state.programs.filter(item => item.status !== "archived").map(item => `<option value="${item.id}" ${item.id === selectedId ? "selected" : ""}>${escapeHtml(item.name)}</option>`).join("");
}

async function showOperations(programId = state.program?.id) {
  if (!programId) return notify("请先选择一个培养项目");
  hideOperationSections("operations-section");
  const [data, retrospective] = await Promise.all([api(`/api/v2/programs/${programId}/dashboard`), api(`/api/v2/programs/${programId}/retrospective`)]);
  $("#operations-section").hidden = false; $("#operations-title").textContent = `${data.name}｜运营总览`;
  $("#operations-program").innerHTML = programSelectorOptions(programId);
  $("#export-excel").href = `/api/v2/programs/${programId}/exports/operations.xlsx`; $("#export-ics").href = `/api/v2/programs/${programId}/calendar.ics`;
  $("#operations-metrics").innerHTML = [
    ["任务进度", `${data.progress}%`, `时间进度 ${data.time_progress}%`], ["健康度", data.health.label, `${data.health.open_alert_count} 条开放预警`],
    ["培养活动", data.outcomes.activity_count, `${data.outcomes.completed_activity_count} 项已完成`], ["覆盖人数", data.outcomes.participant_count || 0, "来自项目或届别"],
    ["预计预算", `¥${Number(data.specialty.budget.estimated_total).toLocaleString("zh-CN")}`, `${data.specialty.budget.progress}% 已通过`],
  ].map(([label,value,note]) => `<article><span>${label}</span><strong class="health-${data.health.code}">${value}</strong><small>${note}</small></article>`).join("");
  const cohortRows = data.cohorts.map(x => `<article class="requirement-card"><strong>届别｜${escapeHtml(x.name)}</strong><span>${x.participant_count} 人 · ${x.progress}% · ${x.completed_activity_count}/${x.activity_count} 项活动完成</span></article>`).join("");
  const activityRows = data.activities.map(x => `<article class="requirement-card"><strong>${escapeHtml(x.name)}</strong><span>${formatDate(x.start_date)}—${formatDate(x.end_date)} · ${x.progress}% · ${escapeHtml(x.owner_name || "未填写负责人")}</span></article>`).join("");
  $("#operations-activities").innerHTML = cohortRows + activityRows || '<div class="empty-mini">暂无活动或届别</div>';
  const focusDates=[...new Set(data.focus.map(x=>x.date))];
  $("#operations-focus").innerHTML = focusDates.length ? focusDates.map(day=>`<article class="focus-date-card"><strong>${formatDate(day)}</strong><ul>${data.focus.filter(x=>x.date===day).map(x=>`<li><span>${escapeHtml(x.title)}</span><small>${x.type} · ${escapeHtml(x.activity_name)}</small></li>`).join("")}</ul></article>`).join("") : '<div class="empty-mini">未来 7 天暂无重点事项</div>';
  $("#retrospective-view").innerHTML = `<article class="requirement-card"><strong>周期与交付</strong><span>${retrospective.task_count} 项任务，完成 ${retrospective.completed_task_count} 项，当前逾期 ${retrospective.overdue_task_count} 项；平均质量评分 ${retrospective.average_quality_score ?? "暂无"}</span></article>${retrospective.retrospective_notes.map(x => `<article class="requirement-card"><strong>${escapeHtml(x.task_title)}｜${x.quality_score || "未评分"}</strong><span>${escapeHtml(x.note || "暂无复盘反馈")}</span></article>`).join("")}`;
  $("#operations-section").scrollIntoView({behavior:"smooth",block:"start"});
}

function renderCenterMonthCalendar(year, month, items, kind) {
  const first=new Date(year,month-1,1),days=new Date(year,month,0).getDate(),leading=(first.getDay()+6)%7;
  const palette=["#8179e8","#27a477","#e08b3e","#3c8fd1","#d65c7a","#6d7f91"],programIds=[...new Set(items.map(item=>item.program_id))],color=id=>palette[Math.max(0,programIds.indexOf(id))%palette.length];
  const cells=Array.from({length:leading},()=>'<div class="center-calendar-day outside"></div>');
  for(let day=1;day<=days;day++){const iso=`${year}-${String(month).padStart(2,"0")}-${String(day).padStart(2,"0")}`,active=items.filter(item=>item.start_date<=iso&&item.end_date>=iso);cells.push(`<div class="center-calendar-day"><b>${day}</b><div>${active.slice(0,3).map(item=>`<span class="center-calendar-event" style="--project-color:${color(item.program_id)}" title="${escapeHtml(item.program_name)}｜${escapeHtml(item.name||item.title)}"><i></i>${escapeHtml(item.program_name)}｜${escapeHtml(item.name||item.title)}${kind==="publicity"&&item.publish_date===iso?" · 发布":""}</span>`).join("")}${active.length>3?`<small>另有 ${active.length-3} 项</small>`:""}</div></div>`);}
  while(cells.length%7)cells.push('<div class="center-calendar-day outside"></div>');
  return `<div class="center-month-calendar"><div class="center-calendar-weekdays">${["一","二","三","四","五","六","日"].map(x=>`<span>${x}</span>`).join("")}</div><div class="center-calendar-grid">${cells.join("")}</div></div>`;
}

async function showTrainingMap() {
  hideOperationSections("training-map-section"); $("#training-map-section").hidden = false;
  document.querySelector(".program-layout").before($("#training-map-section"));
  const year = Number($("#map-year").value || new Date().getFullYear());
  const month=Number($("#map-month").value||0),data=await api(`/api/v2/training-map?year=${year}&group_by=program`),groups=[...new Set(data.items.map(x=>x.group))];
  const overlaps=(item,m)=>{const start=new Date(`${item.start_date}T00:00:00`),end=new Date(`${item.end_date}T00:00:00`),first=new Date(year,m-1,1),last=new Date(year,m,0);return start<=last&&end>=first;};
  if(month){const items=data.items.filter(item=>overlaps(item,month)).sort((a,b)=>a.start_date.localeCompare(b.start_date));$("#training-map").innerHTML=`<div class="calendar-detail-head"><strong>${year}年${month}月培训日历</strong><span>${items.length} 项活动</span></div>${renderCenterMonthCalendar(year,month,items,"training")}`;}else{const heads=["培养项目",...Array.from({length:12},(_,i)=>`<button type="button" data-open-map-month="${i+1}">${i+1}月</button>`)].map(x=>`<div class="map-cell head">${x}</div>`).join("");$("#training-map").innerHTML=`<div class="map-table">${heads}${groups.flatMap(name=>[`<div class="map-cell head">${escapeHtml(name)}</div>`,...Array.from({length:12},(_,i)=>`<div class="map-cell">${data.items.filter(x=>x.group===name&&overlaps(x,i+1)).map(x=>`<span class="map-event">${escapeHtml(x.name)}<br>${formatDate(x.start_date)}—${formatDate(x.end_date)}</span>`).join("")}</div>`)]).join("")}</div>`;document.querySelectorAll("[data-open-map-month]").forEach(button=>button.onclick=()=>{$("#map-month").value=button.dataset.openMapMonth;showTrainingMap();});}
  $("#training-map-section").scrollIntoView({behavior:"smooth",block:"start"});
}

async function showAlerts(evaluate = false, programId = state.program?.id) {
  if (!programId) return notify("请先选择一个培养项目");
  hideOperationSections("alerts-section"); $("#alerts-section").hidden = false;
  $("#alerts-program").innerHTML = programSelectorOptions(programId);
  const rows = await api(evaluate ? `/api/v2/programs/${programId}/alerts/evaluate` : `/api/v2/programs/${programId}/alerts`, evaluate ? {method:"POST"} : {});
  const alertGroups=[["risk","风险"],["attention","关注"]];
  $("#alerts-list").innerHTML = rows.length ? `<div class="alert-bulk"><label><input id="select-all-alerts" type="checkbox">一键全选</label><select id="bulk-alert-action"><option value="acknowledge">批量确认</option><option value="resolve">批量解决</option><option value="dismiss">批量忽略</option></select><button id="apply-alert-bulk" class="text-button">同步操作</button><span id="alert-selected-count">已选 0 项</span></div><div class="alert-groups">${alertGroups.map(([severity,label])=>{const items=rows.filter(x=>x.severity===severity);return `<section class="alert-group ${severity}"><div class="alert-group-title"><h3>${label}</h3><span>${items.length}</span></div>${items.length?`<ul>${items.map(x=>`<li><input class="alert-select" data-alert-select="${x.id}" type="checkbox" aria-label="选择${escapeHtml(x.title)}"><div><strong>• ${escapeHtml(x.title)}</strong><p>${escapeHtml(x.reason)}</p><small>建议：${escapeHtml(x.recommended_action)}</small></div><select class="alert-state" data-alert="${x.id}"><option value="">调整状态</option><option value="acknowledge">确认</option><option value="resolve">解决</option><option value="dismiss">忽略</option></select></li>`).join("")}</ul>`:'<div class="empty-mini">暂无</div>'}</section>`;}).join("")}</div>` : '<div class="empty-mini">当前没有开放预警，项目健康度正常</div>';
  document.querySelectorAll(".alert-state").forEach(select => select.onchange = async () => { if(!select.value)return; await api(`/api/v2/alerts/${select.dataset.alert}/${select.value}`,{method:"POST"}); await showAlerts(false); });
  document.querySelectorAll(".alert-action").forEach(button => button.onclick = async () => { await api(`/api/v2/alerts/${button.dataset.alert}/${button.dataset.action}`,{method:"POST"}); await showAlerts(false); });
  const selections=[...document.querySelectorAll(".alert-select")],count=$("#alert-selected-count"),all=$("#select-all-alerts");
  const updateAlertCount=()=>{const n=selections.filter(x=>x.checked).length;if(count)count.textContent=`已选 ${n} 项`;if(all){all.checked=n===selections.length&&n>0;all.indeterminate=n>0&&n<selections.length;}};
  selections.forEach(input=>input.onchange=updateAlertCount);
  if(all)all.onchange=()=>{selections.forEach(input=>input.checked=all.checked);updateAlertCount();};
  if($("#apply-alert-bulk")) $("#apply-alert-bulk").onclick=async()=>{const ids=selections.filter(x=>x.checked).map(x=>x.dataset.alertSelect);if(!ids.length)return notify("请先选择需要同步操作的预警");const action=$("#bulk-alert-action").value;await Promise.all(ids.map(id=>api(`/api/v2/alerts/${id}/${action}`,{method:"POST"})));await showAlerts(false);notify(`已同步处理 ${ids.length} 条预警`,true);};
  $("#alerts-section").scrollIntoView({behavior:"smooth",block:"start"});
}

async function showResources(programId = state.program?.id) {
  if (!programId) return notify("请先选择一个培养项目");
  hideOperationSections("resources-section"); $("#resources-section").hidden = false;
  $("#resources-program").innerHTML = programSelectorOptions(programId);
  const rows = await api("/api/v2/resources");
  const taskSelect = $('#resource-link-form [name="task_id"]'), resourceSelect = $('#resource-link-form [name="resource_id"]');
  const tasks = state.project?.tasks?.filter(x => x.status !== "cancelled") || [];
  taskSelect.innerHTML = tasks.length ? tasks.map(x => `<option value="${x.id}">${escapeHtml(x.title)}</option>`).join("") : '<option value="">请先选择一个培养活动</option>';
  resourceSelect.innerHTML = rows.length ? rows.map(x => `<option value="${x.id}">${escapeHtml(x.title)}</option>`).join("") : '<option value="">请先添加资料</option>';
  $("#resources-list").innerHTML = rows.length ? rows.map(x => `<article class="requirement-card"><strong>${escapeHtml(x.title)}｜${x.is_upload ? "本地文件" : "链接"}</strong><a href="${escapeHtml(x.url)}" target="_blank" rel="noopener">${x.is_upload ? "下载文件" : "打开资料"}</a><span>${x.file_name ? `${escapeHtml(x.file_name)} · ` : ""}${escapeHtml(x.description || "暂无说明")} · ${escapeHtml(x.owner_name || "未填写负责人")}</span>${x.linked_task_count ? `<button type="button" class="text-button resource-jump" data-resource-jump="${x.id}">查看关联节点（${x.linked_task_count}）</button>` : '<small>尚未关联节点</small>'}</article>`).join("") : '<div class="empty-mini">暂无 SOP 或资料</div>';
  document.querySelectorAll(".resource-jump").forEach(button=>button.onclick=async()=>{const links=await api(`/api/v2/resources/${button.dataset.resourceJump}/tasks`);if(!links.length)return;const first=links[0];await showProgram(first.program_id);await showProject(first.activity_id);const task=state.project.tasks.find(item=>item.id===first.task_id);if(task)await openTaskDialog(task);});
  await loadTaskResourceLinks();
  $("#resources-section").scrollIntoView({behavior:"smooth",block:"start"});
}

async function loadTaskResourceLinks() {
  const taskId = $('#resource-link-form [name="task_id"]').value;
  const rows = taskId ? await api(`/api/v2/tasks/${taskId}/resources`) : [];
  $("#task-resource-links").innerHTML = rows.length ? rows.map(x => `<article class="requirement-card"><strong>已关联｜${escapeHtml(x.title)}</strong><span>${x.relation_type === "deliverable" ? "交付物" : "参考资料"}</span></article>`).join("") : '<div class="empty-mini">当前任务暂无关联资料</div>';
}

function toggleCreate(show) { $("#create-section").hidden = !show; if (show) $("#name").focus(); }
$("#quick-create").onclick = () => toggleCreate(true); $("#close-create").onclick = () => toggleCreate(false);
document.querySelectorAll(".nav-item").forEach(button => button.onclick = () => { document.querySelectorAll(".nav-item").forEach(b => b.classList.remove("active")); button.classList.add("active"); if (button.dataset.view === "create") toggleCreate(true); if (button.dataset.view === "timeline" && state.project) { $("#project-detail").hidden = false; $("#project-detail").scrollIntoView({ behavior: "smooth" }); } if (button.dataset.view === "requirements") openRequirements(); if (button.dataset.view === "operations") showOperations(); if (button.dataset.view === "training-map") showTrainingMap(); if (button.dataset.view === "alerts") showAlerts(); if (button.dataset.view === "resources") showResources(); });
$("#prev-month").onclick = () => { state.calendarDate = new Date(state.calendarDate.getFullYear(), state.calendarDate.getMonth() - 1, 1); renderCalendar(); };
$("#next-month").onclick = () => { state.calendarDate = new Date(state.calendarDate.getFullYear(), state.calendarDate.getMonth() + 1, 1); renderCalendar(); };
$("#today-button").onclick = () => { state.calendarDate = new Date(); selectDate(isoDate(new Date())); };

$("#show-add-milestone").onclick = () => { $("#milestone-form").hidden = false; $("#show-add-milestone").hidden = true; };
$("#cancel-add-milestone").onclick = () => { $("#milestone-form").hidden = true; $("#show-add-milestone").hidden = false; };
$("#milestone-form").onsubmit = async event => { event.preventDefault(); const submittedForm = event.currentTarget; const data = new FormData(submittedForm); await api(`/projects/${state.project.id}/milestones`, { method: "POST", body: JSON.stringify({ name: data.get("name").trim(), deadline: data.get("deadline"), required: data.get("required") === "on" }) }); submittedForm.reset(); $("#cancel-add-milestone").click(); await showProject(state.project.id); };
document.querySelectorAll(".workspace-dialog").forEach(dialog => { dialog.addEventListener("click", event => { if (event.target === dialog) dialog.close(); }); dialog.querySelectorAll(".close-dialog").forEach(button => button.onclick = () => dialog.close()); });
$("#task-detail-form").onsubmit = async event => { event.preventDefault(); const form=event.currentTarget,data=new FormData(form),payload={owner:data.get("owner").trim()||null,status:data.get("status"),start_date:data.get("start_date"),deadline:data.get("deadline"),progress_mode:data.get("progress_mode"),progress_percent:Number(data.get("progress_percent")||0),progress_note:data.get("progress_note").trim()||null,completion_criteria:data.get("completion_criteria").trim()||null,notes:data.get("notes").trim()||null,quality_score:data.get("quality_score")?Number(data.get("quality_score")):null,retrospective_note:data.get("retrospective_note").trim()||null}; try { await api(`/api/v2/tasks/${form.dataset.taskId}`,{method:"PATCH",body:JSON.stringify(payload)}); $("#task-detail-dialog").close(); await showProject(state.project.id); notify("节点详情已保存",true); } catch(error){notify(`节点详情保存失败：${error.message}`);} };
$("#subtask-dialog-form").onsubmit = async event => { event.preventDefault(); const form=event.currentTarget,data=new FormData(form),taskId=data.get("task_id"); try { await api(`/api/v2/tasks/${taskId}/subtasks`,{method:"POST",body:JSON.stringify({title:data.get("title").trim(),owner:data.get("owner").trim()||null,start_date:data.get("start_date"),deadline:data.get("deadline"),notes:data.get("notes").trim()||null})}); await showProject(state.project.id); const task=state.project.tasks.find(x=>x.id===taskId); renderSubtaskDialog(task); form.reset(); form.querySelector('[name="task_id"]').value=taskId; form.querySelector('[name="start_date"]').value=task.start_date; form.querySelector('[name="deadline"]').value=task.deadline; notify("分支任务已添加，可继续添加",true); } catch(error){notify(`分支任务添加失败：${error.message}`);} };

$("#project-form").onsubmit = async event => { event.preventDefault(); const submittedForm = event.currentTarget; try { const program = await api("/api/v2/programs", { method: "POST", body: JSON.stringify({ name: $("#name").value.trim(), program_type: $("#program-type").value, owner_name: $("#program-owner").value.trim() || null, start_date: $("#start-date").value, end_date: $("#end-date").value }) }); submittedForm.reset(); toggleCreate(false); await showProgram(program.id); notify("培养项目已创建", true); } catch (error) { notify(error.message); } };

$("#show-cohort-form").onclick = () => { $("#cohort-form").hidden = !$("#cohort-form").hidden; };
$("#cohort-form").onsubmit = async event => { event.preventDefault(); const form = event.currentTarget, data = new FormData(form); try { await api(`/api/v2/programs/${state.program.id}/cohorts`, { method: "POST", body: JSON.stringify({ name: data.get("name").trim(), start_date: data.get("start_date"), end_date: data.get("end_date"), participant_count: Number(data.get("participant_count") || 0) }) }); form.reset(); form.hidden = true; await showProgram(state.program.id); notify("届别已添加", true); } catch (error) { notify(error.message); } };
$("#show-class-form").onclick = () => { const form=$("#class-form"); form.hidden=!form.hidden; if(!form.hidden){form.querySelector('[name="start_date"]').value=state.program.start_date;form.querySelector('[name="end_date"]').value=state.program.end_date;form.querySelector('[name="name"]').focus();} };
function editClass(item){const form=$("#class-form");form.hidden=false;form.elements.class_id.value=item.id;form.elements.name.value=item.name;form.elements.start_date.value=item.start_date||"";form.elements.end_date.value=item.end_date||"";form.elements.participant_count.value=item.participant_count||0;form.elements.business_unit.value=item.business_unit||"";form.elements.name.focus();}
$("#cancel-class-edit").onclick=()=>{$("#class-form").reset();$("#class-form").hidden=true;};
$("#class-form").onsubmit = async event => { event.preventDefault(); const form=event.currentTarget,data=new FormData(form),classId=data.get("class_id"),payload={name:data.get("name").trim(),start_date:data.get("start_date")||null,end_date:data.get("end_date")||null,participant_count:Number(data.get("participant_count")||0),business_unit:data.get("business_unit").trim()||null}; try { await api(classId?`/api/v2/classes/${classId}`:`/api/v2/programs/${state.program.id}/classes`,{method:classId?"PATCH":"POST",body:JSON.stringify(payload)}); form.reset();form.hidden=true;await showProgram(state.program.id);notify(classId?"班级已更新":"班级已添加",true); } catch(error){notify(`班级保存失败：${error.message}`);} };
function resetActivityForm(){const form=$("#activity-form");form.reset();form.elements.activity_id.value="";form.elements.activity_type.disabled=false;$("#activity-form-help").textContent="线下培训会以开始日期作为标准节点倒推基准，并自动使用 Offline Training v1.0。";}
function editActivity(item){if(!item)return;const form=$("#activity-form");form.hidden=false;form.elements.activity_id.value=item.id;form.elements.name.value=item.name;form.elements.activity_type.value=item.activity_type||item.type;form.elements.activity_type.disabled=true;form.elements.start_date.value=item.start_date||"";form.elements.end_date.value=item.end_date||item.start_date||"";form.elements.cohort_id.value=item.cohort_id||"";form.elements.owner_name.value=item.owner_name||"";$("#activity-form-help").textContent="活动类型和既有模板保持不变；修改活动信息不会重建或覆盖现有节点任务。";form.elements.name.focus();}
$("#show-activity-form").onclick = () => { const form=$("#activity-form");if(!form.hidden){form.hidden=true;resetActivityForm();return;}resetActivityForm();form.hidden=false;form.elements.start_date.value=state.program.start_date;form.elements.end_date.value=state.program.end_date;form.elements.name.focus(); };
$("#cancel-activity-edit").onclick=()=>{resetActivityForm();$("#activity-form").hidden=true;};
$("#activity-form").onsubmit = async event => { event.preventDefault(); const form = event.currentTarget, data = new FormData(form), activityId=data.get("activity_id"), type = form.elements.activity_type.value, startDate = data.get("start_date"); const basePayload={name:data.get("name").trim(),start_date:startDate,end_date:data.get("end_date"),cohort_id:data.get("cohort_id")||null,owner_name:data.get("owner_name").trim()||null};const payload=activityId?basePayload:{...basePayload,activity_type:type,event_date:type==="offline_training"?startDate:null,template_id:type==="offline_training"?"tpl_offline_training_v1_0":null}; try { const activity = await api(activityId?`/api/v2/activities/${activityId}`:`/api/v2/programs/${state.program.id}/activities`, { method: activityId?"PATCH":"POST", body: JSON.stringify(payload) }); resetActivityForm();form.hidden = true; state.project = null; await showProgram(state.program.id); await showProject(activity.id); notify(activityId?"培养活动已更新":type === "offline_training" ? "线下培训活动及标准节点已创建" : "轻量活动已创建", true); } catch (error) { notify(`活动保存失败：${error.message}`); } };
$("#archive-program").onclick = async () => { if (!state.program) return; const restoring = state.program.status === "archived"; if (!confirm(`${restoring ? "恢复" : "归档"}培养项目“${state.program.name}”？`)) return; if (restoring) await api(`/api/v2/programs/${state.program.id}`, { method: "PATCH", body: JSON.stringify({ status: "active" }) }); else await api(`/api/v2/programs/${state.program.id}`, { method: "DELETE" }); state.program = null; state.project = null; $("#program-detail").hidden = true; $("#project-detail").hidden = true; await loadPrograms(); notify(restoring ? "项目已恢复" : "项目已归档，可在已归档项目中查看或恢复", true); };
$("#show-archived-programs").onclick = async event => { state.showArchivedPrograms = !state.showArchivedPrograms; event.currentTarget.textContent = state.showArchivedPrograms ? "只看进行中项目" : "查看已归档项目"; state.program = null; state.project = null; $("#program-detail").hidden = true; $("#project-detail").hidden = true; await loadPrograms(); if (state.programs.length) await showProgram(state.programs[0].id); };
$("#open-requirements").onclick = () => openRequirements(state.program.id);
$("#open-operations").onclick = () => showOperations(state.program.id);
$("#edit-program").onclick=()=>{const p=state.program,form=$("#program-edit-form");["name","owner_name","start_date","end_date","business_unit","participant_count","current_phase"].forEach(name=>form.elements[name].value=p[name]??"");$("#program-edit-dialog").showModal();};
$("#program-edit-form").onsubmit=async event=>{event.preventDefault();const form=event.currentTarget,data=new FormData(form);await api(`/api/v2/programs/${state.program.id}`,{method:"PATCH",body:JSON.stringify({name:data.get("name").trim(),owner_name:data.get("owner_name").trim()||null,start_date:data.get("start_date"),end_date:data.get("end_date"),business_unit:data.get("business_unit").trim()||null,participant_count:Number(data.get("participant_count")||0),current_phase:data.get("current_phase").trim()||null})});$("#program-edit-dialog").close();await showProgram(state.program.id);notify("培训项目已更新",true);};
$("#close-requirements").onclick = () => { $("#requirements-section").hidden = true; };
$("#close-project-detail").onclick = () => { $("#project-detail").hidden = true; };
$("#requirements-program").onchange = async event => { const programId = event.currentTarget.value; $("#requirements-activity").value = ""; if (state.program?.id !== programId) await showProgram(programId); else { state.requirementsProgramId = programId; await loadRequirements(); } };
$("#operations-program").onchange = async event => { const programId = event.currentTarget.value; if (state.program?.id !== programId) await showProgram(programId); else await showOperations(programId); };
$("#alerts-program").onchange = async event => { const programId = event.currentTarget.value; if (state.program?.id !== programId) await showProgram(programId); else await showAlerts(false, programId); };
$("#resources-program").onchange = async event => { const programId = event.currentTarget.value; if (state.program?.id !== programId) await showProgram(programId); else await showResources(programId); };
$("#apply-requirement-filters").onclick = () => loadRequirements();
document.querySelectorAll("[data-requirement-tab]").forEach(button => button.onclick = () => { document.querySelectorAll("[data-requirement-tab]").forEach(item => item.classList.toggle("active", item === button)); document.querySelectorAll("[data-requirement-pane]").forEach(pane => pane.hidden = pane.dataset.requirementPane !== button.dataset.requirementTab); });
document.querySelectorAll(".summary-jump").forEach(button=>button.onclick=()=>{document.querySelector(`[data-requirement-tab="${button.dataset.summaryTab}"]`).click();document.querySelector(`[data-requirement-pane="${button.dataset.summaryTab}"]`).scrollIntoView({behavior:"smooth",block:"start"});});
$("#budget-sheet-form").onsubmit = async event => { event.preventDefault(); const form = event.currentTarget, data = new FormData(form), activityId = data.get("activity_id") || null; try { await api("/api/v2/budget-sheets", { method: "POST", body: JSON.stringify({ program_id: state.requirementsProgramId, activity_id: activityId, owner_name: data.get("owner_name").trim() || null, planned_apply_date: data.get("planned_apply_date") || null, status: data.get("status"), notes: data.get("notes").trim() || null }) }); form.reset(); $("#requirements-activity").value = ""; await loadRequirements(); requirementNotify("预算申请表已创建并显示在右侧列表中"); $("#budget-sheet-list").scrollIntoView({ behavior: "smooth", block: "center" }); } catch (error) { requirementNotify(`预算表创建失败：${error.message}`, false); } };
$("#budget-edit-form").onsubmit=async event=>{event.preventDefault();const form=event.currentTarget,data=new FormData(form);await api(`/api/v2/budget-sheets/${data.get("id")}`,{method:"PATCH",body:JSON.stringify({owner_name:data.get("owner_name").trim()||null,planned_apply_date:data.get("planned_apply_date")||null,status:data.get("status"),notes:data.get("notes").trim()||null})});$("#budget-edit-dialog").close();await loadRequirements();requirementNotify("预算表表头已更新");};
$("#requirement-edit-form").onsubmit=async event=>{event.preventDefault();const form=event.currentTarget,data=new FormData(form),kind=form.dataset.kind,isMaterial=kind==="material";const payload=isMaterial?{activity_id:data.get("activity_id")||null,name:data.get("name").trim(),quantity:optionalNumber(data.get("quantity")),specification:data.get("specification").trim()||null,owner_name:data.get("owner_name").trim()||null,content_due_date:data.get("content_due_date")||null,expected_delivery_date:data.get("expected_delivery_date")||null,status:data.get("status"),notes:data.get("notes").trim()||null,include_in_budget:data.get("include_in_budget")==="on"}:{activity_id:data.get("activity_id")||null,content_type:data.get("content_type").trim(),format:data.get("format").trim()||null,quantity:Number(data.get("quantity")||1),owner_name:data.get("owner_name").trim()||null,start_date:data.get("start_date")||null,expected_completion_date:data.get("expected_completion_date")||null,publish_date:data.get("publish_date")||null,status:data.get("status"),notes:data.get("notes").trim()||null};await api(`/api/v2/${isMaterial?"material-requirements":"publicity-requirements"}/${form.dataset.itemId}`,{method:"PATCH",body:JSON.stringify(payload)});$("#requirement-edit-dialog").close();await loadRequirements();if(!isMaterial&&!$("#publicity-calendar").hidden)await showPublicityCalendar();notify("需求已更新",true);};
$("#budget-item-form").onsubmit = async event => { event.preventDefault(); const form = event.currentTarget, data = new FormData(form); try { await api(`/api/v2/budget-sheets/${data.get("budget_sheet_id")}/items`, { method: "POST", body: JSON.stringify({ expense_name: data.get("expense_name").trim(), reference_price_id: data.get("reference_price_id") || null, quantity: Number(data.get("quantity") || 0), estimated_unit_price: optionalNumber(data.get("estimated_unit_price")), estimated_amount: optionalNumber(data.get("estimated_amount")), unit: data.get("unit").trim() || null }) }); form.reset(); form.hidden = true; await loadRequirements(); notify("预算项已添加", true); } catch (error) { notify(error.message); } };
$("#cancel-budget-item").onclick = () => { $("#budget-item-form").hidden = true; };
$("#material-form").onsubmit = async event => { event.preventDefault(); const form = event.currentTarget, data = new FormData(form); try { await api("/api/v2/material-requirements", { method: "POST", body: JSON.stringify({ program_id: state.requirementsProgramId, activity_id: data.get("activity_id") || null, budget_item_id: data.get("budget_item_id") || null, name: data.get("name").trim(), quantity: optionalNumber(data.get("quantity")), specification: data.get("specification").trim() || null, owner_name: data.get("owner_name").trim() || null, content_due_date: data.get("content_due_date") || null, expected_delivery_date: data.get("expected_delivery_date") || null, status: data.get("status"), notes: data.get("notes").trim() || null, include_in_budget: data.get("include_in_budget") === "on" }) }); form.reset(); $("#requirements-activity").value=""; await loadRequirements(); notify("物料需求已添加", true); } catch (error) { notify(error.message); } };
$("#publicity-form").onsubmit = async event => { event.preventDefault(); const form = event.currentTarget, data = new FormData(form); try { await api("/api/v2/publicity-requirements", { method: "POST", body: JSON.stringify({ program_id: state.requirementsProgramId, activity_id: data.get("activity_id") || null, budget_item_id: data.get("budget_item_id") || null, content_type: data.get("content_type").trim(), format: data.get("format").trim() || null, quantity: Number(data.get("quantity") || 1), owner_name: data.get("owner_name").trim() || null, start_date: data.get("start_date") || null, expected_completion_date: data.get("expected_completion_date") || null, publish_date:data.get("publish_date")||null,status: data.get("status"), notes: data.get("notes").trim() || null }) }); form.reset(); $("#requirements-activity").value=""; await loadRequirements(); if(!$("#publicity-calendar").hidden)await showPublicityCalendar(); notify("宣传需求已添加并同步到排期", true); } catch (error) { notify(error.message); } };
document.querySelectorAll(".publicity-suggestion").forEach(button => button.onclick = async () => { const detail = await ensureRequirementProgramDetail(); const selected = $("#requirements-activity").value; const offline = detail.activities.find(item => item.id === selected && item.activity_type === "offline_training") || detail.activities.find(item => item.activity_type === "offline_training" && item.status !== "archived"); if (!offline) return notify("当前项目没有可关联的线下培训活动"); await api("/api/v2/publicity-requirements", { method: "POST", body: JSON.stringify({ program_id: state.requirementsProgramId, activity_id: offline.id, content_type: button.dataset.contentType, quantity: 1, status: "pending" }) }); await loadRequirements(); if(!$("#publicity-calendar").hidden)await showPublicityCalendar(); notify(`已为“${offline.name}”添加${button.dataset.contentType}`, true); });
$("#reference-price-form").onsubmit = async event => { event.preventDefault(); const form = event.currentTarget, data = new FormData(form); try { await api("/api/v2/reference-prices", { method: "POST", body: JSON.stringify({ expense_name: data.get("expense_name").trim(), price_type: data.get("price_type"), unit_price: optionalNumber(data.get("unit_price")), min_price: optionalNumber(data.get("min_price")), max_price: optionalNumber(data.get("max_price")), unit: data.get("unit").trim() || null, notes: data.get("notes").trim() || null }) }); form.reset(); await loadRequirements(); notify("参考价格已添加", true); } catch (error) { notify(error.message); } };
$("#close-operations").onclick = () => $("#operations-section").hidden = true;
$("#close-training-map").onclick = () => $("#training-map-section").hidden = true;
$("#close-alerts").onclick = () => $("#alerts-section").hidden = true;
$("#close-resources").onclick = () => $("#resources-section").hidden = true;
$("#map-year").value = new Date().getFullYear(); $("#refresh-map").onclick = () => showTrainingMap(); $("#map-month").onchange=()=>showTrainingMap();
$("#evaluate-alerts").onclick = () => showAlerts(true);
async function showPublicityCalendar(monthOverride){
  const container=$("#publicity-calendar"),existingYear=container.querySelector("[data-publicity-year]")?.value;
  const year=Number(existingYear||new Date().getFullYear()),existingMonth=container.querySelector("[data-publicity-month]")?.value||"",month=monthOverride===undefined?Number(existingMonth||0):Number(monthOverride||0);
  const rows=await api(`/api/v2/publicity-calendar?year=${year}`),palette=["#8179e8","#27a477","#e08b3e","#3c8fd1","#d65c7a","#6d7f91"],programs=[...new Set(rows.map(item=>item.program_id))],color=id=>palette[Math.max(0,programs.indexOf(id))%palette.length],unique=[...new Map(rows.map(item=>[item.id,item])).values()];
  container.hidden=false;
  const controls=`<div class="calendar-toolbar"><label>年度<input data-publicity-year type="number" min="2000" max="2100" value="${year}"></label><label>月份<select data-publicity-month><option value="">全年</option>${Array.from({length:12},(_,i)=>`<option value="${i+1}" ${month===i+1?"selected":""}>${i+1}月</option>`).join("")}</select></label><button type="button" class="text-button" data-refresh-publicity-calendar>刷新</button></div>`;
  if(month){const first=`${year}-${String(month).padStart(2,"0")}-01`,last=isoDate(new Date(year,month,0)),items=unique.filter(item=>{const start=item.start_date||item.production_deadline||item.publish_date,end=item.end_date||start;return start&&start<=last&&end>=first;}).map(item=>({...item,start_date:item.start_date||item.production_deadline||item.publish_date,end_date:item.end_date||item.publish_date||item.production_deadline||item.start_date})).sort((a,b)=>a.start_date.localeCompare(b.start_date));container.innerHTML=`<div class="subhead"><h3>${year}年${month}月宣传排期</h3><small>月历中可直接比较不同项目的制作和发布时间</small></div>${controls}${renderCenterMonthCalendar(year,month,items,"publicity")}`;}else{container.innerHTML=`<div class="subhead"><h3>${year} 培训中心宣传排期</h3><small>点击月份查看具体日期区间</small></div>${controls}<div class="publicity-calendar-grid">${Array.from({length:12},(_,m)=>{const items=rows.filter(item=>Number(String(item.date).slice(5,7))===m+1).sort((a,b)=>String(a.date).localeCompare(String(b.date)));return `<button type="button" class="publicity-month-card" data-publicity-open-month="${m+1}"><h4>${m+1}月</h4>${items.length?items.map(item=>`<div class="publicity-event" style="--project-color:${color(item.program_id)}"><i></i><span><b>${String(item.date).slice(5).replace("-","/")} · ${escapeHtml(item.date_type)}</b>${escapeHtml(item.program_name)}｜${escapeHtml(item.title)}</span></div>`).join(""):'<small>暂无排期</small>'}</button>`;}).join("")}</div>`;}
  container.querySelector("[data-refresh-publicity-calendar]").onclick=()=>showPublicityCalendar();container.querySelector("[data-publicity-month]").onchange=event=>showPublicityCalendar(event.currentTarget.value);container.querySelector("[data-publicity-year]").onchange=()=>showPublicityCalendar(month);container.querySelectorAll("[data-publicity-open-month]").forEach(button=>button.onclick=()=>showPublicityCalendar(button.dataset.publicityOpenMonth));container.scrollIntoView({behavior:"smooth",block:"start"});
}
$("#show-publicity-calendar").onclick=showPublicityCalendar;
const resourceForm=$("#resource-combined-form"),resourceType=resourceForm.elements.source_type;
function syncResourceType(){const file=resourceType.value==="file";resourceForm.querySelector("[data-resource-file]").hidden=!file;resourceForm.querySelector("[data-resource-link]").hidden=file;resourceForm.elements.file.required=file;resourceForm.elements.url.required=!file;resourceForm.querySelector("button").textContent=file?"选择文件并上传":"保存链接";}
resourceType.onchange=syncResourceType;syncResourceType();
resourceForm.onsubmit=async event=>{event.preventDefault();const form=event.currentTarget,data=new FormData(form),button=form.querySelector("button"),isFile=data.get("source_type")==="file";try{button.disabled=true;button.textContent=isFile?"上传中…":"保存中…";if(isFile){data.set("resource_type","file");data.delete("source_type");const response=await fetch("/api/v2/resources/upload",{method:"POST",headers:state.actor?{"X-Actor-Name":encodeURIComponent(state.actor)}:{},body:data});if(!response.ok){const body=await response.json().catch(()=>({}));throw new Error(body.detail||"上传失败");}}else{await api("/api/v2/resources",{method:"POST",body:JSON.stringify({title:data.get("title").trim(),resource_type:"link",url:data.get("url").trim(),owner_name:data.get("owner_name").trim()||null,description:data.get("description").trim()||null})});}form.reset();syncResourceType();await showResources();notify(isFile?"文件已上传":"资料链接已保存",true);}catch(error){notify(`资料保存失败：${error.message}`);}finally{button.disabled=false;syncResourceType();}};
$('#resource-link-form [name="task_id"]').onchange = () => loadTaskResourceLinks();
$("#resource-link-form").onsubmit = async event => { event.preventDefault(); const data=new FormData(event.currentTarget); try { await api(`/api/v2/tasks/${data.get("task_id")}/resources`,{method:"POST",body:JSON.stringify({resource_id:data.get("resource_id"),relation_type:data.get("relation_type")})}); await loadTaskResourceLinks(); notify("任务资料关联已保存",true); } catch(error){ notify(`关联失败：${error.message}`); } };
$("#manual-log-form").onsubmit = async event => { event.preventDefault(); if (!state.program) return; const form = event.currentTarget, summary = new FormData(form).get("summary").trim(); if (!summary) return; await api(`/api/v2/programs/${state.program.id}/activity-logs`, { method: "POST", body: JSON.stringify({ summary }) }); form.reset(); await loadActivityLogs(state.program.id); notify("项目动态已记录", true); };
state.actor = loadStoredActor().trim().slice(0, 100);
const actorInput = $("#current-actor"); actorInput.value = state.actor; actorInput.oninput = () => { const value = actorInput.value.trimStart().slice(0, 100); state.actor = value.trim(); storeActor(state.actor); }; actorInput.onchange = () => { actorInput.value = state.actor; notify(state.actor ? `当前使用者：${state.actor}` : "已清除使用者名称", true); };

async function init() {
  arrangeWorkspaceSections();
  try { await Promise.all([loadTemplates(), loadPrograms()]); renderCalendar(); if (state.programs.length) await showProgram(state.programs[0].id); }
  catch (error) { notify(`加载失败：${error.message}`); }
}
init();
})();
