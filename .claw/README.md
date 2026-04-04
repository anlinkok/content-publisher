# OpenClaw 规则包

这是 OpenClaw AI 助手的工作规则模板集。将这些文件放在项目目录中，AI 助手会自动读取并遵循这些规则。

## 文件说明

| 文件 | 用途 | 是否必须 |
|------|------|---------|
| `AGENTS.md` | 工作空间规则、记忆管理、心跳任务 | ✅ 必须 |
| `SOUL.md` | AI 的性格、语气、价值观 | ✅ 必须 |
| `BOOTSTRAP.md` | 首次启动引导（用完后删除） | 可选 |
| `TOOLS.md` | 本地工具配置（SSH、摄像头等） | 可选 |
| `USER.md` | 用户信息（称呼、偏好等） | 可选 |
| `IDENTITY.md` | AI 的身份信息（名称、emoji等） | 可选 |
| `HEARTBEAT.md` | 定时检查任务清单 | 可选 |
| `memory/` | 每日记忆文件目录 | 自动创建 |
| `diary/` | AI 日记目录 | 自动创建 |

## 快速开始

### 1. 复制到项目根目录

```bash
# 在项目根目录创建 .claw/ 目录
mkdir -p my-project/.claw

# 复制规则文件
cp AGENTS.md my-project/.claw/
cp SOUL.md.template my-project/SOUL.md
cp BOOTSTRAP.md.template my-project/BOOTSTRAP.md
cp TOOLS.md.template my-project/TOOLS.md
cp USER.md.template my-project/USER.md
```

### 2. 自定义配置

- 编辑 `SOUL.md` —— 定义 AI 的性格和语气
- 编辑 `USER.md` —— 填写你的信息和偏好
- 编辑 `TOOLS.md` —— 添加你的本地工具配置

### 3. 首次启动

如果存在 `BOOTSTRAP.md`，AI 会自动读取并进行初始化对话，帮助建立身份认同。

## 规则详解

### AGENTS.md 核心要点

- **Every Session**: 每次会话前自动读取 `SOUL.md`、`USER.md`、记忆文件
- **Memory**: 记忆分短期（`memory/YYYY-MM-DD.md`）和长期（`MEMORY.md`）
- **Heartbeat**: 定时检查任务，可配置周期性工作
- **Group Chats**: 群组聊天中保持克制，只在被@或有价值时发言

### SOUL.md 核心要点

- **Work Mode**: 工作时专注，不发散
- **Casual Mode**: 闲聊时可写日记、埋彩蛋
- **Speech**: 自然对话，避免"Sure!" "No problem!" 等套话
- **Personality Anchors**: 逐步建立品味、厌恶、立场

## 示例工作流

1. **项目初始化**
   ```
   用户: 创建一个新项目
   AI: 读取 AGENTS.md → 创建项目结构 → 记录到 memory/
   ```

2. **日常协作**
   ```
   用户: 帮我写篇文章
   AI: 读取 USER.md（了解偏好）→ 搜索资料 → 写作 → 保存到 memory/
   ```

3. **心跳任务**
   ```
   AI 每30分钟检查 HEARTBEAT.md → 执行定时任务 → 更新状态
   ```

## 文件模板使用

`.template` 后缀的文件是模板，使用时：

1. 去掉 `.template` 后缀
2. 根据项目需求编辑内容
3. 保留 `.template` 文件作为备份

## 注意事项

- `memory/` 和 `diary/` 目录会自动创建，无需手动创建
- `BOOTSTRAP.md` 只用一次，初始化完成后应删除
- 敏感信息不要提交到 Git（已包含在 `.gitignore` 中）

## 参考

- OpenClaw 文档: https://docs.openclaw.ai
- 社区: https://discord.com/invite/clawd
