# AI Debate Arena

本项目支持本地与服务器部署，运行部署方式基于 Docker Compose。

---

## 1.项目启动与部署

### 1) 配置环境变量

```
cd ./Debate_arena
```

```powershell
vim .env
```

只需要改 2 类配置即可启动：

1. `SECRET_KEY`
2. 至少一个可用模型 Key（推荐先配 Qwen）

建议在 `.env` 中至少确认：

- `SECRET_KEY=...`
- `QWEN_API_KEY=...`(前往阿里百炼云平台获取)
- `QWEN_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1`
- `QWEN_MODEL=qwen-turbo`(可根据QWEN大模型平台官网自行更改)
- 其他模型的配置类似 

### 2) 启动

```powershell
docker compose up -d --build
```

### 3) 验证
```powershell
docker compose ps
docker compose logs -f app
```

## 

## 2.常见问题

### 1) 发言生成失败
优先检查：
- `.env` 中是否已填写 `QWEN_API_KEY`
- `QWEN_API_BASE` 是否是 `https://dashscope.aliyuncs.com/compatible-mode/v1`
- `docker compose logs -f app` 是否有上游模型报错

### 2) 页面改了但看不到
- 先浏览器强刷 `Ctrl+F5`
- 后端改动：`docker compose up -d --build app`
- 前端改动：`docker compose restart nginx`

