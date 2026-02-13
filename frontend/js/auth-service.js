// 认证服务 - 统一的认证状态管理
import apiClient, { getErrorMessage } from './api.js';

/**
 * 认证服务
 * 提供统一的认证状态管理和相关方法
 */
class AuthService {
    constructor() {
        // 认证状态
        this.isAuthenticated = false;
        this.currentUser = null;
        this.accessToken = null;
        this.refreshToken = null;

        // 事件监听器
        this.listeners = new Set();

        // 加载已保存的用户
        this.loadSavedUser();
    }

    /**
     * 加载已保存的用户数据
     */
    loadSavedUser() {
        try {
            const savedUser = localStorage.getItem('agoraUser');
            if (savedUser) {
                const user = JSON.parse(savedUser);
                this.currentUser = user;
                this.accessToken = user.access_token;
                this.refreshToken = user.refresh_token;
                this.isAuthenticated = true;
            }
        } catch (error) {
            console.error('加载用户数据失败:', error);
        }
    }

    /**
     * 保存用户数据到本地存储
     */
    saveUserData() {
        if (this.currentUser) {
            try {
                const userData = {
                    id: this.currentUser.id,
                    user_id: this.currentUser.user_id || this.currentUser.id,
                    username: this.currentUser.username,
                    email: this.currentUser.email,
                    access_token: this.accessToken,
                    refresh_token: this.refreshToken
                };
                localStorage.setItem('agoraUser', JSON.stringify(userData));
            } catch (error) {
                console.error('保存用户数据失败:', error);
            }
        }
    }

    /**
     * 清除用户数据
     */
    clearUserData() {
        try {
            localStorage.removeItem('agoraUser');
        } catch (error) {
            console.error('清除用户数据失败:', error);
        }
    }

    /**
     * 添加状态变化监听器
     * @param {Function} listener 监听器函数
     * @returns {Function} 取消监听函数
     */
    subscribe(listener) {
        this.listeners.add(listener);
        return () => this.listeners.delete(listener);
    }

    /**
     * 通知所有监听器
     */
    notifyListeners() {
        this.listeners.forEach(listener => listener(this.currentUser));
    }

    /**
     * 用户登录
     * @param {string} username 用户名
     * @param {string} password 密码
     * @returns {Promise<object>}
     */
    async login(username, password) {
        try {
            const result = await apiClient.login(username, password);

            this.currentUser = {
                id: result.user_id,
                user_id: result.user_id,
                username: result.username,
                email: result.email
            };
            this.accessToken = result.access_token;
            this.refreshToken = result.refresh_token;
            this.isAuthenticated = true;

            this.saveUserData();
            this.notifyListeners();

            return result;
        } catch (error) {
            console.error('登录失败:', error);
            throw error;
        }
    }

    /**
     * 用户注册
     * @param {string} username 用户名
     * @param {string} email 邮箱
     * @param {string} password 密码
     * @returns {Promise<object>}
     */
    async register(username, email, password) {
        try {
            const result = await apiClient.register(username, email, password);

            this.currentUser = {
                id: result.user_id,
                user_id: result.user_id,
                username: result.username,
                email: result.email
            };
            this.accessToken = result.access_token;
            this.refreshToken = result.refresh_token;
            this.isAuthenticated = true;

            this.saveUserData();
            this.notifyListeners();

            return result;
        } catch (error) {
            console.error('注册失败:', error);
            throw error;
        }
    }

    /**
     * 刷新访问令牌
     * @returns {Promise<object>}
     */
    async refreshAccessToken() {
        try {
            const result = await apiClient.refreshAccessToken();

            this.accessToken = result.access_token;
            this.refreshToken = result.refresh_token;

            if (result.user_id) {
                this.currentUser.user_id = result.user_id;
            }

            this.saveUserData();
            this.notifyListeners();

            return result;
        } catch (error) {
            console.error('刷新令牌失败:', error);
            await this.logout();
            throw error;
        }
    }

    /**
     * 用户登出
     * @returns {Promise<void>}
     */
    async logout() {
        try {
            await apiClient.logout();
        } catch (error) {
            console.error('登出 API 调用失败:', error);
        } finally {
            this.currentUser = null;
            this.accessToken = null;
            this.refreshToken = null;
            this.isAuthenticated = false;

            this.clearUserData();
            this.notifyListeners();
        }
    }

    /**
     * 获取当前用户信息
     * @returns {Promise<object>}
     */
    async getCurrentUser() {
        try {
            const result = await apiClient.getCurrentUser();

            this.currentUser = {
                id: result.user_id,
                user_id: result.user_id,
                username: result.username,
                email: result.email
            };

            this.saveUserData();
            this.notifyListeners();

            return result;
        } catch (error) {
            console.error('获取用户信息失败:', error);
            throw error;
        }
    }

    /**
     * 检查用户是否已认证
     * @returns {boolean}
     */
    isAuthenticatedUser() {
        return this.isAuthenticated && !!this.accessToken;
    }

    /**
     * 获取访问令牌
     * @returns {string|null}
     */
    getAccessToken() {
        return this.accessToken;
    }

    /**
     * 获取当前用户
     * @returns {object|null}
     */
    getUser() {
        return this.currentUser;
    }

    /**
     * 验证用户会话（检查令牌是否有效）
     * @returns {Promise<boolean>}
     */
    async validateSession() {
        try {
            if (!this.accessToken) {
                return false;
            }

            await this.getCurrentUser();
            return true;
        } catch (error) {
            console.error('会话验证失败:', error);

            // 尝试刷新令牌
            try {
                await this.refreshAccessToken();
                return true;
            } catch (refreshError) {
                console.error('刷新令牌失败:', refreshError);
                return false;
            }
        }
    }

    /**
     * 检查并刷新令牌（在过期前）
     * @param {number} secondsBefore 过期前多少秒刷新
     * @returns {Promise<void>}
     */
    async checkAndRefreshToken(secondsBefore = 60) {
        try {
            // 解析 JWT 令牌获取过期时间
            const payload = this.parseJWT(this.accessToken);

            if (payload && payload.exp) {
                const expiryTime = payload.exp * 1000; // 转换为毫秒
                const currentTime = Date.now();
                const timeUntilExpiry = expiryTime - currentTime;

                // 如果令牌即将过期，刷新它
                if (timeUntilExpiry < secondsBefore * 1000) {
                    console.log('令牌即将过期，正在刷新...');
                    await this.refreshAccessToken();
                }
            }
        } catch (error) {
            console.error('检查令牌过期时间失败:', error);
        }
    }

    /**
     * 解析 JWT 令牌
     * @param {string} token JWT 令牌
     * @returns {object|null}
     */
    parseJWT(token) {
        try {
            const base64Url = token.split('.')[1];
            const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
            const jsonPayload = decodeURIComponent(
                atob(base64)
                    .split('')
                    .map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
                    .join('')
            );
            return JSON.parse(jsonPayload);
        } catch (error) {
            console.error('解析 JWT 失败:', error);
            return null;
        }
    }
}

// 创建单例实例
const authService = new AuthService();

// 设置定期令牌刷新（每分钟检查一次）
setInterval(() => {
    if (authService.isAuthenticatedUser()) {
        authService.checkAndRefreshToken();
    }
}, 60000);

export default authService;
