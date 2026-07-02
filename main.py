import json
import time
import uuid
from pathlib import Path

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import Plain, Image
from astrbot.core.utils.astrbot_path import get_astrbot_plugin_data_path
from quart import jsonify, request

PLUGIN_NAME = "astrbot_plugin_yaya"
RULES_FILE = "keyword_rules.json"
SESSION_TIMEOUT = 300  # 菜单会话超时（秒）


# ==================== 数据持久化 ====================

def _get_rules_path() -> Path:
    data_dir = Path(get_astrbot_plugin_data_path()) / PLUGIN_NAME
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / RULES_FILE


def _load_rules() -> list:
    path = _get_rules_path()
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.error(f"加载关键词规则失败: {e}")
        return []


def _save_rules(rules: list) -> None:
    path = _get_rules_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rules, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存关键词规则失败: {e}")
        raise


# ==================== 树形工具 ====================

def _build_tree(flat_nodes: list) -> list:
    """将扁平节点列表构建为嵌套树（用于 API 返回）"""
    lookup = {}
    roots = []
    for n in flat_nodes:
        lookup[n["id"]] = {**n, "children": []}
    for n in flat_nodes:
        pid = n.get("parent_id")
        if pid and pid in lookup:
            lookup[pid]["children"].append(lookup[n["id"]])
        else:
            roots.append(lookup[n["id"]])
    return roots


def _collect_subtree_ids(flat_nodes: list, node_id: str) -> set:
    """递归收集某个节点及其所有子孙节点的 id"""
    ids = {node_id}
    children = [n["id"] for n in flat_nodes if n.get("parent_id") == node_id]
    for cid in children:
        ids |= _collect_subtree_ids(flat_nodes, cid)
    return ids


def _get_children(flat_nodes: list, parent_id: str | None) -> list:
    """获取指定节点的直接子节点（保持添加顺序）"""
    return [n for n in flat_nodes if n.get("parent_id") == parent_id]


# ==================== 插件主类 ====================

@register("astrbot_plugin_yaya", "贾梦",
          "多级关键词菜单回复插件，支持树形导航、多图片和群聊白名单",
          "3.0.0")
class YaYaPlugin(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}
        # 会话状态: {group_id: {user_id: {"node_id": str, "ts": float}}}
        self._sessions: dict[str, dict[str, dict]] = {}

        # ========== Web API 注册 ==========
        context.register_web_api(
            f"/{PLUGIN_NAME}/rules", self.api_list_rules, ["GET"], "获取树形规则")
        context.register_web_api(
            f"/{PLUGIN_NAME}/rules/add", self.api_add_rule, ["POST"], "新增节点")
        context.register_web_api(
            f"/{PLUGIN_NAME}/rules/update", self.api_update_rule, ["POST"], "更新节点")
        context.register_web_api(
            f"/{PLUGIN_NAME}/rules/delete", self.api_delete_rule, ["POST"], "删除节点（级联）")
        context.register_web_api(
            f"/{PLUGIN_NAME}/rules/move", self.api_move_rule, ["POST"], "移动节点")

    async def initialize(self):
        logger.info("YaYa 多级菜单插件已初始化 v3.0.0")

    # ==================== 会话管理 ====================

    def _get_session(self, group_id: str, user_id: str) -> dict | None:
        gs = self._sessions.get(group_id, {})
        sess = gs.get(user_id)
        if sess and time.time() - sess["ts"] > SESSION_TIMEOUT:
            del gs[user_id]
            return None
        return sess

    def _set_session(self, group_id: str, user_id: str, node_id: str):
        self._sessions.setdefault(group_id, {})[user_id] = {
            "node_id": node_id, "ts": time.time()}

    def _clear_session(self, group_id: str, user_id: str):
        self._sessions.get(group_id, {}).pop(user_id, None)

    def _get_session_path(self, flat_nodes: list, group_id: str, user_id: str) -> list:
        """获取用户从根到当前节点的路径（用于"返回"操作）"""
        sess = self._get_session(group_id, user_id)
        if not sess:
            return []
        path = []
        current_id = sess["node_id"]
        lookup = {n["id"]: n for n in flat_nodes}
        while current_id and current_id in lookup:
            path.insert(0, current_id)
            current_id = lookup[current_id].get("parent_id")
        return path

    # ==================== Web API Handlers ====================

    async def api_list_rules(self):
        nodes = _load_rules()
        tree = _build_tree(nodes)
        return jsonify({"nodes": nodes, "tree": tree, "total": len(nodes)})

    async def api_add_rule(self):
        payload = (await request.get_json(silent=True)) or {}
        keyword = (payload.get("keyword") or "").strip()
        if not keyword:
            return jsonify({"status": "error", "message": "关键词不能为空"}), 400

        parent_id = payload.get("parent_id")
        if parent_id is not None:
            parent_id = str(parent_id).strip() or None

        node = {
            "id": uuid.uuid4().hex[:12],
            "parent_id": parent_id,
            "keyword": keyword,
            "reply_text": (payload.get("reply_text") or "").strip(),
            "reply_images": (payload.get("reply_images") or "").strip(),
        }
        nodes = _load_rules()
        nodes.append(node)
        _save_rules(nodes)
        logger.info(f"新增节点: {keyword} (parent={node['parent_id']})")
        return jsonify({"status": "ok", "data": {"node": node}})

    async def api_update_rule(self):
        payload = (await request.get_json(silent=True)) or {}
        node_id = (payload.get("id") or "").strip()
        if not node_id:
            return jsonify({"status": "error", "message": "节点 ID 不能为空"}), 400
        nodes = _load_rules()
        for n in nodes:
            if n["id"] == node_id:
                keyword = (payload.get("keyword") or "").strip()
                if not keyword:
                    return jsonify({"status": "error", "message": "关键词不能为空"}), 400
                n["keyword"] = keyword
                n["reply_text"] = (payload.get("reply_text") or "").strip()
                n["reply_images"] = (payload.get("reply_images") or "").strip()
                _save_rules(nodes)
                logger.info(f"更新节点: {keyword}")
                return jsonify({"status": "ok", "data": {"node": n}})
        return jsonify({"status": "error", "message": "节点不存在"}), 404

    async def api_delete_rule(self):
        payload = (await request.get_json(silent=True)) or {}
        node_id = (payload.get("id") or "").strip()
        if not node_id:
            return jsonify({"status": "error", "message": "节点 ID 不能为空"}), 400
        nodes = _load_rules()
        if not any(n["id"] == node_id for n in nodes):
            return jsonify({"status": "error", "message": "节点不存在"}), 404
        # 级联删除子树
        remove_ids = _collect_subtree_ids(nodes, node_id)
        new_nodes = [n for n in nodes if n["id"] not in remove_ids]
        _save_rules(new_nodes)
        logger.info(f"删除节点 {node_id} 及 {len(remove_ids) - 1} 个子节点")
        return jsonify({"status": "ok",
                        "data": {"deleted": node_id, "cascade": len(remove_ids) - 1}})

    async def api_move_rule(self):
        payload = (await request.get_json(silent=True)) or {}
        node_id = (payload.get("id") or "").strip()
        new_parent = payload.get("parent_id")
        if new_parent is not None:
            new_parent = str(new_parent).strip() or None
        if not node_id:
            return jsonify({"status": "error", "message": "节点 ID 不能为空"}), 400
        nodes = _load_rules()
        for n in nodes:
            if n["id"] == node_id:
                if new_parent and new_parent in _collect_subtree_ids(nodes, node_id):
                    return jsonify(
                        {"status": "error", "message": "不能移到自己的子节点下"}), 400
                n["parent_id"] = new_parent
                _save_rules(nodes)
                return jsonify({"status": "ok", "data": {"node": n}})
        return jsonify({"status": "error", "message": "节点不存在"}), 404

    # ==================== 消息监听（多级菜单导航） ====================

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        message_str = event.message_str.strip() if event.message_str else ""
        if not message_str:
            return

        group_id = str(event.message_obj.group_id)
        user_id = str(event.get_sender_id())

        # ---- 白名单检查 ----
        whitelist_str = self.config.get("group_whitelist", "")
        if whitelist_str.strip():
            whitelist = [g.strip() for g in
                         whitelist_str.strip().split("\n") if g.strip()]
            if group_id not in whitelist:
                return

        nodes = _load_rules()
        if not nodes:
            return

        # ---- 全局命令：退出 ----
        if message_str in ("退出", "关闭"):
            self._clear_session(group_id, user_id)
            yield event.plain_result("👋 已退出菜单。")
            return

        # ---- 检查会话状态 ----
        sess = self._get_session(group_id, user_id)

        if sess:
            # 用户正在菜单中
            current_id = sess["node_id"]

            # ---- "返回" 命令 ----
            if message_str in ("返回", "0", "back"):
                path = self._get_session_path(nodes, group_id, user_id)
                if len(path) <= 1:
                    self._clear_session(group_id, user_id)
                    yield event.plain_result("👋 已退出菜单。")
                else:
                    parent_id = path[-2]
                    self._set_session(group_id, user_id, parent_id)
                    parent_node = next(
                        (n for n in nodes if n["id"] == parent_id), None)
                    yield self._render_menu(event, nodes, parent_node)
                return

            # ---- 在当前节点的子节点中匹配 ----
            children = _get_children(nodes, current_id)
            matched = self._match_child(children, message_str)
            if matched:
                grand_children = _get_children(nodes, matched["id"])
                if grand_children:
                    # 还有子节点 → 进入下一级
                    self._set_session(group_id, user_id, matched["id"])
                    yield self._render_menu(event, nodes, matched)
                else:
                    # 叶子节点 → 发送回复并退出
                    self._clear_session(group_id, user_id)
                    yield self._render_reply(event, matched)
                return
            else:
                if children:
                    yield event.plain_result(
                        "❓ 没有这个选项，请输入序号或关键词。\r"
                        "发送 返回 回到上一级 | 发送 退出 关闭菜单")
                else:
                    yield event.plain_result(
                        "当前没有子选项，发送 返回 回到上一级。")
                return

        # ---- 无会话：搜索根节点 ----
        for node in nodes:
            if (not node.get("parent_id")
                    and node.get("keyword", "") in message_str):
                children = _get_children(nodes, node["id"])
                if children:
                    self._set_session(group_id, user_id, node["id"])
                    yield self._render_menu(event, nodes, node)
                else:
                    yield self._render_reply(event, node)
                return

    # ==================== 回复构建 ====================

    def _match_child(self, children: list, msg: str) -> dict | None:
        """在子节点列表中匹配用户输入（先序号，再关键词包含匹配）"""
        try:
            idx = int(msg) - 1
            if 0 <= idx < len(children):
                return children[idx]
        except ValueError:
            pass
        for c in children:
            kw = c.get("keyword", "")
            if kw and kw in msg:
                return c
        return None

    def _render_menu(self, event: AstrMessageEvent,
                     nodes: list, parent: dict | None):
        """渲染菜单：列出当前节点的所有子节点"""
        if not parent:
            return event.plain_result("菜单数据错误。")
        children = _get_children(nodes, parent["id"])
        if not children:
            self._clear_session(
                str(event.message_obj.group_id),
                str(event.get_sender_id()))
            return self._render_reply(event, parent)

        lines = []
        header = parent.get("reply_text", "").strip()
        lines.append(header if header else "请选择：")
        for i, c in enumerate(children, 1):
            lines.append(f"{i}. {c['keyword']}")
        lines.append("━━━━━━━━━━")
        lines.append("发送 返回/0 回到上一级 | 发送 退出 关闭菜单")
        return event.plain_result("\r".join(lines))

    def _render_reply(self, event: AstrMessageEvent, node: dict):
        """渲染最终回复（叶子节点：文本 + 图片）"""
        reply_text = node.get("reply_text", "")
        reply_images_str = node.get("reply_images", "")

        chain = []
        if reply_text.strip():
            chain.append(Plain(reply_text.strip().replace("\n", "\r")))

        if reply_images_str.strip():
            image_urls = [u.strip() for u in
                          reply_images_str.strip().split("\n") if u.strip()]
            for url in image_urls:
                try:
                    if url.startswith("http://") or url.startswith("https://"):
                        chain.append(Image.fromURL(url))
                    else:
                        chain.append(Image.fromFileSystem(url))
                except Exception as e:
                    logger.error(f"加载图片失败: {url}, 错误: {e}")

        if chain:
            if not self.config.get("use_ai_reply", False):
                event.stop_event()
            return event.chain_result(chain)
        return event.plain_result("（无回复内容）")

    async def terminate(self):
        logger.info("YaYa 多级菜单插件已卸载")
