// Debate arena configuration module
export const ARENA_CONFIG = {
    // Supported AI models
    aiModels: [
        'DeepSeek',
        'Qwen (通义千问)',
        'Kimi',
        'GPT-4',
        'GPT-3.5',
        'Doubao (豆包)',
        'Gemini Pro',
        'Gemini Ultra',
        'GLM-4',
        'GLM-3'
    ],

    // Job occupations for debaters
    jobs: [
        '大学教授', '资深律师', '技术分析师', '艺术家', '政府官员',
        '在校学生', '自由职业者', '退休医生', '金融投资人', '社会评论家',
        '企业家', '工程师', '记者', '教师', '研究员'
    ],

    // MBTI personality types
    mbtiTypes: [
        'INTJ', 'INTP', 'ENTJ', 'ENTP',
        'INFJ', 'INFP', 'ENFJ', 'ENFP',
        'ISTJ', 'ISFJ', 'ESTJ', 'ESFJ',
        'ISTP', 'ISFP', 'ESTP', 'ESFP'
    ],

    // Personality parameter labels
    paramLabels: {
        aggression: '攻击性',
        logic: '逻辑性',
        rhetoric: '修辞能力',
        emotional: '情感诉求'
    },

    // Debate flow steps
    debateSteps: [
        { phase: '开篇立论', speaker: 'pro-1', duration: 180, side: 'pro' },
        { phase: '开篇立论', speaker: 'con-1', duration: 180, side: 'con' },
        { phase: '攻辩环节', speaker: 'pro-2', duration: 120, side: 'pro', target: 'con' },
        { phase: '攻辩环节', speaker: 'con-2', duration: 120, side: 'con', target: 'pro' },
        { phase: '攻辩环节', speaker: 'pro-3', duration: 120, side: 'pro', target: 'con' },
        { phase: '攻辩环节', speaker: 'con-3', duration: 120, side: 'con', target: 'pro' },
        { phase: '攻辩小结', speaker: 'pro-1', duration: 120, side: 'pro' },
        { phase: '攻辩小结', speaker: 'con-1', duration: 120, side: 'con' },
        { phase: '自由辩论', speaker: 'free', duration: 300, side: 'both' },
        { phase: '总结陈词', speaker: 'con-4', duration: 240, side: 'con' },
        { phase: '总结陈词', speaker: 'pro-4', duration: 240, side: 'pro' },
        { phase: '评委打分', speaker: 'judges', duration: 0, side: 'neutral' }
    ],

    // Income levels for debaters
    incomeLevels: [
        '低收入',
        '中等收入',
        '中高收入',
        '高收入'
    ],

    // Income descriptions
    incomeDescriptions: {
        '低收入': '(< 5万/年)',
        '中等收入': '(5-20万/年)',
        '中高收入': '(20-50万/年)',
        '高收入': '(> 50万/年)'
    }
};

// Agent factory functions
export const createDebater = (position, name, side) => ({
    position,
    name,
    side,
    aiModel: '',
    gender: 'Male',
    age: 30,
    job: '大学教授',
    income: '中等收入',
    mbti: 'INTJ',
    params: {
        aggression: 50,
        logic: 50,
        rhetoric: 50,
        emotional: 50
    },
    initialized: false
});

export const createJudge = (position, name) => ({
    position,
    name,
    aiModel: '',
    gender: 'Male',
    age: 45,
    job: '资深评委',
    initialized: false
});

// Initial agents state
export const createInitialAgents = () => ({
    host: {
        name: 'HOST',
        aiModel: '',
        gender: 'Male',
        age: 35,
        job: '专业主持人',
        mbti: 'ENTJ',
        initialized: false
    },
    pro: {
        'pro-1': createDebater('一辩', 'PRO-1', 'pro'),
        'pro-2': createDebater('二辩', 'PRO-2', 'pro'),
        'pro-3': createDebater('三辩', 'PRO-3', 'pro'),
        'pro-4': createDebater('四辩', 'PRO-4', 'pro')
    },
    con: {
        'con-1': createDebater('一辩', 'CON-1', 'con'),
        'con-2': createDebater('二辩', 'CON-2', 'con'),
        'con-3': createDebater('三辩', 'CON-3', 'con'),
        'con-4': createDebater('四辩', 'CON-4', 'con')
    },
    judges: {
        'judge-1': createJudge('1', 'JUDGE-1'),
        'judge-2': createJudge('2', 'JUDGE-2'),
        'judge-3': createJudge('3', 'JUDGE-3'),
        'judge-4': createJudge('4', 'JUDGE-4'),
        'judge-5': createJudge('5', 'JUDGE-5')
    }
});

// Initial judge scores state
export const createInitialJudgeScores = () => ({
    'judge-1': { pro: 0, con: 0 },
    'judge-2': { pro: 0, con: 0 },
    'judge-3': { pro: 0, con: 0 },
    'judge-4': { pro: 0, con: 0 },
    'judge-5': { pro: 0, con: 0 }
});

// Arena configuration composable for Vue
export function useArenaConfig() {
    const config = reactive({
        title: '',
        // Host configuration
        host: {
            name: '主持人',
            aiModel: 'DeepSeek',
            gender: '男',
            age: 45,
            job: '主持人',
            income: '中等收入',
            mbti: 'INTJ'
        },
        // Pro debaters configuration (4 speakers)
        proAgents: Array.from({ length: 4 }, (_, i) => ({
            id: `pro-${i + 1}`,
            name: '',
            aiModel: 'DeepSeek',
            gender: '',
            age: 30,
            job: '律师',
            income: '',
            mbti: '',
            side: 'pro',
            position: `正方${i + 1}辩`,
            params: {
                aggression: 50,
                logic: 50,
                rhetoric: 50,
                emotional: 50
            }
        })),
        // Con debaters configuration (4 speakers)
        conAgents: Array.from({ length: 4 }, (_, i) => ({
            id: `con-${i + 1}`,
            name: '',
            aiModel: 'DeepSeek',
            gender: '',
            age: 30,
            job: '律师',
            income: '',
            mbti: '',
            side: 'con',
            position: `反方${i + 1}辩`,
            params: {
                aggression: 50,
                logic: 50,
                rhetoric: 50,
                emotional: 50
            }
        })),
        // Judges configuration (4 judges as specified)
        judges: Array.from({ length: 4 }, (_, i) => ({
            id: `judge-${i + 1}`,
            name: `评委${i + 1}`,
            aiModel: 'GPT-4',
            role: 'judge',
            position: `评委${i + 1}`
        }))
    });

    const validateConfig = () => {
        return config.title.trim() !== '' &&
               config.host.aiModel &&
               config.proAgents.every(a => a.name && a.aiModel) &&
               config.conAgents.every(a => a.name && a.aiModel) &&
               config.judges.every(j => j.name && j.aiModel);
    };

    const resetConfig = () => {
        config.title = '';
        config.host = {
            name: '主持人',
            aiModel: 'DeepSeek',
            gender: '男',
            age: 45,
            job: '主持人',
            income: '中等收入',
            mbti: 'INTJ'
        };
        config.proAgents.forEach((agent, i) => {
            agent.name = '';
            agent.aiModel = 'DeepSeek';
            agent.gender = '';
            agent.age = 30;
            agent.job = '律师';
            agent.income = '';
            agent.mbti = '';
            agent.params = { aggression: 50, logic: 50, rhetoric: 50, emotional: 50 };
        });
        config.conAgents.forEach((agent, i) => {
            agent.name = '';
            agent.aiModel = 'DeepSeek';
            agent.gender = '';
            agent.age = 30;
            agent.job = '律师';
            agent.income = '';
            agent.mbti = '';
            agent.params = { aggression: 50, logic: 50, rhetoric: 50, emotional: 50 };
        });
    };

    const getDebateStepIndex = (phase) => {
        return ARENA_CONFIG.debateSteps.findIndex(step => step.phase === phase);
    };

    const getDebateStepByIndex = (index) => {
        return ARENA_CONFIG.debateSteps[index];
    };

    return {
        config,
        validateConfig,
        resetConfig,
        getDebateStepIndex,
        getDebateStepByIndex
    };
}
