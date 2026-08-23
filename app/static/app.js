const form = document.querySelector("#project-form");
const templateSelect = document.querySelector("#template");
const projectList = document.querySelector("#project-list");
const message = document.querySelector("#form-message");
const emptyState = document.querySelector("#empty-state");
const detail = document.querySelector("#project-detail");

const dateFormatter = new Intl.DateTimeFormat("zh-CN", { month: "short", day: "numeric" });

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[character]);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "请求失败");
  }
  return response.json();
}

function formatDate(value) {
  return dateFormatter.format(new Date(`${value}T00:00:00`));
}

async function loadTemplates() {
  const templates = await api("/templates");
  templateSelect.innerHTML = templates
    .map(item => `<option value="${item.id}">${item.name}</option>`)
    .join("");
}

async function loadProjects(selectedId) {
  const projects = await api("/projects");
  projectList.innerHTML = projects.length
    ? projects.map(item => `
      <button class="project-card ${item.id === selectedId ? "active" : ""}" data-id="${item.id}">
        <strong>${item.name}</strong>
        <span>培训日 ${formatDate(item.event_date)}</span>
      </button>`).join("")
    : `<p class="muted">暂无项目</p>`;

  document.querySelectorAll(".project-card").forEach(button => {
    button.addEventListener("click", () => showProject(button.dataset.id));
  });
}

async function showProject(projectId) {
  const project = await api(`/projects/${projectId}`);
  emptyState.hidden = true;
  detail.hidden = false;
  document.querySelector("#detail-name").textContent = project.name;
  document.querySelector("#detail-meta").textContent = `启动 ${formatDate(project.start_date)} · 培训 ${formatDate(project.event_date)}`;
  const activeTasks = project.tasks.filter(task => task.status !== "cancelled");
  document.querySelector("#task-count").textContent = activeTasks.length;

  const groups = project.milestones
    .filter(milestone => milestone.status === "active")
    .map(milestone => ({
      milestone,
      tasks: activeTasks.filter(task => task.project_milestone_id === milestone.id),
    }))
    .sort((a, b) => a.milestone.deadline.localeCompare(b.milestone.deadline) || a.milestone.sort_order - b.milestone.sort_order);

  document.querySelector("#timeline").innerHTML = groups
    .map(({milestone, tasks}) => {
      const doneCount = tasks.filter(task => task.status === "done").length;
      const complete = tasks.length > 0 && doneCount === tasks.length;
      return `
      <article class="milestone ${complete ? "complete" : ""}">
        <div class="milestone-date">
          <input class="milestone-date-input" data-milestone-id="${milestone.id}" type="date" value="${milestone.deadline}">
          <span>${escapeHtml(milestone.code)}</span>
        </div>
        <div>
          <div class="milestone-title">
            <input class="milestone-name-input" data-milestone-id="${milestone.id}" value="${escapeHtml(milestone.name)}" maxlength="200">
            <div class="milestone-controls">
              <span>${doneCount}/${tasks.length} 已完成</span>
              <button class="milestone-required-toggle ${milestone.required ? "active" : ""}" data-milestone-id="${milestone.id}" data-required="${Boolean(milestone.required)}">${milestone.required ? "★ 关键节点" : "☆ 普通节点"}</button>
              <button class="add-task-button" data-milestone-id="${milestone.id}">＋ 添加任务</button>
              <button class="remove-milestone-button" data-milestone-id="${milestone.id}">移除节点</button>
            </div>
          </div>
          <form class="inline-task-form" data-milestone-id="${milestone.id}" hidden>
            <input name="title" maxlength="300" required placeholder="任务名称">
            <input name="owner" maxlength="200" placeholder="责任人（选填）">
            <label><input name="required" type="checkbox"> 设为关键</label>
            <button type="submit">保存</button>
            <button type="button" class="cancel-add-button">取消</button>
          </form>
          <div class="task-list">
            ${tasks.map(task => `
              <div class="task ${task.status === "done" ? "done" : ""}">
                <label class="task-main">
                  <input class="task-checkbox" type="checkbox" data-task-id="${task.id}" ${task.status === "done" ? "checked" : ""}>
                  <span>${escapeHtml(task.title)}</span>
                </label>
                <div class="task-controls">
                  <button class="required-toggle ${task.required ? "active" : ""}" data-task-id="${task.id}" data-required="${Boolean(task.required)}">${task.required ? "★ 关键" : "☆ 设为关键"}</button>
                  <button class="remove-task-button" data-task-id="${task.id}">移除</button>
                </div>
                <input class="owner-input" data-task-id="${task.id}" maxlength="200" value="${escapeHtml(task.owner || "")}" placeholder="添加责任人">
              </div>`).join("")}
          </div>
        </div>
      </article>`;
    }).join("");

  const milestoneForm = document.querySelector("#milestone-form");
  const showMilestoneFormButton = document.querySelector("#show-add-milestone");
  showMilestoneFormButton.onclick = () => {
    milestoneForm.hidden = false;
    showMilestoneFormButton.hidden = true;
  };
  document.querySelector("#cancel-add-milestone").onclick = () => {
    milestoneForm.hidden = true;
    showMilestoneFormButton.hidden = false;
  };
  milestoneForm.onsubmit = async event => {
    event.preventDefault();
    const formData = new FormData(milestoneForm);
    await api(`/projects/${projectId}/milestones`, {
      method: "POST",
      body: JSON.stringify({
        name: formData.get("name").trim(),
        deadline: formData.get("deadline"),
        required: formData.get("required") === "on",
      }),
    });
    milestoneForm.reset();
    milestoneForm.hidden = true;
    showMilestoneFormButton.hidden = false;
    await showProject(projectId);
  };

  document.querySelectorAll(".milestone-date-input").forEach(input => {
    input.addEventListener("change", async () => {
      await api(`/project-milestones/${input.dataset.milestoneId}`, {
        method: "PATCH",
        body: JSON.stringify({ deadline: input.value }),
      });
      await showProject(projectId);
    });
  });

  document.querySelectorAll(".milestone-name-input").forEach(input => {
    const saveName = async () => {
      const name = input.value.trim();
      if (!name || name === input.defaultValue) return;
      await api(`/project-milestones/${input.dataset.milestoneId}`, {
        method: "PATCH",
        body: JSON.stringify({ name }),
      });
      input.defaultValue = name;
    };
    input.addEventListener("blur", saveName);
    input.addEventListener("keydown", event => {
      if (event.key === "Enter") input.blur();
    });
  });

  document.querySelectorAll(".milestone-required-toggle").forEach(button => {
    button.addEventListener("click", async event => {
      event.preventDefault();
      await api(`/project-milestones/${button.dataset.milestoneId}`, {
        method: "PATCH",
        body: JSON.stringify({ required: button.dataset.required !== "true" }),
      });
      await showProject(projectId);
    });
  });

  document.querySelectorAll(".remove-milestone-button").forEach(button => {
    button.addEventListener("click", async event => {
      event.preventDefault();
      if (!window.confirm("从当前项目中移除这个节点及其任务？标准模板不会受到影响。")) return;
      await api(`/project-milestones/${button.dataset.milestoneId}`, { method: "DELETE" });
      await showProject(projectId);
    });
  });

  document.querySelectorAll(".task-checkbox").forEach(checkbox => {
    checkbox.addEventListener("change", async () => {
      checkbox.disabled = true;
      try {
        await api(`/tasks/${checkbox.dataset.taskId}/status`, {
          method: "PATCH",
          body: JSON.stringify({ status: checkbox.checked ? "done" : "todo" }),
        });
        await showProject(projectId);
      } catch (error) {
        checkbox.checked = !checkbox.checked;
        checkbox.disabled = false;
        message.textContent = `任务更新失败：${error.message}`;
      }
    });
  });

  document.querySelectorAll(".owner-input").forEach(input => {
    const saveOwner = async () => {
      const originalValue = input.defaultValue;
      const nextValue = input.value.trim();
      if (nextValue === originalValue) return;
      input.disabled = true;
      try {
        await api(`/tasks/${input.dataset.taskId}/owner`, {
          method: "PATCH",
          body: JSON.stringify({ owner: nextValue || null }),
        });
        input.defaultValue = nextValue;
        message.textContent = nextValue ? `责任人已保存：${nextValue}` : "责任人已清除。";
      } catch (error) {
        input.value = originalValue;
        message.textContent = `责任人保存失败：${error.message}`;
      } finally {
        input.disabled = false;
      }
    };
    input.addEventListener("blur", saveOwner);
    input.addEventListener("keydown", event => {
      if (event.key === "Enter") input.blur();
    });
  });

  document.querySelectorAll(".required-toggle").forEach(button => {
    button.addEventListener("click", async event => {
      event.preventDefault();
      const required = button.dataset.required !== "true";
      await api(`/tasks/${button.dataset.taskId}/required`, {
        method: "PATCH",
        body: JSON.stringify({ required }),
      });
      await showProject(projectId);
    });
  });

  document.querySelectorAll(".remove-task-button").forEach(button => {
    button.addEventListener("click", async event => {
      event.preventDefault();
      if (!window.confirm("从当前项目中移除这项任务？标准模板不会受到影响。")) return;
      await api(`/tasks/${button.dataset.taskId}`, { method: "DELETE" });
      await showProject(projectId);
    });
  });

  document.querySelectorAll(".add-task-button").forEach(button => {
    button.addEventListener("click", event => {
      event.preventDefault();
      document.querySelector(`.inline-task-form[data-milestone-id="${button.dataset.milestoneId}"]`).hidden = false;
      button.hidden = true;
    });
  });

  document.querySelectorAll(".cancel-add-button").forEach(button => {
    button.addEventListener("click", () => {
      const taskForm = button.closest("form");
      taskForm.hidden = true;
      document.querySelector(`.add-task-button[data-milestone-id="${taskForm.dataset.milestoneId}"]`).hidden = false;
    });
  });

  document.querySelectorAll(".inline-task-form").forEach(taskForm => {
    taskForm.addEventListener("submit", async event => {
      event.preventDefault();
      const formData = new FormData(taskForm);
      await api(`/projects/${projectId}/tasks`, {
        method: "POST",
        body: JSON.stringify({
          title: formData.get("title").trim(),
          owner: formData.get("owner").trim() || null,
          required: formData.get("required") === "on",
          project_milestone_id: taskForm.dataset.milestoneId,
        }),
      });
      await showProject(projectId);
    });
  });

  await loadProjects(projectId);
}

form.addEventListener("submit", async event => {
  event.preventDefault();
  message.textContent = "正在创建项目…";
  try {
    const project = await api("/projects", {
      method: "POST",
      body: JSON.stringify({
        name: document.querySelector("#name").value.trim(),
        template_id: templateSelect.value,
        start_date: document.querySelector("#start-date").value,
        event_date: document.querySelector("#event-date").value,
      }),
    });
    message.textContent = "项目已创建，节点与任务已生成。";
    form.reset();
    await loadTemplates();
    await showProject(project.id);
  } catch (error) {
    message.textContent = error.message;
  }
});

Promise.all([loadTemplates(), loadProjects()]).catch(error => {
  message.textContent = `加载失败：${error.message}`;
});
