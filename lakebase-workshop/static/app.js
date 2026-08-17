const state = {
  tickets: [],
  selectedId: null,
  status: "all",
};

const labels = {
  new: "New",
  in_progress: "In Progress",
  waiting: "Waiting",
  resolved: "Resolved",
  urgent: "Urgent",
  high: "High",
  medium: "Medium",
  low: "Low",
};

const listEl = document.querySelector("#ticket-list");
const detailEl = document.querySelector("#detail-panel");
const healthEl = document.querySelector("#health");
const breakButton = document.querySelector("#break-scenario");

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }
  return response.json();
}

function badge(kind, value) {
  return `<span class="badge ${kind}-${value}">${labels[value] || value}</span>`;
}

function formatDate(value) {
  return new Intl.DateTimeFormat("ja-JP", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

async function loadHealth() {
  try {
    const result = await api("/api/health");
    renderHealth(result);
  } catch (error) {
    renderHealth({
      ok: false,
      database: "unknown",
      error_hint: error.message,
    });
  }
}

function renderHealth(result) {
  healthEl.className = "health";
  healthEl.replaceChildren();

  const statusLine = document.createElement("div");
  statusLine.className = "health-line";

  const dot = document.createElement("span");
  dot.className = "health-dot";
  dot.textContent = "●";
  statusLine.append(dot);

  const label = document.createElement("strong");
  label.className = "health-label";

  const meta = document.createElement("span");
  meta.className = "health-meta";

  if (result.ok && result.database === "lakebase" && result.init_ok === false) {
    healthEl.classList.add("health-init-error");
    label.textContent = "接続済み・初期化に失敗";
    meta.textContent = "（権限不足の可能性）";
  } else if (result.ok && result.database === "lakebase" && result.init_ok) {
    healthEl.classList.add("health-ok");
    label.textContent = "Lakebase 接続済み";
    const details = [
      result.database_name,
      result.branch ? `branch: ${result.branch}` : null,
      result.connection_mode === "app-resource" ? "Apps resource" : null,
    ].filter(Boolean);
    meta.textContent = details.length ? ` ・ ${details.join(" ・ ")}` : "";
  } else if (result.database === "sqlite-local") {
    healthEl.classList.add("health-warn");
    label.textContent = "デモモード";
    meta.textContent = "（SQLite・デモ専用データ） ・ Lakebaseには未接続です";
  } else {
    healthEl.classList.add("health-danger");
    label.textContent = "接続エラー";
    meta.textContent = "（設定を確認してください）";
  }

  statusLine.append(label, meta);
  healthEl.append(statusLine);

  if (result.database === "sqlite-local") {
    const demoHint = document.createElement("div");
    demoHint.className = "health-hint";
    demoHint.textContent = "Lakebase接続後は、チケットがデモ専用の3件からLakebase上の5件へ切り替わります。";
    healthEl.append(demoHint);
  }

  if (result.ok && result.database === "lakebase" && result.init_ok === false) {
    const permissionHint = document.createElement("div");
    permissionHint.className = "health-hint";
    permissionHint.textContent = initErrorLooksLikePermission(result.init_error)
      ? 'テーブル作成権限が不足している可能性があります。GRANT USAGE, CREATE ON SCHEMA public TO "<アプリの実行ID>"; を実行し再デプロイしてください。'
      : "起動時のテーブル作成またはサンプルデータ投入に失敗しました。設定と権限を確認して再デプロイしてください。";
    healthEl.append(permissionHint);
  }

  if (!result.ok && result.error_hint) {
    const hint = document.createElement("div");
    hint.className = "health-hint";
    hint.textContent = result.error_hint;
    healthEl.append(hint);
  }

  if (result.ok && result.database === "lakebase" && result.init_ok === false && result.init_error) {
    const hint = document.createElement("div");
    hint.className = "health-hint health-hint-muted";
    hint.textContent = result.init_error;
    healthEl.append(hint);
  }

  updateBreakButton(result);
}

function updateBreakButton(result) {
  if (!breakButton) return;
  const canBreak = result.ok && result.database === "lakebase" && result.init_ok;
  breakButton.disabled = !canBreak;
  breakButton.title = canBreak
    ? "接続中の Lakebase で priority 列を削除します"
    : "Lakebase 接続と初期化完了後に実行できます";
}

function initErrorLooksLikePermission(message) {
  const text = String(message || "").toLowerCase();
  return text.includes("permission denied") || text.includes("insufficientprivilege");
}

async function loadTickets() {
  const query = state.status === "all" ? "" : `?status=${encodeURIComponent(state.status)}`;
  state.tickets = await api(`/api/tickets${query}`);
  if (!state.selectedId && state.tickets.length > 0) {
    state.selectedId = state.tickets[0].id;
  }
  renderList();
  if (state.selectedId) {
    await renderDetail(state.selectedId);
  }
}

function renderList() {
  if (state.tickets.length === 0) {
    listEl.innerHTML = `<div class="empty-state"><p>No tickets found.</p></div>`;
    return;
  }
  listEl.innerHTML = state.tickets.map((ticket) => `
    <button class="ticket-card ${ticket.id === state.selectedId ? "active" : ""}" data-ticket-id="${ticket.id}">
      <div class="badge-row">
        ${badge("status", ticket.status)}
        ${badge("priority", ticket.priority)}
      </div>
      <h2>${escapeHtml(ticket.title)}</h2>
      <div class="meta-row">
        <span>#${ticket.id}</span>
        <span>${escapeHtml(ticket.customer)}</span>
        <span>${escapeHtml(ticket.owner)}</span>
        <span>${ticket.comment_count} comments</span>
      </div>
    </button>
  `).join("");

  document.querySelectorAll("[data-ticket-id]").forEach((button) => {
    button.addEventListener("click", async () => {
      state.selectedId = Number(button.dataset.ticketId);
      renderList();
      await renderDetail(state.selectedId);
    });
  });
}

async function renderDetail(ticketId) {
  try {
    const [ticket, comments] = await Promise.all([
      api(`/api/tickets/${ticketId}`),
      api(`/api/tickets/${ticketId}/comments`),
    ]);

    detailEl.innerHTML = `
      <div class="detail-header">
        <div>
          <div class="badge-row">
            ${badge("status", ticket.status)}
            ${badge("priority", ticket.priority)}
          </div>
          <h2>${escapeHtml(ticket.title)}</h2>
          <div class="customer">${escapeHtml(ticket.customer)} / ${escapeHtml(ticket.category)} / Updated ${formatDate(ticket.updated_at)}</div>
        </div>
      </div>

      <div class="description">${escapeHtml(ticket.description)}</div>

      <form class="fields" id="ticket-form">
        <div class="field">
          <label for="status">Status</label>
          <select id="status" name="status">
            ${option("new", ticket.status)}
            ${option("in_progress", ticket.status)}
            ${option("waiting", ticket.status)}
            ${option("resolved", ticket.status)}
          </select>
        </div>
        <div class="field">
          <label for="priority">Priority</label>
          <select id="priority" name="priority">
            ${option("urgent", ticket.priority)}
            ${option("high", ticket.priority)}
            ${option("medium", ticket.priority)}
            ${option("low", ticket.priority)}
          </select>
        </div>
        <div class="field">
          <label for="owner">Owner</label>
          <input id="owner" name="owner" value="${escapeAttr(ticket.owner)}" />
        </div>
      </form>

      <div class="actions">
        <button class="primary" id="save-ticket">Save Changes</button>
        <span class="toast" id="save-toast"></span>
      </div>

      <section class="comments">
        <h3>Comments</h3>
        <div id="comments">
          ${comments.map((comment) => `
            <article class="comment">
              <strong>${escapeHtml(comment.author)} <span class="customer">${formatDate(comment.created_at)}</span></strong>
              <p>${escapeHtml(comment.body)}</p>
            </article>
          `).join("")}
        </div>
        <form class="comment-form" id="comment-form">
          <textarea name="body" placeholder="Add a comment"></textarea>
          <button class="primary" type="submit">Add Comment</button>
        </form>
      </section>
    `;

    document.querySelector("#save-ticket").addEventListener("click", () => saveTicket(ticketId));
    document.querySelector("#comment-form").addEventListener("submit", (event) => addComment(event, ticketId));
  } catch (error) {
    detailEl.innerHTML = `<div class="error">Ticket could not be loaded. ${escapeHtml(error.message)}</div>`;
  }
}

function option(value, selected) {
  return `<option value="${value}" ${value === selected ? "selected" : ""}>${labels[value]}</option>`;
}

async function saveTicket(ticketId) {
  const form = new FormData(document.querySelector("#ticket-form"));
  await api(`/api/tickets/${ticketId}`, {
    method: "PATCH",
    body: JSON.stringify({
      status: form.get("status"),
      priority: form.get("priority"),
      owner: form.get("owner"),
    }),
  });
  document.querySelector("#save-toast").textContent = "Saved";
  await loadTickets();
}

async function addComment(event, ticketId) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const body = String(form.get("body") || "").trim();
  if (!body) return;
  await api(`/api/tickets/${ticketId}/comments`, {
    method: "POST",
    body: JSON.stringify({ body }),
  });
  await loadTickets();
}

async function breakScenario() {
  if (!breakButton || breakButton.disabled) return;
  const confirmed = window.confirm(
    "接続中の Lakebase で tickets.priority 列を削除します。\n\n" +
    "この操作は Part 3 の復旧シナリオ用です。実行するとチケット画面はエラーになります。"
  );
  if (!confirmed) return;

  breakButton.disabled = true;
  breakButton.textContent = "実行中...";
  try {
    await api("/api/admin/break-priority", { method: "POST" });
    detailEl.innerHTML = `
      <div class="error">
        priority 列を削除しました。チケット一覧はこの後エラーになります。
        Lakebase の復旧ブランチに接続し直して復旧を確認してください。
      </div>
    `;
    try {
      await loadTickets();
    } catch (error) {
      listEl.innerHTML = `<div class="error">想定通り priority 列参照でエラーになりました。</div>`;
      detailEl.innerHTML = `
        <div class="error">
          priority 列が削除されたため、アプリがチケットを読み込めません。
          Lakebase の復旧ブランチに接続し直して、画面が復旧することを確認してください。
        </div>
      `;
    }
  } catch (error) {
    const message = String(error.message || "");
    if (message.includes("must be owner of table tickets")) {
      detailEl.innerHTML = `
        <div class="error">
          このブランチの tickets テーブル所有者設定が不足しているため、シナリオを開始できません。
          講師が対象ブランチで tickets と ticket_comments の所有者を
          ワークショップ用の所有者ロールへ更新してから、もう一度実行してください。
        </div>
      `;
    } else {
      detailEl.innerHTML = `<div class="error">シナリオ操作に失敗しました。 ${escapeHtml(message)}</div>`;
    }
  } finally {
    breakButton.textContent = "シナリオを壊す";
    await loadHealth();
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttr(value) {
  return escapeHtml(value).replaceAll("`", "&#096;");
}

document.querySelectorAll(".filter").forEach((button) => {
  button.addEventListener("click", async () => {
    document.querySelectorAll(".filter").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    state.status = button.dataset.status;
    state.selectedId = null;
    await loadTickets();
  });
});

if (breakButton) {
  breakButton.addEventListener("click", breakScenario);
}

loadHealth();
loadTickets().catch((error) => {
  detailEl.innerHTML = `<div class="error">Application failed to start. ${escapeHtml(error.message)}</div>`;
});
