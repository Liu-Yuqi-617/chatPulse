# ChatPulse — 今日开发计划

**日期：** 2026-10-26  
**今日主题：** 项目启动与可运行骨架  
**今日完成标准：** 本地可同时启动前端和后端；Dashboard 能读取后端健康状态和模拟数据；项目结构、配置方式与下一步接口已明确。

## 1. 今日必须完成（P0）

### 1.1 仓库与工程结构

- [ ] 建立 `frontend/`、`backend/`、`docs/` 目录。
- [ ] 初始化 React + TypeScript + Vite 前端。
- [ ] 初始化 FastAPI + Pydantic 后端。
- [ ] 添加根目录 README，写明本地启动命令。
- [ ] 添加 `.gitignore` 和 `.env.example`，禁止提交密钥。

### 1.2 后端最小骨架

- [ ] 提供 `GET /api/health`，返回服务状态和版本。
- [ ] 定义核心数据模型：`ChatMessage`、`Topic`、`QuestionGroup`、`Spotlight`。
- [ ] 提供内存状态容器，先支持单频道。
- [ ] 提供开发模拟接口 `POST /api/dev/simulate`。
- [ ] 配置 CORS，允许本地前端访问。

### 1.3 前端最小骨架

- [ ] 建立 Dashboard 三栏布局：Topic Radar、Question Queue、Live Spotlight。
- [ ] 显示后端连接状态。
- [ ] 使用模拟数据展示 Topics、Questions 和 Spotlight。
- [ ] 补齐加载中、无数据、连接失败三种基础状态。
- [ ] 确认桌面尺寸下布局可用。

### 1.4 联调与质量门槛

- [ ] 前端成功调用 `GET /api/health`。
- [ ] 通过模拟接口注入消息并在 Dashboard 中看到状态变化。
- [ ] 后端至少包含健康检查与数据模型单元测试。
- [ ] 运行一次前端构建和后端测试，记录结果。
- [ ] 确认仓库中没有 Token、Client Secret 或本地 `.env`。

## 2. 今日建议完成（P1）

- [ ] 定义 Dashboard WebSocket 消息事件格式。
- [ ] 为 Overlay 建立独立路由和透明空状态。
- [ ] 实现 Spotlight 的 Pin / Clear 内存状态闭环。
- [ ] 准备 3 组聊天模拟场景：重复问题、多话题、垃圾消息。
- [ ] 画出 Twitch EventSub 与 OAuth 的接入清单，供明天直接实施。

## 3. 今日暂不做

- Twitch OAuth 与真实 EventSub 连接。
- 正式 LLM 调用和语义聚类。
- 数据库与长期存储。
- 部署、OBS 实机调试和视觉精修。
- P1 AI 回复建议与趋势分析。

这些工作分别安排在后续 Twitch 集成、AI Pipeline 和 OBS 集成阶段，今天只预留清晰的接口边界。

## 4. 推荐执行顺序

1. 初始化目录、依赖、环境变量模板。
2. 创建 FastAPI 健康检查与核心模型。
3. 创建 React Dashboard 骨架。
4. 打通前端到后端健康检查。
5. 添加模拟消息与内存状态。
6. 完成 Pin / Clear Spotlight 最小闭环。
7. 添加测试、构建检查和 README。
8. 整理明日 Twitch 集成所需配置。

## 5. 时间盒

| 时间 | 工作内容 | 产出 |
|---|---|---|
| 09:00–10:00 | 工程初始化 | 前后端可分别启动 |
| 10:00–12:00 | 后端模型与 API | 健康检查、模拟接口、内存状态 |
| 13:00–15:30 | Dashboard 骨架 | 三栏 UI 与基础状态 |
| 15:30–17:00 | 前后端联调 | 模拟数据可进入 Dashboard |
| 17:00–18:00 | Spotlight 闭环 | Pin / Clear 可用 |
| 19:00–20:00 | 测试与文档 | 构建通过、测试通过、README 完成 |
| 20:00–20:30 | 收尾检查 | 明日 Twitch 接入清单 |

## 6. 今日验收演示

今日结束前应能完成下面的本地演示：

1. 启动 FastAPI。
2. 启动 React Dashboard。
3. Dashboard 显示后端为 Connected。
4. 注入一组模拟聊天消息。
5. 页面显示话题卡片和问题队列。
6. 点击 Pin 后 Spotlight 预览更新。
7. 点击 Clear 后 Spotlight 恢复空状态。

## 7. 明日进入条件

只有满足以下条件，明天才开始 Twitch OAuth / EventSub：

- [ ] 前后端启动命令可复现。
- [ ] API 数据模型已稳定。
- [ ] 模拟数据链路可用。
- [ ] Spotlight 状态闭环可用。
- [ ] 密钥配置只通过环境变量完成。

