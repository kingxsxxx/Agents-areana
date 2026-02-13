// 辩论服务 - 统一的辩论管理
import apiClient from './api.js';

/**
 * 辩论服务
 * 提供辩论、角色、发言记录等管理功能
 */
class DebateService {
    /**
     * 获取辩论列表
     * @returns {Promise<Array>}
     */
    async getDebates() {
        try {
            const result = await apiClient.getDebates();
            return Array.isArray(result) ? result : [];
        } catch (error) {
            console.error('获取辩论列表失败:', error);
            throw error;
        }
    }

    /**
     * 获取辩论详情
     * @param {number} debateId 辩论 ID
     * @returns {Promise<object>}
     */
    async getDebate(debateId) {
        try {
            return await apiClient.getDebate(debateId);
        } catch (error) {
            console.error('获取辩论详情失败:', error);
            throw error;
        }
    }

    /**
     * 创建辩论
     * @param {string} title 辩论标题
     * @returns {Promise<object>}
     */
    async createDebate(title) {
        try {
            return await apiClient.createDebate(title);
        } catch (error) {
            console.error('创建辩论失败:', error);
            throw error;
        }
    }

    /**
     * 更新辩论
     * @param {number} debateId 辩论 ID
     * @param {object} updateData 更新数据
     * @returns {Promise<object>}
     */
    async updateDebate(debateId, updateData) {
        try {
            return await apiClient.updateDebate(debateId, updateData);
        } catch (error) {
            console.error('更新辩论失败:', error);
            throw error;
        }
    }

    /**
     * 删除辩论
     * @param {number} debateId 辩论 ID
     * @returns {Promise<object>}
     */
    async deleteDebate(debateId) {
        try {
            return await apiClient.deleteDebate(debateId);
        } catch (error) {
            console.error('删除辩论失败:', error);
            throw error;
        }
    }

    /**
     * 启动辩论
     * @param {number} debateId 辩论 ID
     * @returns {Promise<object>}
     */
    async startDebate(debateId) {
        try {
            return await apiClient.startDebate(debateId);
        } catch (error) {
            console.error('启动辩论失败:', error);
            throw error;
        }
    }

    /**
     * 暂停辩论
     * @param {number} debateId 辩论 ID
     * @returns {Promise<object>}
     */
    async pauseDebate(debateId) {
        try {
            return await apiClient.pauseDebate(debateId);
        } catch (error) {
            console.error('暂停辩论失败:', error);
            throw error;
        }
    }

    /**
     * 恢复辩论
     * @param {number} debateId 辩论 ID
     * @returns {Promise<object>}
     */
    async resumeDebate(debateId) {
        try {
            return await apiClient.resumeDebate(debateId);
        } catch (error) {
            console.error('恢复辩论失败:', error);
            throw error;
        }
    }

    /**
     * 终止辩论
     * @param {number} debateId 辩论 ID
     * @returns {Promise<object>}
     */
    async stopDebate(debateId) {
        try {
            return await apiClient.stopDebate(debateId);
        } catch (error) {
            console.error('终止辩论失败:', error);
            throw error;
        }
    }

    // ===== 角色管理 =====

    /**
     * 创建 AI 角色
     * @param {number} debateId 辩论 ID
     * @param {object} agentConfig 角色配置
     * @returns {Promise<object>}
     */
    async createAgent(debateId, agentConfig) {
        try {
            return await apiClient.createAgent(debateId, agentConfig);
        } catch (error) {
            console.error('创建角色失败:', error);
            throw error;
        }
    }

    /**
     * 批量创建角色
     * @param {number} debateId 辩论 ID
     * @param {Array} agentConfigs 角色配置数组
     * @returns {Promise<Array>}
     */
    async createAgents(debateId, agentConfigs) {
        try {
            const promises = agentConfigs.map(config =>
                this.createAgent(debateId, config)
            );
            return await Promise.all(promises);
        } catch (error) {
            console.error('批量创建角色失败:', error);
            throw error;
        }
    }

    /**
     * 更新 AI 角色
     * @param {number} debateId 辩论 ID
     * @param {number} agentId 角色 ID
     * @param {object} updateData 更新数据
     * @returns {Promise<object>}
     */
    async updateAgent(debateId, agentId, updateData) {
        try {
            return await apiClient.updateAgent(debateId, agentId, updateData);
        } catch (error) {
            console.error('更新角色失败:', error);
            throw error;
        }
    }

    /**
     * 删除 AI 角色
     * @param {number} debateId 辩论 ID
     * @param {number} agentId 角色 ID
     * @returns {Promise<object>}
     */
    async deleteAgent(debateId, agentId) {
        try {
            return await apiClient.deleteAgent(debateId, agentId);
        } catch (error) {
            console.error('删除角色失败:', error);
            throw error;
        }
    }

    // ===== 发言记录 =====

    /**
     * 获取辩论发言记录
     * @param {number} debateId 辩论 ID
     * @returns {Promise<Array>}
     */
    async getSpeeches(debateId) {
        try {
            const result = await apiClient.getSpeeches(debateId);
            return Array.isArray(result) ? result : [];
        } catch (error) {
            console.error('获取发言记录失败:', error);
            throw error;
        }
    }

    // ===== 评分记录 =====

    /**
     * 获取辩论评分
     * @param {number} debateId 辩论 ID
     * @returns {Promise<Array>}
     */
    async getScores(debateId) {
        try {
            const result = await apiClient.getScores(debateId);
            return Array.isArray(result) ? result : [];
        } catch (error) {
            console.error('获取评分失败:', error);
            throw error;
        }
    }

    // ===== WebSocket 连接 =====

    /**
     * 创建 WebSocket 连接
     * @param {number} debateId 辩论 ID
     * @param {object} eventHandlers 事件处理器
     * @returns {WebSocket}
     */
    connectWebSocket(debateId, eventHandlers = {}) {
        return apiClient.connectWebSocket(debateId, eventHandlers);
    }

    // ===== 辅助方法 =====

    /**
     * 格式化辩论状态
     * @param {string} status 状态值
     * @returns {string} 中文状态
     */
    formatDebateStatus(status) {
        const statusMap = {
            'draft': '草稿',
            'running': '进行中',
            'paused': '已暂停',
            'finished': '已结束'
        };
        return statusMap[status] || status;
    }

    /**
     * 格式化辩论阶段
     * @param {string} phase 阶段值
     * @returns {string} 中文阶段
     */
    formatDebatePhase(phase) {
        const phaseMap = {
            '开篇立论': '开篇立论',
            '攻辩环节': '攻辩环节',
            '攻辩小结': '攻辩小结',
            '自由辩论': '自由辩论',
            '总结陈词': '总结陈词',
            '评委打分': '评委打分'
        };
        return phaseMap[phase] || phase;
    }

    /**
     * 格式化日期时间
     * @param {string} dateTime ISO 日期时间字符串
     * @returns {string} 格式化的日期时间
     */
    formatDateTime(dateTime) {
        if (!dateTime) return '-';
        try {
            const date = new Date(dateTime);
            const now = new Date();
            const diff = now - date;

            if (diff < 60000) {
                return '刚刚';
            } else if (diff < 3600000) {
                return `${Math.floor(diff / 60000)} 分钟前`;
            } else if (diff < 86400000) {
                return `${Math.floor(diff / 3600000)} 小时前`;
            } else {
                return date.toLocaleDateString('zh-CN', {
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit'
                });
            }
        } catch (error) {
            return dateTime;
        }
    }
}

// 创建单例实例
const debateService = new DebateService();

export default debateService;
