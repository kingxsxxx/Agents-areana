// Debate display module - handles WebSocket connection and speech display

export function useDebateDisplay(debateId) {
    const speeches = ref([]);
    const currentPhase = ref('');
    const currentStep = ref(0);
    const isPaused = ref(false);
    const ws = ref(null);
    const isConnected = ref(false);

    const connectWebSocket = (token) => {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/debates/${debateId}?token=${token}`;

        try {
            ws.value = new WebSocket(wsUrl);

            ws.value.onopen = () => {
                console.log('WebSocket connected');
                isConnected.value = true;
            };

            ws.value.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);

                    switch(data.type) {
                        case 'speech':
                            speeches.value.push({
                                id: Date.now(),
                                phase: data.phase,
                                speakerId: data.agent_id,
                                side: data.side,
                                speakerName: data.speaker_name,
                                position: data.position,
                                content: data.content,
                                time: new Date(),
                                timestamp: new Date().toLocaleTimeString()
                            });
                            break;
                        case 'status':
                            currentPhase.value = data.current_phase;
                            currentStep.value = data.current_step;
                            isPaused.value = data.paused || false;
                            break;
                        case 'score':
                            // Score updates handled by parent component
                            break;
                        case 'phase_change':
                            currentPhase.value = data.phase;
                            currentStep.value = data.step_index;
                            break;
                        case 'speaker_change':
                            // Speaker change notification
                            break;
                        case 'finish':
                            // Debate finished
                            break;
                    }
                } catch (error) {
                    console.error('Error parsing WebSocket message:', error);
                }
            };

            ws.value.onerror = (error) => {
                console.error('WebSocket error:', error);
                isConnected.value = false;
            };

            ws.value.onclose = () => {
                console.log('WebSocket closed');
                isConnected.value = false;
            };
        } catch (error) {
            console.error('Failed to create WebSocket connection:', error);
        }
    };

    const disconnect = () => {
        if (ws.value) {
            ws.value.close();
            ws.value = null;
            isConnected.value = false;
        }
    };

    const sendCommand = (command, data = {}) => {
        if (ws.value && ws.value.readyState === WebSocket.OPEN) {
            ws.value.send(JSON.stringify({ command, ...data }));
        }
    };

    const pauseDebate = () => {
        sendCommand('pause');
    };

    const resumeDebate = () => {
        sendCommand('resume');
    };

    const stopDebate = () => {
        sendCommand('stop');
    };

    return {
        speeches,
        currentPhase,
        currentStep,
        isPaused,
        isConnected,
        connectWebSocket,
        disconnect,
        pauseDebate,
        resumeDebate,
        stopDebate
    };
}

// Hook for local debate display (without WebSocket)
export function useLocalDebateDisplay(engine) {
    const speeches = ref([]);
    const currentPhase = ref('');
    const currentStep = ref(0);
    const isPaused = ref(false);
    const currentSpeaker = ref('');

    onMounted(() => {
        if (engine) {
            // Listen to engine events
            engine.on('speech', (speech) => {
                speeches.value.push({
                    ...speech,
                    time: new Date()
                });
            });

            engine.on('phase-change', (data) => {
                currentPhase.value = data.phase;
                currentStep.value = data.stepIndex;
            });

            engine.on('speaker-change', (data) => {
                currentSpeaker.value = data.speaker;
            });

            engine.on('pause', () => {
                isPaused.value = true;
            });

            engine.on('resume', () => {
                isPaused.value = false;
            });

            engine.on('stop', () => {
                isPaused.value = false;
            });
        }
    });

    return {
        speeches,
        currentPhase,
        currentStep,
        isPaused,
        currentSpeaker
    };
}

// Helper function to format speech content for display
export function formatSpeechContent(content, maxLength = 300) {
    if (content.length <= maxLength) return content;
    return content.substring(0, maxLength) + '...';
}

// Helper function to get speaker display name
export function getSpeakerDisplayName(speech, agents) {
    if (speech.side === 'neutral') {
        return speech.speakerName || speech.speaker;
    }
    const agent = getAgentById(speech.id, agents);
    return agent ? agent.name : speech.speakerName || speech.speaker;
}

// Helper function to get agent by ID
export function getAgentById(id, agents) {
    if (id === 'host') return agents?.host;
    if (id.startsWith('pro')) return agents?.pro[id];
    if (id.startsWith('con')) return agents?.con[id];
    return null;
}

// Helper function to get side badge color
export function getSideBadgeColor(side) {
    switch(side) {
        case 'pro': return 'bg-cyan-600';
        case 'con': return 'bg-pink-600';
        default: return 'bg-purple-600';
    }
}

// Helper function to get side display name
export function getSideDisplayName(side) {
    switch(side) {
        case 'pro': return '正方';
        case 'con': return '反方';
        default: return '';
    }
}
