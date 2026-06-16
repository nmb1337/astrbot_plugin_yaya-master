from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import Plain, Image


@register("astrbot_plugin_yaya", "贾梦", "关键词自动回复插件，支持多图片回复和群聊白名单", "1.0.0")
class YaYaPlugin(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}

    async def initialize(self):
        """插件初始化"""
        logger.info("YaYa 关键词回复插件已初始化")

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        """监听群消息，匹配关键词并自动回复"""
        message_str = event.message_str
        if not message_str:
            return

        group_id = str(event.message_obj.group_id)

        # === 群聊白名单检查 ===
        whitelist_str = self.config.get("group_whitelist", "")
        if whitelist_str.strip():
            whitelist = [
                g.strip() for g in whitelist_str.strip().split("\n") if g.strip()
            ]
            if group_id not in whitelist:
                return

        # === 获取关键词规则列表 ===
        keywords_rules = self.config.get("keywords", [])
        if not keywords_rules:
            return

        # === 匹配关键词（包含匹配） ===
        matched_rule = None
        for rule in keywords_rules:
            keyword = rule.get("keyword", "")
            if keyword and keyword in message_str:
                matched_rule = rule
                break

        if not matched_rule:
            return

        # === 构建回复消息链 ===
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

        # === 是否同时使用 AI 大模型回复 ===
        use_ai = self.config.get("use_ai_reply", False)
        if not use_ai:
            # 停止事件传播，阻止后续的 AI 大模型回复
            event.stop_event()

    async def terminate(self):
        """插件卸载"""
        logger.info("YaYa 关键词回复插件已卸载")
