# API 集成文档

## 概述

本项目已实现完整的前端与后端 API 集成功能，包括认证管理、辩论管理、角色管理、WebSocket 实时通信等模块。

## 文件结构

```
frontend/js/
├── api.js              # 核心 API 客户端
├── auth-service.js     # 认证服务
└── debate-service.js   # 辩论服务
```

## 1. API 客户端 (api.js)

### 功能特性

- 统一的 API 调用管理
- 自动错误处理和重试机制
- JWT 令牌管理
- WebSocket 连接支持

### 使用方法

#### 基本导入

```javascript
import apiClient, { getErrorMessage } from './js/api.js';
```

#### 认证 API

```javascript
// 用户登录
const result = await apiClient.login(username, password);

// 用户注册
const result = await apiClient.register(username, email, password);

// 获取当前用户信息
const userInfo = await apiClient.getCurrentUser();

// 用户登出
await apiClient.logout();
```

#### 辩论管理 API

```javascript
// 获取辩论列表
const debates = await apiClient.getDebates();

// 获取辩论详情
const debate = await apiClient.getDebate(debateId);

// 创建辩论
const result = await apiClient.createDebate(title);

// 更新辩论
await apiClient.updateDebate(debateId, { title: '新标题' });

// 删除辩论
await apiClient.deleteDebate(debateId);
```

#### 辩论控制 API

```javascript
// 启动辩论
await apiClient.startDebate(debateId);

// 暂停辩论
await apiClient.pauseDebate(debateId);

// 恢复辩论
await apiClient.resumeDebate(debateId);

// 终止辩论
await apiClient.stopDebate(debateId);
```

#### 角色管理 API

```javascript
// 创建 AI 角色
const agent = await apiClient.createAgent(debateId, {
    agent_type: 'debater',
    position: 'pro-1',
    side: 'pro',
    name: '张三',
    ai_model: 'DeepSeek',
    gender: '男',
    age: 35,
    job: '大学教授',
    mbti: 'INTJ',
    params: {
        aggression: 60,
        logic: 80,
        rhetoric: 70,
        emotional: 40
    }
});

// 更新角色
await apiClient.updateAgent(debateId, agentId, { name: '新名称' });

// 删除角色
await apiClient.deleteAgent(debateId, agentId);
```

#### 发言记录 API

```javascript
// 获取辩论发言记录
const speeches = await apiClient.getSpeeches(debateId);
```

#### 评分 API

```javascript
// 获取辩论评分
const scores = await apiClient.getScores(debateId);
```

#### WebSocket API

```javascript
// 创建 WebSocket 连接
const ws = apiClient.connectWebSocket(debateId, {
    onOpen: () => console.log('连接已建立'),
    onMessage: (data) => console.log('收到消息:', data),
    onError: (error) => console.error('连接错误:', error),
    onClose: () => console.log('连接已关闭'),

    // 消息类型处理器
    debate_started: (data) => console.log('辩论已开始:', data),
    debate_paused: (data) => console.log('辩论已暂停:', data),
    speech: (data) => console.log('收到发言:', data)
});
```

### 错误处理

```javascript
import { getErrorMessage } from './js/api.js';

try {
    const result = await apiClient.login(username, password);
} catch (error) {
    const message = getErrorMessage(error);
    alert(message);
}
```

## 2. 认证服务 (auth-service.js)

### 功能特性

- 统一的认证状态管理
- 自动令牌刷新
- 会话验证
- 本地存储管理

### 使用方法

```javascript
import authService from './js/auth-service.js';

// 用户登录
await authService.login(username, password);

// 用户注册
await authService.register(username, email, password);

// 检查是否已认证
if (authService.isAuthenticatedUser()) {
    console.log('用户已登录');
}

// 获取当前用户
const user = authService.getUser();

// 获取访问令牌
const token = authService.getAccessToken();

// 用户登出
await authService.logout();

// 验证会话
const isValid = await authService.validateSession();

// 订阅认证状态变化
const unsubscribe = authService.subscribe((user) => {
    console.log('用户状态变化:', user);
});

// 取消订阅
unsubscribe();
```

## 3. 辩论服务 (debate-service.js)

### 功能特性

- 辩论 CRUD 操作
- 角色管理
- 批量操作
- 数据格式化

### 使用方法

```javascript
import debateService from './js/debate-service.js';

// 获取辩论列表
const debates = await debateService.getDebates();

// 创建辩论
const debate = await debateService.createDebate('人工智能是否有意识？');

// 启动辩论
await debateService.startDebate(debateId);

// 批量创建角色
const agents = await debateService.createAgents(debateId, [
    { /* 角色配置 1 */ },
    { /* 角色配置 2 */ }
]);

// 格式化辩论状态
const status = debateService.formatDebateStatus('running'); // '进行中'
```

## 错误处理机制

### 重试策略

API 客户端内置了智能重试机制：

- 最大重试次数：3 次
- 初始延迟：1 秒
- 退避倍数：2（指数退避）
- 可重试状态码：408, 429, 500, 502, 503, 504

### 网络错误处理

自动重试以下网络错误：
- ECONNRESET（连接重置）
- ETIMEDOUT（连接超时）
- EAI_AGAIN（DNS 解析临时失败）

### 错误类型

```javascript
class APIError extends Error {
    constructor(message, status, data = null) {
        super(message);
        this.name = 'APIError';
        this.status = status;
        this.data = data;
    }
}
```

## 本地存储

### 数据结构

```json
{
    "id": 123,
    "user_id": 123,
    "username": "用户名",
    "email": "user@example.com",
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

### 存储键名

- `agoraUser`：用户数据（包含令牌）

## 安全注意事项

1. 令牌过期处理：客户端会自动尝试刷新令牌
2. HTTPS 传输：生产环境必须使用 HTTPS
3. 令牌存储：使用 localStorage 存储（可考虑迁移到 httpOnly cookies）
4. CSRF 保护：后端已实现相关保护机制

## WebSocket 消息类型

### 客户端发送

- `ping`：心跳消息

### 服务端发送

- `debate_started`：辩论开始
- `debate_paused`：辩论暂停
- `debate_resumed`：辩论恢复
- `debate_finished`：辩论结束
- `speech`：新发言
- `score`：新评分
- `notification`：系统通知

## 配置项

```javascript
const RETRY_CONFIG = {
    maxAttempts: 3,           // 最大重试次数
    retryDelay: 1000,         // 初始延迟（毫秒）
    backoffMultiplier: 2,      // 退避倍数
    retryableStatuses: [       // 可重试的状态码
        408, 429, 500, 502, 503, 504
    ],
    networkErrors: [           // 可重试的网络错误代码
        'ECONNRESET', 'ETIMEDOUT', 'EAI_AGAIN'
    ]
};
```

## 更新日志

### v1.0.0 (2026-02-11)

- 实现 API 客户端核心功能
- 添加认证服务和辩论服务
- 实现错误处理和重试机制
- 支持 WebSocket 连接
- 集成到前端 index.html
