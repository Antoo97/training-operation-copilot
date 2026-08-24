const $ = selector => document.querySelector(selector);
const state = { project: null, projects: [], calendarDate: new Date(), selectedDate: null };
const dateFmt = new Intl.DateTimeFormat("zh-CN", { month: "short", day: "numeric" });
const fullDateFmt = new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric", weekday: "short" });

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[c]);
}

async function api(path, options = {}) {
  const response = await fetch(path, { headers: { "Content-Type": "application/json", ...(options.headers || {}) }, ...options });
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

function isoDate(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatDate(value) { return dateFmt.format(new Date(`${value}T00:00:00`)); }

async function loadTemplates() {
  const templates = await api("/templates");
  $("#template").innerHTML = templates.map(item => `<option value="${item.id}">${escapeHtml(item.name)}</option>`).join("");
}

async function loadProjects(selectedId) {
  state.projects = await api("/projects");
  $("#project-total").textContent = state.projects.length;
  $("#project-list").innerHTML = state.projects.length ? state.projects.map(item => `
    <button class="project-card ${item.id === selectedId ? "active" : ""}" data-project-id="${item.id}">
      <strong>${escapeHtml(item.name)}</strong><span>培训日 · ${formatDate(item.event_date)}</span>
    </button>`).join("") : `<div class="empty-mini">暂无项目<br>点击右上角开始创建</div>`;
  document.querySelectorAll("[data-project-id]").forEach(button => button.onclick = () => showProject(button.dataset.projectId));
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
    .map(m => ({ type: "节点", title: m.name, done: false, meta: m.required ? "关键节点" : "普通节点" }));
  const tasks = state.project.tasks.filter(t => t.status !== "cancelled" && t.deadline === date)
    .map(t => ({ type: "任务", title: t.title, done: t.status === "done", meta: t.owner ? `负责人：${t.owner}` : "未分配负责人" }));
  return [...milestones, ...tasks];
}

function selectDate(date) {
  state.selectedDate = date;
  const items = itemsForDate(date);
  $("#selected-date-title").textContent = fullDateFmt.format(new Date(`${date}T00:00:00`));
  $("#day-items").innerHTML = items.length ? items.map(item => `
    <article class="day-item ${item.done ? "done" : ""}"><small>${item.type}${item.done ? " · 已完成" : ""}</small><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(item.meta)}</span></article>`).join("")
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
    const hasMilestone = items.some(item => item.type === "节点");
    const hasOpenTask = items.some(item => item.type === "任务" && !item.done);
    const hasDone = items.some(item => item.type === "任务" && item.done);
    cells.push(`<button class="calendar-day ${date.getMonth() !== month ? "outside" : ""} ${key === today ? "today" : ""} ${key === state.selectedDate ? "selected" : ""}" data-date="${key}">
      <span class="day-number">${date.getDate()}</span><span class="day-markers">${hasMilestone ? '<i class="marker milestone"></i>' : ""}${hasOpenTask ? '<i class="marker task"></i>' : ""}${hasDone ? '<i class="marker done"></i>' : ""}</span>
    </button>`);
  }
  $("#calendar-grid").innerHTML = cells.join("");
  document.querySelectorAll("[data-date]").forEach(button => button.onclick = () => selectDate(button.dataset.date));
}

function renderTimeline(project) {
  const tasks = project.tasks.filter(t => t.status !== "cancelled");
  const groups = project.milestones.filter(m => m.status === "active").map(milestone => ({
    milestone, tasks: tasks.filter(task => task.project_milestone_id === milestone.id),
  })).sort((a, b) => a.milestone.deadline.localeCompare(b.milestone.deadline) || a.milestone.sort_order - b.milestone.sort_order);
  $("#timeline").innerHTML = groups.map(({ milestone, tasks: grouped }) => {
    const done = grouped.filter(t => t.status === "done").length;
    return `<article class="milestone">
      <div><input class="milestone-date-input" data-mid="${milestone.id}" type="date" value="${milestone.deadline}"><span class="milestone-code">${escapeHtml(milestone.code)}</span></div>
      <div><div class="milestone-top"><input class="milestone-name-input" data-mid="${milestone.id}" value="${escapeHtml(milestone.name)}" maxlength="200"><div class="milestone-controls"><span>${done}/${grouped.length} 已完成</span><button class="link-button milestone-required ${milestone.required ? "accent" : ""}" data-mid="${milestone.id}" data-value="${Boolean(milestone.required)}">${milestone.required ? "◆ 关键节点" : "◇ 设为关键"}</button><button class="link-button accent add-task" data-mid="${milestone.id}">＋任务</button><button class="link-button danger remove-milestone" data-mid="${milestone.id}">移除</button></div></div>
      <form class="inline-task-form" data-task-form="${milestone.id}" hidden><input name="title" maxlength="300" required placeholder="任务名称"><input name="owner" maxlength="200" placeholder="负责人（选填）"><label class="check-label"><input name="required" type="checkbox">关键</label><button class="primary-button">保存</button><button type="button" class="text-button cancel-task">取消</button></form>
      <div class="task-list">${grouped.map(task => `<div class="task ${task.status === "done" ? "done" : ""}"><label class="task-main"><input class="task-check" data-tid="${task.id}" type="checkbox" ${task.status === "done" ? "checked" : ""}><span>${escapeHtml(task.title)}</span></label><div class="task-tools"><button class="link-button task-required ${task.required ? "accent" : ""}" data-tid="${task.id}" data-value="${Boolean(task.required)}">${task.required ? "◆ 关键" : "◇ 设为关键"}</button><button class="link-button danger remove-task" data-tid="${task.id}">移除</button></div><input class="owner-input" data-tid="${task.id}" value="${escapeHtml(task.owner || "")}" placeholder="添加负责人"></div>`).join("")}</div></div>
    </article>`;
  }).join("") || `<div class="empty-mini">暂无节点</div>`;
  bindTimelineEvents(project.id);
}

async function showProject(id) {
  try {
    const project = await api(`/projects/${id}`); state.project = project;
    $("#project-detail").hidden = false; $("#detail-name").textContent = project.name;
    $("#detail-meta").textContent = `启动 ${formatDate(project.start_date)} · 培训 ${formatDate(project.event_date)}`;
    updateMetrics(project); renderCalendar(); renderTimeline(project); await loadProjects(id);
  } catch (error) { notify(error.message); }
}

function bindTimelineEvents(projectId) {
  document.querySelectorAll(".milestone-date-input").forEach(el => el.onchange = async () => { await api(`/project-milestones/${el.dataset.mid}`, { method: "PATCH", body: JSON.stringify({ deadline: el.value }) }); await showProject(projectId); });
  document.querySelectorAll(".milestone-name-input").forEach(el => el.onblur = async () => { const name = el.value.trim(); if (name && name !== el.defaultValue) { await api(`/project-milestones/${el.dataset.mid}`, { method: "PATCH", body: JSON.stringify({ name }) }); el.defaultValue = name; } });
  document.querySelectorAll(".milestone-required").forEach(el => el.onclick = async () => { await api(`/project-milestones/${el.dataset.mid}`, { method: "PATCH", body: JSON.stringify({ required: el.dataset.value !== "true" }) }); await showProject(projectId); });
  document.querySelectorAll(".remove-milestone").forEach(el => el.onclick = async () => { if (confirm("移除这个节点及其任务？标准模板不会受到影响。")) { await api(`/project-milestones/${el.dataset.mid}`, { method: "DELETE" }); await showProject(projectId); } });
  document.querySelectorAll(".task-check").forEach(el => el.onchange = async () => { await api(`/tasks/${el.dataset.tid}/status`, { method: "PATCH", body: JSON.stringify({ status: el.checked ? "done" : "todo" }) }); await showProject(projectId); });
  document.querySelectorAll(".task-required").forEach(el => el.onclick = async () => { await api(`/tasks/${el.dataset.tid}/required`, { method: "PATCH", body: JSON.stringify({ required: el.dataset.value !== "true" }) }); await showProject(projectId); });
  document.querySelectorAll(".remove-task").forEach(el => el.onclick = async () => { if (confirm("移除这项任务？标准模板不会受到影响。")) { await api(`/tasks/${el.dataset.tid}`, { method: "DELETE" }); await showProject(projectId); } });
  document.querySelectorAll(".owner-input").forEach(el => el.onblur = async () => { const owner = el.value.trim(); if (owner !== el.defaultValue) { await api(`/tasks/${el.dataset.tid}/owner`, { method: "PATCH", body: JSON.stringify({ owner: owner || null }) }); el.defaultValue = owner; notify("负责人已保存", true); } });
  document.querySelectorAll(".add-task").forEach(el => el.onclick = () => { $(`[data-task-form="${el.dataset.mid}"]`).hidden = false; el.hidden = true; });
  document.querySelectorAll(".cancel-task").forEach(el => el.onclick = () => { const taskForm = el.closest("form"); taskForm.hidden = true; $(`.add-task[data-mid="${taskForm.dataset.taskForm}"]`).hidden = false; });
  document.querySelectorAll("[data-task-form]").forEach(taskForm => taskForm.onsubmit = async event => { event.preventDefault(); const data = new FormData(taskForm); await api(`/projects/${projectId}/tasks`, { method: "POST", body: JSON.stringify({ title: data.get("title").trim(), owner: data.get("owner").trim() || null, required: data.get("required") === "on", project_milestone_id: taskForm.dataset.taskForm }) }); await showProject(projectId); });
}

function toggleCreate(show) { $("#create-section").hidden = !show; if (show) $("#name").focus(); }
$("#quick-create").onclick = () => toggleCreate(true); $("#close-create").onclick = () => toggleCreate(false);
document.querySelectorAll(".nav-item").forEach(button => button.onclick = () => { document.querySelectorAll(".nav-item").forEach(b => b.classList.remove("active")); button.classList.add("active"); if (button.dataset.view === "create") toggleCreate(true); if (button.dataset.view === "timeline" && !$("#project-detail").hidden) $("#project-detail").scrollIntoView({ behavior: "smooth" }); });
$("#prev-month").onclick = () => { state.calendarDate = new Date(state.calendarDate.getFullYear(), state.calendarDate.getMonth() - 1, 1); renderCalendar(); };
$("#next-month").onclick = () => { state.calendarDate = new Date(state.calendarDate.getFullYear(), state.calendarDate.getMonth() + 1, 1); renderCalendar(); };
$("#today-button").onclick = () => { state.calendarDate = new Date(); selectDate(isoDate(new Date())); };

$("#show-add-milestone").onclick = () => { $("#milestone-form").hidden = false; $("#show-add-milestone").hidden = true; };
$("#cancel-add-milestone").onclick = () => { $("#milestone-form").hidden = true; $("#show-add-milestone").hidden = false; };
$("#milestone-form").onsubmit = async event => { event.preventDefault(); const data = new FormData(event.currentTarget); await api(`/projects/${state.project.id}/milestones`, { method: "POST", body: JSON.stringify({ name: data.get("name").trim(), deadline: data.get("deadline"), required: data.get("required") === "on" }) }); event.currentTarget.reset(); $("#cancel-add-milestone").click(); await showProject(state.project.id); };

$("#project-form").onsubmit = async event => { event.preventDefault(); try { const project = await api("/projects", { method: "POST", body: JSON.stringify({ name: $("#name").value.trim(), template_id: $("#template").value, start_date: $("#start-date").value, event_date: $("#event-date").value }) }); event.currentTarget.reset(); await loadTemplates(); toggleCreate(false); await showProject(project.id); notify("项目已创建，节点与任务已生成", true); } catch (error) { notify(error.message); } };

async function init() {
  try { await Promise.all([loadTemplates(), loadProjects()]); renderCalendar(); if (state.projects.length) await showProject(state.projects[0].id); }
  catch (error) { notify(`加载失败：${error.message}`); }
}
init();
