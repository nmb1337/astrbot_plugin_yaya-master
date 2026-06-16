// ==================== YaYa 关键词回复控制台 — Plugin Page JS ====================

const bridge = window.AstrBotPluginPage;

// ==================== DOM 引用 ====================
const $ = (sel) => document.querySelector(sel);

const rulesList = $("#rules-list");
const ruleCount = $("#rule-count");
const btnAdd = $("#btn-add");

// Modal
const modalOverlay = $("#modal-overlay");
const modalTitle = $("#modal-title");
const editId = $("#edit-id");
const inputKeyword = $("#input-keyword");
const inputText = $("#input-text");
const inputImages = $("#input-images");
const btnSave = $("#btn-save");
const btnCancel = $("#btn-cancel");
const btnCloseModal = $("#btn-close-modal");

// Toast
const toast = $("#toast");

// ==================== 状态 ====================
let rules = [];
let toastTimer = null;

// ==================== 初始化 ====================
async function init() {
  const context = await bridge.ready();
  console.log("YaYa keyword-console ready:", context);

  bindEvents();
  await loadRules();
}

// ==================== 事件绑定 ====================
function bindEvents() {
  btnAdd.addEventListener("click", () => openModal());
  btnSave.addEventListener("click", handleSave);
  btnCancel.addEventListener("click", closeModal);
  btnCloseModal.addEventListener("click", closeModal);
  modalOverlay.addEventListener("click", (e) => {
    if (e.target === modalOverlay) closeModal();
  });
}

// ==================== 数据加载 ====================
async function loadRules() {
  try {
    const data = await bridge.apiGet("rules");
    rules = data.rules || [];
    renderRules();
  } catch (err) {
    console.error("加载规则失败:", err);
    showToast("加载规则失败: " + err.message, "error");
  }
}

// ==================== 渲染 ====================
function renderRules() {
  ruleCount.textContent = `共 ${rules.length} 条规则`;

  if (rules.length === 0) {
    rulesList.innerHTML = '<div class="empty-state">暂无规则，点击上方按钮添加</div>';
    return;
  }

  rulesList.innerHTML = rules
    .map(
      (rule) => `
    <div class="rule-card" data-id="${escapeHtml(rule.id)}">
      <div class="rule-header">
        <span class="rule-keyword">🔑 ${escapeHtml(rule.keyword)}</span>
        <div class="rule-actions">
          <button class="btn btn-sm" data-action="edit" data-id="${escapeHtml(rule.id)}">编辑</button>
          <button class="btn btn-sm btn-danger" data-action="delete" data-id="${escapeHtml(rule.id)}">删除</button>
        </div>
      </div>
      <div class="rule-body">
        ${
          rule.reply_text
            ? `<div class="rule-text">${escapeHtml(rule.reply_text)}</div>`
            : ""
        }
        ${renderImageTags(rule.reply_images)}
      </div>
      <div class="rule-meta">ID: ${escapeHtml(rule.id)}</div>
    </div>
  `
    )
    .join("");

  // 绑定卡片内按钮事件
  rulesList.querySelectorAll("[data-action='edit']").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.id;
      const rule = rules.find((r) => r.id === id);
      if (rule) openModal(rule);
    });
  });

  rulesList.querySelectorAll("[data-action='delete']").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.id;
      const isConfirming = btn.dataset.confirming === "true";
      if (!isConfirming) {
        // 第一次点击：进入确认状态
        btn.dataset.confirming = "true";
        btn.textContent = "确认删除？";
        btn.style.background = "#c0392b";
        clearTimeout(btn._confirmTimer);
        btn._confirmTimer = setTimeout(() => {
          resetDeleteBtn(btn);
        }, 3000);
      } else {
        // 第二次点击：执行删除
        clearTimeout(btn._confirmTimer);
        resetDeleteBtn(btn);
        handleDelete(id);
      }
    });
  });
}

function renderImageTags(imagesStr) {
  if (!imagesStr || !imagesStr.trim()) return "";
  const urls = imagesStr
    .split("\n")
    .map((u) => u.trim())
    .filter(Boolean);
  if (urls.length === 0) return "";
  return (
    '<div class="rule-images">' +
    urls
      .map((url) => `<span class="rule-image-tag" title="${escapeHtml(url)}">🖼️ ${escapeHtml(url)}</span>`)
      .join("") +
    "</div>"
  );
}

// ==================== Modal 操作 ====================
function openModal(rule = null) {
  if (rule) {
    modalTitle.textContent = "编辑规则";
    editId.value = rule.id;
    inputKeyword.value = rule.keyword || "";
    inputText.value = rule.reply_text || "";
    inputImages.value = rule.reply_images || "";
  } else {
    modalTitle.textContent = "新增规则";
    editId.value = "";
    inputKeyword.value = "";
    inputText.value = "";
    inputImages.value = "";
  }
  modalOverlay.classList.remove("hidden");
  inputKeyword.focus();
}

function closeModal() {
  modalOverlay.classList.add("hidden");
}

// ==================== 保存 ====================
async function handleSave() {
  const id = editId.value.trim();
  const keyword = inputKeyword.value.trim();
  const replyText = inputText.value.trim();
  const replyImages = inputImages.value.trim();

  if (!keyword) {
    showToast("请输入触发关键词", "error");
    inputKeyword.focus();
    return;
  }

  const payload = {
    id: id || undefined,
    keyword,
    reply_text: replyText,
    reply_images: replyImages,
  };

  try {
    if (id) {
      await bridge.apiPost("rules/update", payload);
      showToast("规则已更新", "success");
    } else {
      await bridge.apiPost("rules/add", payload);
      showToast("规则已添加", "success");
    }
    closeModal();
    await loadRules();
  } catch (err) {
    console.error("保存规则失败:", err);
    showToast("保存失败: " + err.message, "error");
  }
}

// ==================== 删除按钮状态重置 ====================
function resetDeleteBtn(btn) {
  btn.dataset.confirming = "false";
  btn.textContent = "删除";
  btn.style.background = "";
}

// ==================== 删除 ====================
async function handleDelete(id) {
  console.log("[YaYa] 删除规则:", id);
  try {
    const result = await bridge.apiPost("rules/delete", { id });
    console.log("[YaYa] 删除响应:", result);
    showToast("规则已删除", "success");
    await loadRules();
  } catch (err) {
    console.error("[YaYa] 删除规则失败:", err);
    showToast("删除失败: " + err.message, "error");
  }
}

// ==================== Toast ====================
function showToast(message, type = "success") {
  toast.textContent = message;
  toast.className = `toast ${type}`;
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.classList.add("hidden");
  }, 2500);
}

// ==================== 工具函数 ====================
function escapeHtml(str) {
  if (!str) return "";
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// ==================== 启动 ====================
init();
