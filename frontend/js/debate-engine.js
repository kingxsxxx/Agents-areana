// Debate engine module - handles debate flow and simulation

export class DebateEngine {
    constructor(agents, config) {
        this.agents = agents;
        this.config = config;
        this.state = {
            status: 'idle', // idle, running, paused, finished
            currentStepIndex: 0,
            currentPhase: '',
            currentSpeaker: '',
            speechHistory: [],
            judgeScores: {}
        };
        this.callbacks = {};
    }

    // Event handling
    on(event, callback) {
        if (!this.callbacks[event]) {
            this.callbacks[event] = [];
        }
        this.callbacks[event].push(callback);
    }

    emit(event, data) {
        if (this.callbacks[event]) {
            this.callbacks[event].forEach(cb => cb(data));
        }
    }

    // Start the debate
    start(topic) {
        if (this.state.status !== 'idle') return;

        this.state.status = 'running';
        this.state.currentStepIndex = 0;
        this.state.speechHistory = [];
        this.state.currentPhase = '';
        this.state.currentSpeaker = '';

        // Host opening speech
        const host = this.agents.host;
        this.addSpeech('host', host.name, '主持人', `欢迎各位来到今天的辩论赛。本次辩论的主题是："${topic}"。让我们有请正方一辩开始陈词。`, 'neutral');

        this.emit('start', { topic });
        this.executeNextStep();
    }

    // Execute next debate step
    executeNextStep() {
        if (this.state.currentStepIndex >= this.config.debateSteps.length) {
            this.finishDebate();
            return;
        }

        const step = this.config.debateSteps[this.state.currentStepIndex];
        this.state.currentPhase = step.phase;
        this.emit('phase-change', { phase: step.phase, stepIndex: this.state.currentStepIndex });

        if (step.speaker === 'judges') {
            this.simulateJudging();
        } else if (step.speaker === 'free') {
            this.simulateFreeDebate();
        } else {
            this.simulateAgentSpeech(step);
        }
    }

    // Simulate agent speech
    async simulateAgentSpeech(step) {
        const agent = this.getAgentById(step.speaker);
        if (!agent) {
            this.advanceToNextStep();
            return;
        }

        this.state.currentSpeaker = agent.name;
        this.emit('speaker-change', { speaker: agent.name, side: step.side });

        // Simulate AI response delay
        await this.simulateDelay(2000);

        const content = `这是${agent.name}的发言内容。（使用${agent.aiModel}生成，时长约${step.duration}秒）`;
        this.addSpeech(step.speaker, agent.name, agent.position, content, step.side);

        this.state.currentSpeaker = '';
        this.advanceToNextStep();
    }

    // Simulate free debate
    async simulateFreeDebate() {
        const rounds = 6;
        const { pro, con } = this.agents;

        for (let i = 0; i < rounds; i++) {
            if (this.state.status !== 'running') break;

            // Pro speaker
            const proAgent = pro[`pro-${(i % 4) + 1}`];
            this.state.currentSpeaker = proAgent.name;
            this.emit('speaker-change', { speaker: proAgent.name, side: 'pro' });
            await this.simulateDelay(1500);
            this.addSpeech(`pro-${(i % 4) + 1}`, proAgent.name, proAgent.position, `自由辩论发言 ${i + 1} - 正方`, 'pro');
            this.state.currentSpeaker = '';

            if (this.state.status !== 'running') break;
            await this.simulateDelay(500);

            // Con speaker
            const conAgent = con[`con-${(i % 4) + 1}`];
            this.state.currentSpeaker = conAgent.name;
            this.emit('speaker-change', { speaker: conAgent.name, side: 'con' });
            await this.simulateDelay(1500);
            this.addSpeech(`con-${(i % 4) + 1}`, conAgent.name, conAgent.position, `自由辩论发言 ${i + 1} - 反方`, 'con');
            this.state.currentSpeaker = '';

            if (this.state.status !== 'running') break;
            await this.simulateDelay(500);
        }

        this.advanceToNextStep();
    }

    // Simulate judging
    async simulateJudging() {
        await this.simulateDelay(2000);

        // Generate random scores
        Object.keys(this.state.judgeScores).forEach(judgeId => {
            this.state.judgeScores[judgeId].pro = Math.floor(Math.random() * 30) + 70;
            this.state.judgeScores[judgeId].con = Math.floor(Math.random() * 30) + 70;
        });

        this.addSpeech('judges', '评审团', '评委', '所有评委已完成打分', 'neutral');
        this.emit('scores-update', this.state.judgeScores);

        this.advanceToNextStep();
    }

    // Advance to next step
    advanceToNextStep() {
        this.state.currentStepIndex++;

        if (this.state.status === 'running') {
            this.simulateDelay(1000).then(() => {
                if (this.state.status === 'running') {
                    this.executeNextStep();
                }
            });
        }
    }

    // Finish debate
    finishDebate() {
        this.state.status = 'finished';

        const totalScores = this.calculateTotalScores();
        const winner = totalScores.pro > totalScores.con ? '正方' : '反方';

        const host = this.agents.host;
        this.addSpeech('host', host.name, '主持人', `本场辩论结束！经过评委打分，${winner}获胜！`, 'neutral');

        this.emit('finish', { winner, scores: totalScores });
    }

    // Pause debate
    pause() {
        if (this.state.status === 'running') {
            this.state.status = 'paused';
            this.emit('pause');
        }
    }

    // Resume debate
    resume() {
        if (this.state.status === 'paused') {
            this.state.status = 'running';
            this.emit('resume');
            this.executeNextStep();
        }
    }

    // Stop debate
    stop() {
        this.state.status = 'finished';
        this.emit('stop');
    }

    // Add speech to history
    addSpeech(id, speaker, role, content, side) {
        const speech = {
            id,
            speaker,
            role,
            content,
            side,
            timestamp: new Date().toLocaleTimeString()
        };
        this.state.speechHistory.push(speech);
        this.emit('speech', speech);
    }

    // Get agent by ID
    getAgentById(id) {
        if (id === 'host') return this.agents.host;
        if (id.startsWith('pro')) return this.agents.pro[id];
        if (id.startsWith('con')) return this.agents.con[id];
        return null;
    }

    // Calculate total scores
    calculateTotalScores() {
        const scores = this.state.judgeScores;
        return {
            pro: Object.values(scores).reduce((sum, s) => sum + (s.pro || 0), 0),
            con: Object.values(scores).reduce((sum, s) => sum + (s.con || 0), 0)
        };
    }

    // Simulate delay
    simulateDelay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    // Reset engine
    reset() {
        this.state = {
            status: 'idle',
            currentStepIndex: 0,
            currentPhase: '',
            currentSpeaker: '',
            speechHistory: [],
            judgeScores: {}
        };
    }
}

// Factory function to create debate engine
export const createDebateEngine = (agents, config) => new DebateEngine(agents, config);
