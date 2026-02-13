// WebSocket 客户端 - 带重连机制和消息类型处理

/**
 * WebSocket 消息类型
 */
export const WSMessageType = {
    SPEECH: 'speech',
    STATUS: 'status',
    SCORE: 'score',
    NOTIFICATION: 'notification',
    ERROR: 'error',
    CONNECTED: 'connected'
};

/**
 * WebSocket 重连配置
 */
const RECONNECT_CONFIG = {
    enabled: true,              // 是否启用自动重连
    maxAttempts: 5,             // 最大重连次数
    baseDelay: 1000,            // 基础延迟（毫秒）
    maxDelay: 30000,            // 最大延迟（毫秒）
    backoffMultiplier: 2,       // 指数退避倍数
    heartbeatInterval: 30000    // 心跳间隔（毫秒）
};

/**
 * WebSocket 客户端类
 */
export class WebSocketClient {
    constructor(debateId, eventHandlers = {}, config = {}) {
        this.debateId = debateId;
        this.eventHandlers = eventHandlers;
        this.config = { ...RECONNECT_CONFIG, ...config };

        // 连接状态
        this.ws = null;
        this.isConnecting = false;
        this.isConnected = false;
        this.shouldReconnect = true;
        this.reconnectAttempts = 0;
        this.reconnectTimer = null;
        this.heartbeatTimer = null;

        // 消息队列
        this.messageQueue = [];

        // 获取令牌
        this.getToken();
    }

    /**
     * 获取认证令牌
     */
    getToken() {
        try {
            const userData = localStorage.getItem('agoraUser');
            if (userData) {
                const user = JSON.parse(userData);
                this.token = user.access_token || user.token;
                return this.token;
            }
        } catch (error) {
            console.error('获取令牌失败:', error);
        }
        return null;
    }

    /**
     * 构建 WebSocket URL
     */
    buildUrl() {
        if (!this.token) {
            throw new Error('未找到认证令牌');
        }
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = process.env.WS_HOST || window.location.host;
        return `${protocol}//${host}/ws/debates/${this.debateId}?token=${encodeURIComponent(this.token)}`;
    }

    /**
     * 连接 WebSocket
     */
    connect() {
        if (this.isConnecting || this.isConnected) {
            console.log('WebSocket 已连接或正在连接');
            return;
        }

        this.isConnecting = true;
        this.getToken(); // 重新获取令牌

        try {
            const url = this.buildUrl();
            console.log('正在连接 WebSocket:', url);
            this.ws = new WebSocket(url);
            this.setupEventHandlers();
        } catch (error) {
            console.error('WebSocket 连接失败:', error);
            this.isConnecting = false;
            this.handleConnectionError(error);
        }
    }

    /**
     * 设置事件处理器
     */
    setupEventHandlers() {
        this.ws.onopen = () => {
            this.handleOpen();
        };

        this.ws.onmessage = (event) => {
            this.handleMessage(event);
        };

        this.ws.onerror = (error) => {
            this.handleError(error);
        };

        this.ws.onclose = (event) => {
            this.handleClose(event);
        };
    }

    /**
     * 处理连接打开事件
     */
    handleOpen() {
        console.log('WebSocket 连接已建立');
        this.isConnecting = false;
        this.isConnected = true;
        this.reconnectAttempts = 0;

        // 发送消息队列中的消息
        this.flushMessageQueue();

        // 启动心跳
        this.startHeartbeat();

        // 触发连接成功回调
        this.emit('onOpen');
    }

    /**
     * 处理消息事件
     */
    handleMessage(event) {
        try {
            const data = JSON.parse(event.data);
            console.log('WebSocket 消息:', data);

            // 重置心跳计时器
            this.resetHeartbeat();

            // 根据消息类型调用对应的处理器
            if (data.type) {
                switch (data.type) {
                    case WSMessageType.SPEECH:
                        this.emit('onSpeech', data);
                        break;
                    case WSMessageType.STATUS:
                        this.emit('onStatus', data);
                        break;
                    case WSMessageType.SCORE:
                        this.emit('onScore', data);
                        break;
                    case WSMessageType.NOTIFICATION:
                        this.emit('onNotification', data);
                        break;
                    case WSMessageType.ERROR:
                        this.emit('onError', data);
                        break;
                    case WSMessageType.CONNECTED:
                        this.emit('onConnected', data);
                        break;
                    default:
                        console.warn('未知的 WebSocket 消息类型:', data.type);
                }
            }

            // 通用消息回调
            this.emit('onMessage', data);
        } catch (error) {
            console.error('解析 WebSocket 消息失败:', error);
        }
    }

    /**
     * 处理错误事件
     */
    handleError(error) {
        console.error('WebSocket 错误:', error);
        this.emit('onError', error);
    }

    /**
     * 处理连接关闭事件
     */
    handleClose(event) {
        console.log('WebSocket 连接已关闭', event);
        this.isConnecting = false;
        this.isConnected = false;

        // 停止心跳
        this.stopHeartbeat();

        // 触发关闭回调
        this.emit('onClose', event);

        // 自动重连
        if (this.shouldReconnect && this.config.enabled) {
            this.scheduleReconnect();
        }
    }

    /**
     * 处理连接错误
     */
    handleConnectionError(error) {
        console.error('WebSocket 连接错误:', error);
        this.emit('onError', error);

        if (this.shouldReconnect && this.config.enabled) {
            this.scheduleReconnect();
        }
    }

    /**
     * 安排重连
     */
    scheduleReconnect() {
        if (this.reconnectAttempts >= this.config.maxAttempts) {
            console.log('已达到最大重连次数，停止重连');
            this.emit('onReconnectFailed');
            return;
        }

        // 计算重连延迟（指数退避）
        const delay = Math.min(
            this.config.baseDelay * Math.pow(this.config.backoffMultiplier, this.reconnectAttempts),
            this.config.maxDelay
        );

        this.reconnectAttempts++;
        console.log(`${delay}ms 后进行第 ${this.reconnectAttempts} 次重连...`);

        this.reconnectTimer = setTimeout(() => {
            this.connect();
        }, delay);
    }

    /**
     * 启动心跳
     */
    startHeartbeat() {
        this.stopHeartbeat();
        this.heartbeatTimer = setInterval(() => {
            if (this.isConnected && this.ws) {
                this.ws.send(JSON.stringify({ type: 'ping' }));
            }
        }, this.config.heartbeatInterval);
    }

    /**
     * 停止心跳
     */
    stopHeartbeat() {
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }
    }

    /**
     * 重置心跳计时器
     */
    resetHeartbeat() {
        // 这里可以实现心跳超时检测
        // 例如：如果在指定时间内没有收到消息，则认为连接断开
    }

    /**
     * 发送消息
     */
    send(message) {
        if (!this.isConnected || !this.ws) {
            console.warn('WebSocket 未连接，消息已加入队列');
            this.messageQueue.push(message);
            return false;
        }

        try {
            const messageString = typeof message === 'string' ? message : JSON.stringify(message);
            this.ws.send(messageString);
            return true;
        } catch (error) {
            console.error('发送消息失败:', error);
            this.messageQueue.push(message);
            return false;
        }
    }

    /**
     * 清空消息队列
     */
    flushMessageQueue() {
        while (this.messageQueue.length > 0) {
            const message = this.messageQueue.shift();
            if (!this.send(message)) {
                break;
            }
        }
    }

    /**
     * 断开连接
     */
    disconnect() {
        this.shouldReconnect = false;

        // 清除重连定时器
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }

        // 停止心跳
        this.stopHeartbeat();

        // 关闭 WebSocket 连接
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }

        this.isConnected = false;
        this.isConnecting = false;
    }

    /**
     * 重新连接
     */
    reconnect() {
        this.disconnect();
        this.shouldReconnect = true;
        this.reconnectAttempts = 0;
        this.connect();
    }

    /**
     * 触发事件
     */
    emit(eventName, data) {
        if (this.eventHandlers[eventName]) {
            this.eventHandlers[eventName](data);
        }
    }

    /**
     * 设置事件处理器
     */
    on(eventName, handler) {
        this.eventHandlers[eventName] = handler;
    }

    /**
     * 移除事件处理器
     */
    off(eventName) {
        delete this.eventHandlers[eventName];
    }
}

/**
 * 工厂函数：创建 WebSocket 客户端
 */
export function createWebSocketClient(debateId, eventHandlers = {}, config = {}) {
    return new WebSocketClient(debateId, eventHandlers, config);
}

/**
 * 简化的连接函数（向后兼容）
 */
export function connectWebSocket(debateId, eventHandlers = {}, config = {}) {
    const client = createWebSocketClient(debateId, eventHandlers, config);
    client.connect();
    return client;
}

export default WebSocketClient;
