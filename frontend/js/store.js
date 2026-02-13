// Simple state management store (similar to Vuex/Pinia)

export const createStore = (options) => {
    const state = reactive(options.state || {});
    const getters = options.getters || {};
    const mutations = options.mutations || {};
    const actions = options.actions || {};

    const computedGetters = {};
    Object.keys(getters).forEach(key => {
        computedGetters[key] = computed(() => getters[key](state));
    });

    const commit = (mutationName, payload) => {
        if (mutations[mutationName]) {
            mutations[mutationName](state, payload);
        } else {
            console.warn(`Mutation ${mutationName} not found`);
        }
    };

    const dispatch = (actionName, payload) => {
        if (actions[actionName]) {
            return actions[actionName]({ state, commit, dispatch }, payload);
        } else {
            console.warn(`Action ${actionName} not found`);
            return Promise.reject(new Error(`Action ${actionName} not found`));
        }
    };

    return {
        state,
        getters: computedGetters,
        commit,
        dispatch
    };
};

// Main application store
export const useAppStore = () => {
    return createStore({
        state: {
            currentUser: null,
            isAuthenticated: false,
            theme: 'dark',
            language: 'zh-CN',
            notifications: []
        },

        getters: {
            userName: (state) => state.currentUser?.username || '',
            userId: (state) => state.currentUser?.id || null,
            unreadNotifications: (state) => state.notifications.filter(n => !n.read).length
        },

        mutations: {
            SET_USER(state, user) {
                state.currentUser = user;
                state.isAuthenticated = !!user;
                if (user) {
                    localStorage.setItem('agoraUser', JSON.stringify(user));
                } else {
                    localStorage.removeItem('agoraUser');
                }
            },
            CLEAR_USER(state) {
                state.currentUser = null;
                state.isAuthenticated = false;
                localStorage.removeItem('agoraUser');
            },
            SET_THEME(state, theme) {
                state.theme = theme;
                document.documentElement.setAttribute('data-theme', theme);
            },
            SET_LANGUAGE(state, language) {
                state.language = language;
            },
            ADD_NOTIFICATION(state, notification) {
                state.notifications.unshift({
                    id: Date.now(),
                    read: false,
                    ...notification
                });
            },
            MARK_NOTIFICATION_READ(state, id) {
                const notification = state.notifications.find(n => n.id === id);
                if (notification) notification.read = true;
            },
            CLEAR_NOTIFICATIONS(state) {
                state.notifications = [];
            }
        },

        actions: {
            async login({ commit }, { username, password }) {
                // In production, this would call an API
                return new Promise((resolve, reject) => {
                    setTimeout(() => {
                        if (username && password) {
                            commit('SET_USER', {
                                id: Date.now(),
                                username,
                                email: `${username}@example.com`
                            });
                            resolve();
                        } else {
                            reject(new Error('Invalid credentials'));
                        }
                    }, 1000);
                });
            },
            async register({ commit }, { username, password, email }) {
                return new Promise((resolve, reject) => {
                    setTimeout(() => {
                        if (username && password && email) {
                            commit('SET_USER', {
                                id: Date.now(),
                                username,
                                email
                            });
                            resolve();
                        } else {
                            reject(new Error('Invalid registration data'));
                        }
                    }, 1000);
                });
            },
            async logout({ commit }) {
                commit('CLEAR_USER');
            },
            loadSavedUser({ commit }) {
                try {
                    const savedUser = localStorage.getItem('agoraUser');
                    if (savedUser) {
                        commit('SET_USER', JSON.parse(savedUser));
                    }
                } catch (error) {
                    console.error('Error loading saved user:', error);
                }
            }
        }
    });
};

// Create singleton store instance
let appStore = null;

export const getAppStore = () => {
    if (!appStore) {
        appStore = useAppStore();
    }
    return appStore;
};
