// 用户管理模块 - 基于真实 API 的用户认证和管理
import { ref, reactive, onMounted } from 'https://unpkg.com/vue@3/dist/vue.esm-browser.js';
import apiClient, { getErrorMessage } from './api.js';

/**
 * 用户管理组合式函数
 * 提供完整的用户认证、登录、注册、登出功能
 */
export function useUserManager() {
    // ===== 响应式状态 =====
    const currentUser = ref(null);
    const isAuthenticated = ref(false);
    const token = ref(localStorage.getItem('agoraToken') || null);
    const showAuthModal = ref(false);
    const authError = ref('');
    const isLoading = ref(false);

    // 认证表单
    const authForm = reactive({
        username: '',
        password: '',
        email: ''
    });

    // 认证模式：login 或 register
    const authMode = ref('login');

    // 用户菜单显示状态
    const showUserMenu = ref(false);

    // ===== API 方法 =====
    const api = {
        /**
         * 用户登录
         * @param {string} username 用户名
         * @param {string} password 密码
         * @returns {Promise<void>}
         */
        async login(username, password) {
            isLoading.value = true;
            authError.value = '';

            try {
                const data = await apiClient.login(username, password);

                // 更新状态
                currentUser.value = data;
                token.value = data.access_token;
                isAuthenticated.value = true;

                // 存储到本地
                localStorage.setItem('agoraToken', token.value);
                localStorage.setItem('agoraUser', JSON.stringify(data));

                // 关闭模态框
                showAuthModal.value = false;
                authError.value = '';

                // 清空表单
                authForm.username = '';
                authForm.password = '';

                return data;
            } catch (error) {
                const errorMessage = getErrorMessage(error);
                authError.value = errorMessage || '登录失败，请检查用户名和密码';
                throw error;
            } finally {
                isLoading.value = false;
            }
        },

        /**
         * 用户注册
         * @param {string} username 用户名
         * @param {string} email 邮箱
         * @param {string} password 密码
         * @returns {Promise<void>}
         */
        async register(username, email, password) {
            isLoading.value = true;
            authError.value = '';

            try {
                const data = await apiClient.register(username, email, password);

                // 注册成功后自动登录
                currentUser.value = data;
                token.value = data.access_token;
                isAuthenticated.value = true;

                // 存储到本地
                localStorage.setItem('agoraToken', token.value);
                localStorage.setItem('agoraUser', JSON.stringify(data));

                // 关闭模态框
                showAuthModal.value = false;
                authError.value = '';

                // 清空表单
                authForm.username = '';
                authForm.email = '';
                authForm.password = '';

                // 切换回登录模式
                authMode.value = 'login';

                return data;
            } catch (error) {
                const errorMessage = getErrorMessage(error);
                authError.value = errorMessage || '注册失败，请重试';
                throw error;
            } finally {
                isLoading.value = false;
            }
        },

        /**
         * 用户登出
         */
        logout() {
            // 调用后端登出 API（可选）
            apiClient.logout().catch(error => {
                console.error('Logout API call failed:', error);
            });

            // 清除本地存储
            localStorage.removeItem('agoraToken');
            localStorage.removeItem('agoraUser');

            // 重置状态
            currentUser.value = null;
            token.value = null;
            isAuthenticated.value = false;
            showAuthModal.value = false;
            showUserMenu.value = false;
            authError.value = '';
        },

        /**
         * 检查认证状态
         * 从本地存储恢复用户信息，并验证 token 有效性
         * @returns {Promise<void>}
         */
        async checkAuth() {
            const savedToken = localStorage.getItem('agoraToken');
            const savedUser = localStorage.getItem('agoraUser');

            if (savedToken && savedUser) {
                try {
                    // 尝试获取当前用户信息以验证 token 有效性
                    const data = await apiClient.getCurrentUser();

                    // 更新用户信息（可能后端有新的用户数据）
                    currentUser.value = data;
                    token.value = savedToken;
                    isAuthenticated.value = true;
                } catch (error) {
                    // Token 可能已过期，清除本地数据
                    console.warn('Token validation failed:', error);
                    this.logout();
                }
            }
        },

        /**
         * 刷新认证令牌
         * @returns {Promise<boolean>}
         */
        async refreshAccessToken() {
            try {
                const data = await apiClient.refreshAccessToken();

                if (data.access_token) {
                    token.value = data.access_token;
                    localStorage.setItem('agoraToken', data.access_token);

                    // 同时更新 localStorage 中的用户数据
                    const savedUser = JSON.parse(localStorage.getItem('agoraUser') || '{}');
                    localStorage.setItem('agoraUser', JSON.stringify({
                        ...savedUser,
                        ...data
                    }));

                    return true;
                }

                return false;
            } catch (error) {
                console.error('Token refresh failed:', error);
                // 刷新失败，执行登出
                this.logout();
                return false;
            }
        },

        /**
         * 更新用户信息
         * @param {object} updates 更新的用户数据
         */
        updateUser(updates) {
            if (currentUser.value) {
                currentUser.value = {
                    ...currentUser.value,
                    ...updates
                };
                localStorage.setItem('agoraUser', JSON.stringify(currentUser.value));
            }
        },

        /**
         * 切换认证模式
         * @param {string} mode 'login' 或 'register'
         */
        toggleAuthMode(mode) {
            authMode.value = mode || (authMode.value === 'login' ? 'register' : 'login');
            authError.value = '';
        }
    };

    // ===== 便捷方法 =====

    /**
     * 处理认证表单提交
     * 根据当前模式自动选择登录或注册
     * @returns {Promise<void>}
     */
    const handleAuthSubmit = async () => {
        // 基本验证
        if (!authForm.username || !authForm.password) {
            authError.value = '请填写用户名和密码';
            return;
        }

        if (authMode.value === 'register' && !authForm.email) {
            authError.value = '请填写邮箱地址';
            return;
        }

        try {
            if (authMode.value === 'login') {
                await api.login(authForm.username, authForm.password);
            } else {
                await api.register(authForm.username, authForm.email, authForm.password);
            }
        } catch (error) {
            // 错误已在 login/register 方法中处理
        }
    };

    /**
     * 显示登录模态框
     */
    const showLogin = () => {
        authMode.value = 'login';
        showAuthModal.value = true;
        authError.value = '';
    };

    /**
     * 显示注册模态框
     */
    const showRegister = () => {
        authMode.value = 'register';
        showAuthModal.value = true;
        authError.value = '';
    };

    /**
     * 关闭认证模态框
     */
    const hideAuthModal = () => {
        showAuthModal.value = false;
        authError.value = '';
    };

    /**
     * 切换用户菜单
     */
    const toggleUserMenu = () => {
        showUserMenu.value = !showUserMenu.value;
    };

    /**
     * 关闭用户菜单
     */
    const closeUserMenu = () => {
        showUserMenu.value = false;
    };

    // ===== 生命周期 =====

    // 组件挂载时检查认证状态
    onMounted(() => {
        api.checkAuth().catch(error => {
            console.error('Initial auth check failed:', error);
        });
    });

    // ===== 返回公开接口 =====
    return {
        // 状态
        currentUser,
        isAuthenticated,
        token,
        showAuthModal,
        authError,
        isLoading,
        authForm,
        authMode,
        showUserMenu,

        // API 方法
        api,

        // 便捷方法
        handleAuthSubmit,
        showLogin,
        showRegister,
        hideAuthModal,
        toggleUserMenu,
        closeUserMenu
    };
}

/**
 * 全局用户管理器实例
 * 可在应用的任何地方使用
 */
let globalUserManager = null;

export const getGlobalUserManager = () => {
    if (!globalUserManager) {
        globalUserManager = useUserManager();
    }
    return globalUserManager;
};

export default useUserManager;
