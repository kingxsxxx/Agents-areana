// API client - unified API request manager
import { WebSocketClient, WSMessageType } from './websocket-client.js';

// API base URL: env override -> global override -> same-origin /api
const API_BASE =
    import.meta.env?.VITE_API_BASE ||
    window.API_BASE ||
    `${window.location.origin}/api`;

// WebSocket client cache
const wsClients = new Map();

/**
 * API 閿欒绫? */
class APIError extends Error {
    constructor(message, status, data = null) {
        super(message);
        this.name = 'APIError';
        this.status = status;
        this.data = data;
    }
}

/**
 * 閲嶈瘯閰嶇疆
 */
const RETRY_CONFIG = {
    maxAttempts: 3,
    retryDelay: 1000, // initial delay: 1s
    backoffMultiplier: 2, // exponential backoff multiplier
    retryableStatuses: [408, 429, 500, 502, 503, 504],
    nonRetryableStatuses: [400, 401, 403, 404],
    networkErrors: ['ECONNRESET', 'ETIMEDOUT', 'EAI_AGAIN']
};

/**
 * 寤惰繜鍑芥暟
 * @param {number} ms 寤惰繜姣鏁? * @returns {Promise<void>}
 */
function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * 鍒ゆ柇閿欒鏄惁鍙噸璇? * @param {Error} error 閿欒瀵硅薄
 * @returns {boolean}
 */
function isRetryableError(error) {
    // 璁よ瘉閿欒涓嶅彲閲嶈瘯
    if (error instanceof APIError && RETRY_CONFIG.nonRetryableStatuses.includes(error.status)) {
        return false;
    }

    // 缃戠粶閿欒
    if (error.name === 'TypeError' && error.message.includes('fetch')) {
        return true;
    }

    // 缃戠粶閿欒浠ｇ爜
    if (RETRY_CONFIG.networkErrors.some(code => error.message.includes(code))) {
        return true;
    }

    // HTTP 鐘舵€佺爜
    if (error instanceof APIError && RETRY_CONFIG.retryableStatuses.includes(error.status)) {
        return true;
    }

    return false;
}

/**
 * 甯﹂噸璇曟満鍒剁殑璇锋眰鍑芥暟
 * @param {string} url 璇锋眰 URL
 * @param {object} options fetch 閫夐」
 * @param {number} attempt 褰撳墠灏濊瘯娆℃暟
 * @returns {Promise<Response>}
 */
async function fetchWithRetry(url, options = {}, attempt = 1) {
    try {
        const response = await fetch(url, options);

        // 妫€鏌ュ搷搴旂姸鎬?        if (!response.ok) {
            let errorMessage = `HTTP ${response.status}`;
            let errorData = null;

            try {
                const contentType = response.headers.get('content-type');
                if (contentType && contentType.includes('application/json')) {
                    const json = await response.json();
                    errorData = json;
                    errorMessage = json.message || json.detail || errorMessage;
                } else {
                    const text = await response.text();
                    errorMessage = text || errorMessage;
                }
            } catch (e) {
                // 鏃犳硶瑙ｆ瀽閿欒鍝嶅簲
            }

            throw new APIError(errorMessage, response.status, errorData);
        }

        return response;
    } catch (error) {
        // 濡傛灉涓嶅彲閲嶈瘯鎴栧凡杈惧埌鏈€澶ч噸璇曟鏁帮紝鎶涘嚭閿欒
        if (!isRetryableError(error) || attempt >= RETRY_CONFIG.maxAttempts) {
            throw error;
        }

        // 璁＄畻寤惰繜鏃堕棿锛堟寚鏁伴€€閬匡級
        const delayMs = RETRY_CONFIG.retryDelay * Math.pow(RETRY_CONFIG.backoffMultiplier, attempt - 1);
        console.warn(`API 璇锋眰澶辫触锛?{delayMs}ms 鍚庤繘琛岀 ${attempt + 1} 娆￠噸璇?..`, error.message);

        await delay(delayMs);
        return fetchWithRetry(url, options, attempt + 1);
    }
}

/**
 * 缁熶竴鍝嶅簲澶勭悊
 * @param {Response} response fetch 鍝嶅簲瀵硅薄
 * @returns {Promise<object>}
 */
async function handleResponse(response) {
    const contentType = response.headers.get('content-type');

    if (contentType && contentType.includes('application/json')) {
        return await response.json();
    }

    return await response.text();
}

/**
 * 鑾峰彇璁よ瘉浠ょ墝
 * @returns {string|null}
 */
function getToken() {
    try {
        const userData = localStorage.getItem('agoraUser');
        if (userData) {
            const user = JSON.parse(userData);
            return user.access_token || user.token;
        }
    } catch (error) {
        console.error('鑾峰彇浠ょ墝澶辫触:', error);
    }
    return null;
}

/**
 * 淇濆瓨鐢ㄦ埛鏁版嵁鍒版湰鍦板瓨鍌? * @param {object} data 鐢ㄦ埛鏁版嵁
 */
function saveUserData(data) {
    try {
        const userData = {
            id: data.user_id,
            username: data.username,
            email: data.email,
            access_token: data.access_token,
            refresh_token: data.refresh_token
        };
        localStorage.setItem('agoraUser', JSON.stringify(userData));
    } catch (error) {
        console.error('淇濆瓨鐢ㄦ埛鏁版嵁澶辫触:', error);
    }
}

/**
 * 娓呴櫎鐢ㄦ埛鏁版嵁
 */
function clearUserData() {
    try {
        localStorage.removeItem('agoraUser');
    } catch (error) {
        console.error('娓呴櫎鐢ㄦ埛鏁版嵁澶辫触:', error);
    }
}

/**
 * 甯﹁璇佺殑璇锋眰澶? * @param {object} headers 棰濆鐨勮姹傚ご
 * @returns {object}
 */
function getAuthHeaders(headers = {}) {
    const token = getToken();
    const defaultHeaders = {
        'Content-Type': 'application/json',
        ...headers
    };

    if (token) {
        defaultHeaders['Authorization'] = `Bearer ${token}`;
    }

    return defaultHeaders;
}

/**
 * 鍒锋柊浠ょ墝
 * @returns {Promise<boolean>}
 */
async function refreshToken() {
    try {
        const userData = localStorage.getItem('agoraUser');
        if (!userData) return false;

        const user = JSON.parse(userData);
        if (!user.refresh_token) return false;

        const response = await fetchWithRetry(`${API_BASE}/auth/refresh`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ refresh_token: user.refresh_token })
        });

        const data = await handleResponse(response);

        if (data.success || data.access_token) {
            saveUserData({
                ...user,
                ...data,
                ...data.data // 鍏煎涓嶅悓鐨勫搷搴旀牸寮?            });
            return true;
        }

        return false;
    } catch (error) {
        console.error('鍒锋柊浠ょ墝澶辫触:', error);
        clearUserData();
        return false;
    }
}

/**
 * API 瀹㈡埛绔? */
export const apiClient = {
    // ===== 璁よ瘉妯″潡 =====

    /**
     * 鐢ㄦ埛鐧诲綍
     * @param {string} username 鐢ㄦ埛鍚?     * @param {string} password 瀵嗙爜
     * @returns {Promise<object>}
     */
    async login(username, password) {
        try {
            const response = await fetchWithRetry(`${API_BASE}/auth/login`, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({ username, password })
            });

            const data = await handleResponse(response);

            // 鍏煎涓嶅悓鐨勫搷搴旀牸寮?            const result = data.data || data;

            if (result.access_token) {
                saveUserData(result);
                return result;
            }

            throw new APIError('鐧诲綍澶辫触', 500, data);
        } catch (error) {
            console.error('鐧诲綍澶辫触:', error);
            throw error;
        }
    },

    /**
     * 鐢ㄦ埛娉ㄥ唽
     * @param {string} username 鐢ㄦ埛鍚?     * @param {string} email 閭
     * @param {string} password 瀵嗙爜
     * @returns {Promise<object>}
     */
    async register(username, email, password) {
        try {
            const response = await fetchWithRetry(`${API_BASE}/auth/register`, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({ username, email, password })
            });

            const data = await handleResponse(response);

            // 鍏煎涓嶅悓鐨勫搷搴旀牸寮?            const result = data.data || data;

            if (result.access_token) {
                saveUserData(result);
                return result;
            }

            throw new APIError('娉ㄥ唽澶辫触', 500, data);
        } catch (error) {
            console.error('娉ㄥ唽澶辫触:', error);
            throw error;
        }
    },

    /**
     * 鍒锋柊浠ょ墝
     * @returns {Promise<object>}
     */
    async refreshAccessToken() {
        try {
            const response = await fetchWithRetry(`${API_BASE}/auth/refresh`, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({ refresh_token: JSON.parse(localStorage.getItem('agoraUser')).refresh_token })
            });

            const data = await handleResponse(response);
            const result = data.data || data;

            if (result.access_token) {
                saveUserData(result);
                return result;
            }

            throw new APIError('鍒锋柊浠ょ墝澶辫触', 500, data);
        } catch (error) {
            console.error('鍒锋柊浠ょ墝澶辫触:', error);
            throw error;
        }
    },

    /**
     * 鐢ㄦ埛鐧诲嚭
     * @returns {Promise<object>}
     */
    async logout() {
        try {
            const response = await fetchWithRetry(`${API_BASE}/auth/logout`, {
                method: 'POST',
                headers: getAuthHeaders()
            });

            const data = await handleResponse(response);
            clearUserData();
            return data;
        } catch (error) {
            console.error('鐧诲嚭澶辫触:', error);
            // 鍗充娇鐧诲嚭 API 澶辫触锛屼篃娓呴櫎鏈湴鏁版嵁
            clearUserData();
            throw error;
        }
    },

    /**
     * 鑾峰彇褰撳墠鐢ㄦ埛淇℃伅
     * @returns {Promise<object>}
     */
    async getCurrentUser() {
        try {
            const response = await fetchWithRetry(`${API_BASE}/auth/me`, {
                method: 'GET',
                headers: getAuthHeaders()
            });

            const data = await handleResponse(response);
            return data.data || data;
        } catch (error) {
            console.error('鑾峰彇鐢ㄦ埛淇℃伅澶辫触:', error);
            throw error;
        }
    },

    // ===== 杈╄绠＄悊妯″潡 =====

    /**
     * 鑾峰彇杈╄鍒楄〃
     * @param {string} token 璁块棶浠ょ墝锛堝彲閫夛紝榛樿浠?localStorage 鑾峰彇锛?     * @returns {Promise<object>}
     */
    async getDebates(token) {
        try {
            const headers = token ? getAuthHeaders() : getAuthHeaders();
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }

            const response = await fetchWithRetry(`${API_BASE}/debates`, {
                method: 'GET',
                headers
            });

            const data = await handleResponse(response);
            return data.data || data;
        } catch (error) {
            console.error('鑾峰彇杈╄鍒楄〃澶辫触:', error);
            throw error;
        }
    },

    /**
     * 鑾峰彇杈╄璇︽儏
     * @param {number} debateId 杈╄ ID
     * @returns {Promise<object>}
     */
    async getDebate(debateId) {
        try {
            const response = await fetchWithRetry(`${API_BASE}/debates/${debateId}`, {
                method: 'GET',
                headers: getAuthHeaders()
            });

            const data = await handleResponse(response);
            return data.data || data;
        } catch (error) {
            console.error('鑾峰彇杈╄璇︽儏澶辫触:', error);
            throw error;
        }
    },

    /**
     * 鍒涘缓杈╄
     * @param {string} title 杈╄鏍囬
     * @param {string} token 璁块棶浠ょ墝锛堝彲閫夛級
     * @returns {Promise<object>}
     */
    async createDebate(title, token) {
        try {
            const headers = getAuthHeaders();
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }

            const response = await fetchWithRetry(`${API_BASE}/debates`, {
                method: 'POST',
                headers,
                body: JSON.stringify({ title })
            });

            const data = await handleResponse(response);
            return data.data || data;
        } catch (error) {
            console.error('鍒涘缓杈╄澶辫触:', error);
            throw error;
        }
    },

    /**
     * 鏇存柊杈╄
     * @param {number} debateId 杈╄ ID
     * @param {object} updateData 鏇存柊鏁版嵁
     * @returns {Promise<object>}
     */
    async updateDebate(debateId, updateData) {
        try {
            const response = await fetchWithRetry(`${API_BASE}/debates/${debateId}`, {
                method: 'PUT',
                headers: getAuthHeaders(),
                body: JSON.stringify(updateData)
            });

            const data = await handleResponse(response);
            return data.data || data;
        } catch (error) {
            console.error('鏇存柊杈╄澶辫触:', error);
            throw error;
        }
    },

    /**
     * 鍒犻櫎杈╄
     * @param {number} debateId 杈╄ ID
     * @returns {Promise<object>}
     */
    async deleteDebate(debateId) {
        try {
            const response = await fetchWithRetry(`${API_BASE}/debates/${debateId}`, {
                method: 'DELETE',
                headers: getAuthHeaders()
            });

            const data = await handleResponse(response);
            return data;
        } catch (error) {
            console.error('鍒犻櫎杈╄澶辫触:', error);
            throw error;
        }
    },

    // ===== 瑙掕壊绠＄悊妯″潡 =====

    /**
     * 鍒涘缓 AI 瑙掕壊
     * @param {number} debateId 杈╄ ID
     * @param {object} agentConfig 瑙掕壊閰嶇疆
     * @returns {Promise<object>}
     */
    async createAgent(debateId, agentConfig) {
        try {
            const response = await fetchWithRetry(`${API_BASE}/debates/${debateId}/agents`, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify(agentConfig)
            });

            const data = await handleResponse(response);
            return data.data || data;
        } catch (error) {
            console.error('鍒涘缓瑙掕壊澶辫触:', error);
            throw error;
        }
    },

    /**
     * 鏇存柊 AI 瑙掕壊
     * @param {number} debateId 杈╄ ID
     * @param {number} agentId 瑙掕壊 ID
     * @param {object} updateData 鏇存柊鏁版嵁
     * @returns {Promise<object>}
     */
    async updateAgent(debateId, agentId, updateData) {
        try {
            const response = await fetchWithRetry(`${API_BASE}/debates/${debateId}/agents/${agentId}`, {
                method: 'PUT',
                headers: getAuthHeaders(),
                body: JSON.stringify(updateData)
            });

            const data = await handleResponse(response);
            return data.data || data;
        } catch (error) {
            console.error('鏇存柊瑙掕壊澶辫触:', error);
            throw error;
        }
    },

    /**
     * 鍒犻櫎 AI 瑙掕壊
     * @param {number} debateId 杈╄ ID
     * @param {number} agentId 瑙掕壊 ID
     * @returns {Promise<object>}
     */
    async deleteAgent(debateId, agentId) {
        try {
            const response = await fetchWithRetry(`${API_BASE}/debates/${debateId}/agents/${agentId}`, {
                method: 'DELETE',
                headers: getAuthHeaders()
            });

            const data = await handleResponse(response);
            return data;
        } catch (error) {
            console.error('鍒犻櫎瑙掕壊澶辫触:', error);
            throw error;
        }
    },

    // ===== 杈╄鎺у埗妯″潡 =====

    /**
     * 鍚姩杈╄
     * @param {number} debateId 杈╄ ID
     * @returns {Promise<object>}
     */
    async startDebate(debateId) {
        try {
            const response = await fetchWithRetry(`${API_BASE}/debates/${debateId}/start`, {
                method: 'POST',
                headers: getAuthHeaders()
            });

            const data = await handleResponse(response);
            return data.data || data;
        } catch (error) {
            console.error('鍚姩杈╄澶辫触:', error);
            throw error;
        }
    },

    /**
     * 鏆傚仠杈╄
     * @param {number} debateId 杈╄ ID
     * @returns {Promise<object>}
     */
    async pauseDebate(debateId) {
        try {
            const response = await fetchWithRetry(`${API_BASE}/debates/${debateId}/pause`, {
                method: 'POST',
                headers: getAuthHeaders()
            });

            const data = await handleResponse(response);
            return data.data || data;
        } catch (error) {
            console.error('鏆傚仠杈╄澶辫触:', error);
            throw error;
        }
    },

    /**
     * 鎭㈠杈╄
     * @param {number} debateId 杈╄ ID
     * @returns {Promise<object>}
     */
    async resumeDebate(debateId) {
        try {
            const response = await fetchWithRetry(`${API_BASE}/debates/${debateId}/resume`, {
                method: 'POST',
                headers: getAuthHeaders()
            });

            const data = await handleResponse(response);
            return data.data || data;
        } catch (error) {
            console.error('鎭㈠杈╄澶辫触:', error);
            throw error;
        }
    },

    /**
     * 缁堟杈╄
     * @param {number} debateId 杈╄ ID
     * @returns {Promise<object>}
     */
    async stopDebate(debateId) {
        try {
            const response = await fetchWithRetry(`${API_BASE}/debates/${debateId}/stop`, {
                method: 'POST',
                headers: getAuthHeaders()
            });

            const data = await handleResponse(response);
            return data.data || data;
        } catch (error) {
            console.error('缁堟杈╄澶辫触:', error);
            throw error;
        }
    },

    // ===== 鍙戣█璁板綍妯″潡 =====

    /**
     * 鑾峰彇杈╄鍙戣█璁板綍
     * @param {number} debateId 杈╄ ID
     * @returns {Promise<object>}
     */
    async getSpeeches(debateId) {
        try {
            const response = await fetchWithRetry(`${API_BASE}/debates/${debateId}/speeches`, {
                method: 'GET',
                headers: getAuthHeaders()
            });

            const data = await handleResponse(response);
            return data.data || data;
        } catch (error) {
            console.error('鑾峰彇鍙戣█璁板綍澶辫触:', error);
            throw error;
        }
    },

    // ===== 璇勫垎妯″潡 =====

    /**
     * 鑾峰彇杈╄璇勫垎
     * @param {number} debateId 杈╄ ID
     * @returns {Promise<object>}
     */
    async getScores(debateId) {
        try {
            const response = await fetchWithRetry(`${API_BASE}/debates/${debateId}/scores`, {
                method: 'GET',
                headers: getAuthHeaders()
            });

            const data = await handleResponse(response);
            return data.data || data;
        } catch (error) {
            console.error('鑾峰彇璇勫垎澶辫触:', error);
            throw error;
        }
    },

    // ===== 缁熻妯″潡 =====

    /**
     * 鑾峰彇绯荤粺缁熻淇℃伅
     * @returns {Promise<object>}
     */
    async getStats() {
        try {
            const response = await fetchWithRetry(`${API_BASE}/stats`, {
                method: 'GET',
                headers: getAuthHeaders()
            });

            const data = await handleResponse(response);
            return data.data || data;
        } catch (error) {
            console.error('鑾峰彇缁熻淇℃伅澶辫触:', error);
            throw error;
        }
    },

    // ===== WebSocket 绠＄悊 =====

    /**
     * 鍒涘缓 WebSocket 杩炴帴
     * @param {number} debateId 杈╄ ID
     * @param {object} eventHandlers 浜嬩欢澶勭悊鍣?     * @param {object} config WebSocket 閰嶇疆
     * @returns {WebSocketClient}
     */
    connectWebSocket(debateId, eventHandlers = {}, config = {}) {
        const token = getToken();
        if (!token) {
            throw new APIError('鏈壘鍒拌璇佷护鐗?, 401);
        }

        // 妫€鏌ユ槸鍚﹀凡鏈夌紦瀛樼殑 WebSocket 瀹㈡埛绔?        const cacheKey = `${debateId}`;
        if (wsClients.has(cacheKey)) {
            const existingClient = wsClients.get(cacheKey);
            if (existingClient.isConnected) {
                console.log('浣跨敤宸茬紦瀛樼殑 WebSocket 杩炴帴');
                // 鏇存柊浜嬩欢澶勭悊鍣?                Object.keys(eventHandlers).forEach(key => {
                    existingClient.on(key, eventHandlers[key]);
                });
                return existingClient;
            }
        }

        // 鍒涘缓鏂扮殑 WebSocket 瀹㈡埛绔?        const wsClient = new WebSocketClient(debateId, eventHandlers, config);

        // 缂撳瓨 WebSocket 瀹㈡埛绔?        wsClients.set(cacheKey, wsClient);

        // 杩炴帴 WebSocket
        wsClient.connect();

        return wsClient;
    },

    /**
     * 鏂紑骞剁Щ闄?WebSocket 杩炴帴
     * @param {number} debateId 杈╄ ID
     */
    disconnectWebSocket(debateId) {
        const cacheKey = `${debateId}`;
        if (wsClients.has(cacheKey)) {
            const client = wsClients.get(cacheKey);
            client.disconnect();
            wsClients.delete(cacheKey);
        }
    },

    /**
     * 鏂紑鎵€鏈?WebSocket 杩炴帴
     */
    disconnectAllWebSockets() {
        wsClients.forEach((client) => {
            client.disconnect();
        });
        wsClients.clear();
    }
};

/**
 * 杈呭姪鍑芥暟锛氫粠 API 閿欒涓彁鍙栫敤鎴峰弸濂界殑閿欒娑堟伅
 * @param {Error|APIError} error 閿欒瀵硅薄
 * @returns {string}
 */
export function getErrorMessage(error) {
    if (error instanceof APIError) {
        return error.message || '璇锋眰澶辫触';
    }

    if (error.name === 'TypeError' && error.message.includes('fetch')) {
        return '缃戠粶杩炴帴澶辫触锛岃妫€鏌ョ綉缁滆缃?;
    }

    return error.message || '鍙戠敓鏈煡閿欒';
}

export default apiClient;
export { WebSocketClient, WSMessageType };

