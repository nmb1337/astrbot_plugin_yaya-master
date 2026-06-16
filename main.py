import json
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


def _get_rules_path() -> Path:
    """获取关键词规则数据文件路径"""
    data_dir = Path(get_astrbot_plugin_data_path()) / PLUGIN_NAME
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / RULES_FILE


def _load_rules() -> list:
    """从磁盘加载关键词规则"""
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
    """保存关键词规则到磁盘"""
    path = _get_rules_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rules, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存关键词规则失败: {e}")
        raise


@register("astrbot_plugin_yaya", "贾梦", "关键词自动回复插件，支持多图片回复和群聊白名单，使用 Plugin Page 管理规则", "2.0.0")
class YaYaPlugin(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}

        # ========== 注册 Plugin Page 后端 Web API ==========
        # 获取所有规则
        context.register_web_api(
            f"/{PLUGIN_NAME}/rules",
            self.api_list_rules,
            ["GET"],
            "获取所有关键词回复规则",
        )
        # 新增规则
        context.register_web_api(
            f"/{PLUGIN_NAME}/rules/add",
            self.api_add_rule,
            ["POST"],
            "新增一条关键词回复规则",
        )
        # 更新规则
        context.register_web_api(
            f"/{PLUGIN_NAME}/rules/update",
            self.api_update_rule,
            ["POST"],
            "更新指定关键词回复规则",
        )
        # 删除规则
        context.register_web_api(
            f"/{PLUGIN_NAME}/rules/delete",
            self.api_delete_rule,
            ["POST"],
            "删除指定关键词回复规则",
        )

    async def initialize(self):
        """插件初始化"""
        logger.info("YaYa 关键词回复插件已初始化（Plugin Page 模式）")

    # ==================== Web API Handlers ====================

    async def api_list_rules(self):
        """GET /rules — 返回所有规则"""
        rules = _load_rules()
        return jsonify({"rules": rules, "total": len(rules)})

    async def api_add_rule(self):
        """POST /rules/add — 新增一条规则"""
        payload = (await request.get_json(silent=True)) or {}
        keyword = (payload.get("keyword") or "").strip()
        if not keyword:
            return jsonify({"status": "error", "message": "关键词不能为空"}), 400

        rule = {
            "id": uuid.uuid4().hex[:12],
            "keyword": keyword,
            "reply_text": (payload.get("reply_text") or "").strip(),
            "reply_images": (payload.get("reply_images") or "").strip(),
        }
        rules = _load_rules()
        rules.append(rule)
        _save_rules(rules)
        logger.info(f"新增关键词规则: {keyword}")
        return jsonify({"status": "ok", "data": {"rule": rule}})

    async def api_update_rule(self):
        """POST /rules/update — 更新一条规则"""
        payload = (await request.get_json(silent=True)) or {}
        rule_id = (payload.get("id") or "").strip()
        if not rule_id:
            return jsonify({"status": "error", "message": "规则 ID 不能为空"}), 400
        rules = _load_rules()
        for rule in rules:
            if rule.get("id") == rule_id:
                keyword = (payload.get("keyword") or "").strip()
                if not keyword:
                    return jsonify({"status": "error", "message": "关键词不能为空"}), 400
                rule["keyword"] = keyword
                rule["reply_text"] = (payload.get("reply_text") or "").strip()
                rule["reply_images"] = (payload.get("reply_images") or "").strip()
                _save_rules(rules)
                logger.info(f"更新关键词规则: {keyword}")
        return jsonify({"status": "ok", "data": {"rule": rule}})
        rule_id = (payload.get("id") or "").strip()
        if not rule_id:
            return jsonify({"status": "error", "message": "规则 ID 不能为空"}), 400
        rules = _load_rules()
        new_rules = [r for r in rules if r.get("id") != rule_id]
        if len(new_rules) == len(rules):
            return jsonify({"status": "error", "message": "规则不存在"}), 404
        _save_rules(new_rules)
        logger.info(f"删除关键词规则: {rule_id}")
        return jsonify({"status": "ok", "data": {"deleted": rule_id}})

    # ==================== 消息监听 ====================

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        """监听群消息，匹配关键词并自动回复"""
        message_str = event.message_str
        if not message_str:
            return

        group_id = str(event.message_obj.group_id)

        # 群聊白名单检查
        whitelist_str = self.config.get("group_whitelist", "")
        if whitelist_str.strip():
            whitelist = [
                g.strip() for g in whitelist_str.strip().split("\n") if g.strip()
            ]
            if group_id not in whitelist:
                return

        # 从磁盘加载关键词规则
        keywords_rules = _load_rules()
        if not keywords_rules:
            return

        # 匹配关键词（包含匹配）
        matched_rule = None
        for rule in keywords_rules:
            keyword = rule.get("keyword", "")
            if keyword and keyword in message_str:
                matched_rule = rule
                break

        if not matched_rule:
            return

        # 构建回复消息链
        reply_text = matched_rule.get("reply_text", "")
        reply_images_str = matched_rule.get("reply_images", "")

        chain = []
        if reply_text.strip():
            chain.append(Plain(reply_text.strip()))

        if reply_images_str.strip():
            image_urls = [
                url.strip()
                for url in reply_images_str.strip().split("\n")
                if url.strip()
            ]
            for url in image_urls:
                try:
                    if url.startswith("http://") or url.startswith("https://"):
                        chain.append(Image.fromURL(url))
                    else:
                        chain.append(Image.fromFileSystem(url))
                except Exception as e:
                    logger.error(f"加载图片失败: {url}, 错误: {e}")

        if chain:
            yield event.chain_result(chain)
            logger.info(
                f"关键词「{matched_rule.get('keyword')}」触发，群聊: {group_id}"
            )

        # 是否同时使用 AI 大模型回复
        use_ai = self.config.get("use_ai_reply", False)
        if not use_ai:
            event.stop_event()

    async def terminate(self):
        """插件卸载"""
        logger.info("YaYa 关键词回复插件已卸载")
