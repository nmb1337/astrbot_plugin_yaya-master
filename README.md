# YaYa 关键词回复 🐟

群聊关键词自动回复插件，使用 **Plugin Page** 管理规则，支持多图片回复、群聊白名单，以及 AI 大模型回复联动控制。

## 👤 作者

**贾梦** — 一个爱敲代码的咸鱼 🐟

## ✨ 功能

- 🎯 **关键词自动回复**：在 Plugin Page（keyword-console）中动态管理关键词规则，群内有人发送包含关键词的消息时自动回复
- 🖼️ **多图片支持**：每条规则可配置多张图片 URL（支持 http/https 链接和本地路径）
- 📝 **自定义回复文本**：可自由编辑每条规则的回复文本
- 🔒 **群聊白名单**：在配置面板中设置群号白名单，仅白名单内的群聊触发此插件
- 🤖 **AI 联动控制**：可在配置面板选择触发关键词时是否同时使用 AI 大模型回复
- 🖥️ **Plugin Page 控制台**：通过 AstrBot WebUI → 插件详情 → keyword-console 页面，可视化增删改查关键词规则



## ⚙️ 配置

### 基础配置（配置面板）

在 AstrBot WebUI 的插件管理 → YaYa 关键词回复 → 配置面板：

| 配置项 | 说明 |
|--------|------|
| **群聊白名单** | 每行一个群号，留空则所有群聊生效 |
| **是否使用 AI 回复** | 开启后，触发关键词时 AI 大模型也会同时回复 |

### 关键词规则管理（Plugin Page）

在 AstrBot WebUI 的插件管理 → YaYa 关键词回复 → 点击 **keyword-console** 页面：

- ➕ 新增规则：填写触发关键词、回复文本、图片 URL（每行一个）
- ✏️ 编辑规则：修改已有规则的关键词、文本或图片
- 🗑️ 删除规则：移除不再需要的规则

> 规则数据存储在 AstrBot 的 `data/astrbot_plugin_yaya/` 目录下，更新插件不会覆盖规则数据。

## 🚀 使用示例

1. 打开 WebUI → 插件管理 → YaYa 关键词回复 → **keyword-console** 页面
2. 点击「+ 新增规则」，关键词 = `菜单`，回复文本 = `这是本群的菜单：`，图片 = `https://example.com/menu.jpg`
3. 在配置面板中，群聊白名单填入你的群号
4. 群内有人发送包含「菜单」的消息时，机器人自动回复文本和图片

## 🏗️ 技术架构

- **Plugin Page**：基于 AstrBot Plugin Pages 机制，`pages/keyword-console/` 提供完整的前端管理界面
- **Bridge API**：前端通过 `window.AstrBotPluginPage` bridge 调用后端 Web API
- **后端 Web API**：`context.register_web_api()` 注册 CRUD 接口，符合 AstrBot v4 新规范
- **数据持久化**：规则数据以 JSON 格式存储在 AstrBot 插件数据目录

## 📄 许可

MIT License
