# Wechatsync 方案 A 快速启动指南

## 第一步：安装 Node.js

### Windows 用户：
```powershell
# 下载并安装 Node.js LTS 版本
# 访问：https://nodejs.org/ 下载安装包
# 或者使用 winget
winget install OpenJS.NodeJS.LTS

# 验证安装
node --version
npm --version
```

## 第二步：安装 Wechatsync CLI

```powershell
npm install -g @wechatsync/cli

# 验证安装
wechatsync --version
```

## 第三步：安装 Chrome 扩展

1. 打开 Chrome 浏览器
2. 访问 Chrome 应用商店，搜索 "文章同步助手" 或 "Wechatsync"
3. 点击安装
4. 安装后点击扩展图标，进入设置

## 第四步：启用 MCP 并获取 Token

1. 点击 Wechatsync 扩展图标
2. 进入「设置」→「高级设置」
3. 启用「MCP 连接」
4. 设置一个 Token（任意字符串，例如：`my-token-123`）
5. 复制 Token 备用

## 第五步：设置环境变量

### Windows PowerShell：
```powershell
$env:WECHATSYNC_TOKEN="your-token-here"

# 验证
wechatsync platforms --auth
```

### Windows CMD：
```cmd
set WECHATSYNC_TOKEN=your-token-here
wechatsync platforms --auth
```

### 永久设置（Windows）：
```powershell
# 添加到系统环境变量
[Environment]::SetEnvironmentVariable("WECHATSYNC_TOKEN", "your-token-here", "User")

# 重启 PowerShell 后生效
```

## 第六步：登录各平台

在 Chrome 浏览器中登录以下平台：
- https://www.zhihu.com （知乎）
- https://mp.toutiao.com （头条号）
- https://baijiahao.baidu.com （百家号）
- https://juejin.cn （掘金）
- https://www.csdn.net （CSDN）
- https://www.jianshu.com （简书）

登录后，Wechatsync 会自动检测到已登录的账号。

## 第七步：测试发布

### 查看支持的平台：
```powershell
wechatsync platforms
```

### 查看登录状态：
```powershell
wechatsync platforms --auth
```

### 同步 Markdown 文件：
```powershell
# 同步到单个平台
wechatsync sync "C:\Users\Administrator\Desktop\文章.md" -p zhihu

# 同步到多个平台
wechatsync sync "C:\Users\Administrator\Desktop\文章.md" -p zhihu,toutiao,baijiahao

# 同步到所有已登录平台
wechatsync sync "C:\Users\Administrator\Desktop\文章.md"
```

### 从 URL 提取并同步：
```powershell
wechatsync extract https://example.com/article -o article.md
wechatsync sync article.md -p zhihu,juejin
```

## 第八步：创建定时任务（可选）

### Windows 定时任务：
```powershell
# 创建每天 6:00 执行的定时任务
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-Command wechatsync sync 'C:\articles\morning.md' -p zhihu,toutiao,baijiahao"
$trigger = New-ScheduledTaskTrigger -Daily -At 6am
Register-ScheduledTask -TaskName "WechatsyncPublish" -Action $action -Trigger $trigger
```

## 支持的 29+ 平台 ID

| 平台 | ID | 类型 |
|------|-----|------|
| 知乎 | zhihu | 主流自媒体 |
| 头条号 | toutiao | 主流自媒体 |
| 百家号 | baijiahao | 主流自媒体 |
| 掘金 | juejin | 技术社区 |
| CSDN | csdn | 技术社区 |
| 简书 | jianshu | 通用 |
| 小红书 | xiaohongshu | 主流自媒体 |
| 微博 | weibo | 主流自媒体 |
| B站专栏 | bilibili | 通用 |
| 语雀 | yuque | 技术社区 |
| 豆瓣 | douban | 通用 |
| 搜狐号 | sohu | 通用 |
| 大鱼号 | dayu | 通用 |
| 一点号 | yidian | 通用 |
| 51CTO | 51cto | 技术社区 |
| 慕课网 | imooc | 技术社区 |
| 开源中国 | oschina | 技术社区 |
| SegmentFault | segmentfault | 技术社区 |
| 博客园 | cnblogs | 技术社区 |
| X (Twitter) | x | 海外 |
| 抖音图文 | douyin | 主流自媒体 |
| 微信公众号 | weixin | 主流自媒体 |
| WordPress | wordpress | 自建站 |
| Typecho | typecho | 自建站 |

## 常见问题

### Q: 提示 "未找到 Token"
确保设置了环境变量 `WECHATSYNC_TOKEN`，且 Chrome 扩展中启用了 MCP。

### Q: 提示平台未登录
需要在 Chrome 浏览器中打开对应平台网站并登录，Wechatsync 会自动读取 Cookie。

### Q: 同步后文章在哪里？
默认同步到各平台的**草稿箱**，需要你手动进入平台发布。

### Q: Word 文档怎么发布？
```powershell
# 先将 Word 转为 Markdown（需要安装 pandoc）
pandoc "文章.docx" -o "文章.md"
wechatsync sync "文章.md" -p zhihu,toutiao
```

## 下一步

测试成功后，可以：
1. 创建自动化脚本
2. 集成到 Claude Code / OpenClaw
3. 添加更多平台支持
