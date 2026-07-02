// ==================== YaYa 多级菜单控制台 v3.0 — Plugin Page JS ====================

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
const editParent = $("#edit-parent");
const parentInfo = $("#parent-info");
const inputKeyword = $("#input-keyword");
const inputText = $("#input-text");
const inputImages = $("#input-images");
const btnSave = $("#btn-save");
const btnCancel = $("#btn-cancel");
const btnCloseModal = $("#btn-close-modal");

// Toast
const toast = $("#toast");

// ==================== 状态 ====================
let treeData = [];       // 嵌套树
let flatNodes = [];      // 扁平节点列表
let toastTimer = null;

// ==================== 初始化 ====================
async function init() {
  const context = await bridge.ready();
  console.log("YaYa v3.0 keyword-console ready:", context);
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
    flatNodes = data.nodes || [];
    treeData = data.tree || [];
    renderTree();
  } catch (err) {
    console.error("加载规则失败:", err);
    showToast("加载规则失败: " + err.message, "error");
  }
}

// ==================== 树形渲染 ====================
function renderTree() {
  const total = flatNodes.length;
  const roots = treeData.length;
  ruleCount.textContent = `共 ${total} 个节点（${roots} 个根节点）`;

  if (total === 0) {
    rulesList.innerHTML =
      '<div class="empty-state">暂无节点，点击上方按钮添加根节点</div>';
    return;
  }

  rulesList.innerHTML = treeData
    .map((node) => renderNode(node, 0))
    .join("");

  // 绑定所有按钮事件
  bindTreeEvents();
}

function renderNode(node, depth) {
  const hasChildren = node.children && node.children.length > 0;
  const childCount = hasChildren ? node.children.length : 0;
  const isLeaf = !hasChildren;
  const icon = isLeaf ? "📄" : "📁";

  let html = `
  <div class="tree-node" data-id="${escapeHtml(node.id)}" data-depth="${depth}">
    <div class="tree-row" style="padding-left: ${depth * 24 + 8}px;">
      <span class="tree-toggle" data-id="${escapeHtml(node.id)}">
        ${hasChildren ? "▼" : "　"}
      </span>
      <span class="tree-icon">${icon}</span>
      <span class="tree-keyword">${escapeHtml(node.keyword)}</span>
      ${childCount > 0 ? `<span class="tree-badge">${childCount} 个子项</span>` : ""}
      ${isLeaf && node.reply_text
        ? `<span class="tree-preview">— ${escapeHtml(node.reply_text).substring(0, 30)}</span>`
        : ""}
      <div class="tree-actions">
        <button class="btn btn-sm" data-action="add-child" data-id="${escapeHtml(node.id)}" title="添加子节点">+子</button>
        <button class="btn btn-sm" data-action="edit" data-id="${escapeHtml(node.id)}">编辑</button>
        <button class="btn btn-sm btn-danger" data-action="delete" data-id="${escapeHtml(node.id)}">删除</button>
      </div>
    </div>`;

  if (hasChildren) {
    html += `<div class="tree-children" data-parent="${escapeHtml(node.id)}">`;
    for (const child of node.children) {
      html += renderNode(child, depth + 1);
    }
    html += `</div>`;
  }

  html += `</div>`;
  return html;
}

function bindTreeEvents() {
  // 折叠/展开
  rulesList.querySelectorAll(".tree-toggle").forEach((btn) => {
    btn.addEventListener("click", () => {
      const nodeId = btn.dataset.id;
      const nodeEl = rulesList.querySelector(`.tree-node[data-id="${nodeId}"]`);
      const childrenEl = nodeEl?.querySelector(".tree-children");
      if (childrenEl) {
        const isHidden = childrenEl.style.display === "none";
        childrenEl.style.display = isHidden ? "" : "none";
        btn.textContent = isHidden ? "▼" : "▶";
      }
    });
  });

  // 编辑
  rulesList.querySelectorAll("[data-action='edit']").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.id;
      const node = flatNodes.find((n) => n.id === id);
      if (node) openModal(node);
    });
  });

  // 添加子节点
  rulesList.querySelectorAll("[data-action='add-child']").forEach((btn) => {
    btn.addEventListener("click", () => {
      const parentId = btn.dataset.id;
      const parent = flatNodes.find((n) => n.id === parentId);
      openModal(null, parent);
    });
  });

  // 删除
  rulesList.querySelectorAll("[data-action='delete']").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.id;
      const isConfirming = btn.dataset.confirming === "true";
      if (!isConfirming) {
        const node = flatNodes.find((n) => n.id === id);
        const cascade = countDescendants(id);
        btn.dataset.confirming = "true";
        btn.textContent = cascade > 0
          ? `确认删除(${cascade + 1}项)?` : "确认删除?";
        btn.style.background = "#c0392b";
        clearTimeout(btn._confirmTimer);
        btn._confirmTimer = setTimeout(() => resetDeleteBtn(btn), 3000);
      } else {
        clearTimeout(btn._confirmTimer);
        resetDeleteBtn(btn);
        handleDelete(id);
      }
    });
  });
}

function countDescendants(parentId) {
  let count = 0;
  for (const n of flatNodes) {
    if (n.parent_id === parentId) {
      count += 1 + countDescendants(n.id);
    }
  }
  return count;
}

// ==================== Modal 操作 ====================
function openModal(node = null, parent = null) {
  editId.value = "";
  editParent.value = "";
  parentInfo.textContent = "";

  if (node) {
    // 编辑模式
    modalTitle.textContent = "编辑节点";
    editId.value = node.id;
    inputKeyword.value = node.keyword || "";
    inputText.value = node.reply_text || "";
    inputImages.value = node.reply_images || "";
    if (node.parent_id) {
      const p = flatNodes.find((n) => n.id === node.parent_id);
      parentInfo.textContent = `父节点: ${p ? p.keyword : node.parent_id}`;
    } else {
      parentInfo.textContent = "根节点（无父节点）";
    }
  } else if (parent) {
    // 添加子节点模式
    modalTitle.textContent = `添加子节点`;
    editParent.value = parent.id;
    parentInfo.textContent = `父节点: ${parent.keyword}`;
    inputKeyword.value = "";
    inputText.value = "";
    inputImages.value = "";
  } else {
    // 添加根节点模式
    modalTitle.textContent = "新增根节点";
    parentInfo.textContent = "根节点（无父节点）";
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
  const parentId = editParent.value.trim() || null;
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
    parent_id: parentId || undefined,
    keyword,
    reply_text: replyText,
    reply_images: replyImages,
  };

  try {
    if (id) {
      await bridge.apiPost("rules/update", payload);
      showToast("节点已更新", "success");
    } else {
      await bridge.apiPost("rules/add", payload);
      showToast(parentId ? "子节点已添加" : "根节点已添加", "success");
    }
    closeModal();
    await loadRules();
  } catch (err) {
    console.error("保存失败:", err);
    showToast("保存失败: " + err.message, "error");
  }
}

// ==================== 删除按钮重置 ====================
function resetDeleteBtn(btn) {
  btn.dataset.confirming = "false";
  btn.textContent = "删除";
  btn.style.background = "";
}

// ==================== 删除 ====================
async function handleDelete(id) {
  console.log("[YaYa] 删除节点:", id);
  try {
    const result = await bridge.apiPost("rules/delete", { id });
    const cascade = (result && result.cascade) || 0;
    showToast(
      cascade > 0 ? `已删除节点及 ${cascade} 个子节点` : "节点已删除",
      "success"
    );
    await loadRules();
  } catch (err) {
    console.error("[YaYa] 删除失败:", err);
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
