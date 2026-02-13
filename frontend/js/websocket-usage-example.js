// WebSocket 使用示例

// 从 api.js 导入
import apiClient, { WSMessageType } from './api.js';

/**
 * 示例 1: 基本连接和消息处理
 */
function basicConnectionExample(debateId) {
    const wsClient = apiClient.connectWebSocket(debateId, {
        // 连接成功回调
        onOpen: () => {
            console.log('WebSocket 连接已建立');
        },

        // 接收发言消息
        onSpeech: (data) => {
            console.log('收到发言消息:', data);
            console.log(`阶段: ${data.phase}, 发言人: ${data.agent_id}, 方: ${data.side}`);
            console.log(`内容: ${data.content}`);
        },

        // 接收状态更新
        onStatus: (data) => {
            console.log('收到状态更新:', data);
            console.log(`状态: ${data.status}, 阶段: ${data.current_phase}, 步骤: ${data.current_step}`);
        },

        // 接收评分
        onScore: (data) => {
            console.log('收到评分:', data);
            console.log(`正方得分: ${data.pro_score}, 反方得分: ${data.con_score}`);
            console.log(`获胜方: ${data.winner}`);
        },

        // 接收通知
        onNotification: (data) => {
            console.log('收到通知:', data);
            console.log(`类型: ${data.notification_type}, 消息: ${data.message}`);
        },

        // 接收错误
        onError: (error) => {
            console.error('收到错误:', error);
        },

        // 连接关闭
        onClose: (event) => {
            console.log('连接已关闭', event);
        }
    });

    return wsClient;
}

/**
 * 示例 2: 在辩论页面中使用 WebSocket
 */
class DebatePageManager {
    constructor(debateId) {
        this.debateId = debateId;
        this.wsClient = null;
        this.isConnected = false;

        // UI 元素
        this.elements = {
            speechContainer: document.getElementById('speech-container'),
            phaseIndicator: document.getElementById('phase-indicator'),
            statusIndicator: document.getElementById('status-indicator'),
            scoreDisplay: document.getElementById('score-display'),
            notificationArea: document.getElementById('notification-area')
        };

        this.initWebSocket();
    }

    initWebSocket() {
        this.wsClient = apiClient.connectWebSocket(this.debateId, {
            onOpen: () => this.handleOpen(),
            onSpeech: (data) => this.handleSpeech(data),
            onStatus: (data) => this.handleStatus(data),
            onScore: (data) => this.handleScore(data),
            onNotification: (data) => this.handleNotification(data),
            onError: (error) => this.handleError(error),
            onClose: (event) => this.handleClose(event)
        });
    }

    handleOpen() {
        console.log('辩论 WebSocket 已连接');
        this.isConnected = true;
        this.updateConnectionStatus('已连接');
    }

    handleSpeech(data) {
        // 添加发言到显示区域
        const speechElement = this.createSpeechElement(data);
        this.elements.speechContainer.appendChild(speechElement);

        // 滚动到底部
        this.elements.speechContainer.scrollTop = this.elements.speechContainer.scrollHeight;
    }

    handleStatus(data) {
        // 更新状态显示
        this.updateStatusDisplay(data);
    }

    handleScore(data) {
        // 更新评分显示
        this.updateScoreDisplay(data);
    }

    handleNotification(data) {
        // 显示通知
        this.showNotification(data);
    }

    handleError(error) {
        console.error('WebSocket 错误:', error);
        this.showNotification({
            notification_type: 'error',
            message: '连接发生错误'
        });
    }

    handleClose(event) {
        console.log('WebSocket 连接已关闭', event);
        this.isConnected = false;
        this.updateConnectionStatus('连接已断开');
    }

    // 辅助方法
    createSpeechElement(data) {
        const div = document.createElement('div');
        div.className = `speech-item ${data.side}`;
        div.innerHTML = `
            <div class="speech-header">
                <span class="speaker">${data.agent_id}</span>
                <span class="phase">${data.phase}</span>
                <span class="timestamp">${data.timestamp}</span>
            </div>
            <div class="speech-content">${data.content}</div>
        `;
        return div;
    }

    updateStatusDisplay(data) {
        if (this.elements.phaseIndicator) {
            this.elements.phaseIndicator.textContent = data.current_phase;
        }
        if (this.elements.statusIndicator) {
            this.elements.statusIndicator.textContent = data.status;
        }
    }

    updateScoreDisplay(data) {
        if (this.elements.scoreDisplay) {
            this.elements.scoreDisplay.innerHTML = `
                <div class="score pro">正方: ${data.pro_score}</div>
                <div class="score con">反方: ${data.con_score}</div>
                <div class="winner">获胜方: ${data.winner === 'pro' ? '正方' : '反方'}</div>
            `;
        }
    }

    showNotification(data) {
        if (this.elements.notificationArea) {
            const notification = document.createElement('div');
            notification.className = `notification ${data.notification_type}`;
            notification.textContent = data.message;
            this.elements.notificationArea.appendChild(notification);

            // 5秒后自动移除
            setTimeout(() => {
                notification.remove();
            }, 5000);
        }
    }

    updateConnectionStatus(status) {
        const statusElement = document.getElementById('connection-status');
        if (statusElement) {
            statusElement.textContent = status;
            statusElement.className = `connection-status ${this.isConnected ? 'connected' : 'disconnected'}`;
        }
    }

    // 清理
    destroy() {
        if (this.wsClient) {
            this.wsClient.disconnect();
        }
    }
}

/**
 * 示例 3: 带自定义配置的 WebSocket 连接
 */
function customConfigExample(debateId) {
    const wsClient = apiClient.connectWebSocket(debateId, {
        onOpen: () => console.log('连接成功'),
        onMessage: (data) => console.log('收到消息:', data),
        onClose: (event) => console.log('连接关闭')
    }, {
        // 重连配置
        enabled: true,
        maxAttempts: 10,
        baseDelay: 2000,
        maxDelay: 60000,
        backoffMultiplier: 2,
        heartbeatInterval: 45000
    });

    return wsClient;
}

/**
 * 示例 4: 手动管理 WebSocket 生命周期
 */
function manualLifecycleManagement(debateId) {
    let wsClient = null;

    // 连接
    function connect() {
        wsClient = apiClient.connectWebSocket(debateId, {
            onOpen: () => console.log('已连接'),
            onMessage: (data) => handleMessage(data),
            onError: (error) => console.error('错误:', error),
            onClose: (event) => console.log('已关闭')
        });
    }

    // 处理消息
    function handleMessage(data) {
        switch (data.type) {
            case WSMessageType.SPEECH:
                console.log('发言:', data.content);
                break;
            case WSMessageType.STATUS:
                console.log('状态:', data.status);
                break;
            case WSMessageType.SCORE:
                console.log('评分:', data);
                break;
            default:
                console.log('其他消息:', data);
        }
    }

    // 断开连接
    function disconnect() {
        apiClient.disconnectWebSocket(debateId);
    }

    // 重新连接
    function reconnect() {
        disconnect();
        setTimeout(connect, 1000);
    }

    return {
        connect,
        disconnect,
        reconnect
    };
}

/**
 * 示例 5: 使用 React Hooks (如果使用 React)
 */
// function useDebateWebSocket(debateId) {
//     const [isConnected, setIsConnected] = useState(false);
//     const [lastMessage, setLastMessage] = useState(null);
//     const wsClientRef = useRef(null);

//     useEffect(() => {
//         wsClientRef.current = apiClient.connectWebSocket(debateId, {
//             onOpen: () => setIsConnected(true),
//             onMessage: (data) => setLastMessage(data),
//             onClose: () => setIsConnected(false)
//         });

//         return () => {
//             apiClient.disconnectWebSocket(debateId);
//         };
//     }, [debateId]);

//     return { isConnected, lastMessage, wsClient: wsClientRef.current };
// }

// 导出示例
export {
    basicConnectionExample,
    DebatePageManager,
    customConfigExample,
    manualLifecycleManagement
};
