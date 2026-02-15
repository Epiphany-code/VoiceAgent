/**
 * 配置管理页面逻辑
 */
class ConfigManager {
    constructor() {
        this.config = null;
        this.pendingUpdates = {};
        this.init();
    }

    async init() {
        this.initTheme();
        await this.loadConfig();
        this.bindEvents();
    }

    /**
     * 初始化主题
     */
    initTheme() {
        const savedTheme = localStorage.getItem('config-theme') || 'light';
        document.documentElement.setAttribute('data-theme', savedTheme);
        this.updateThemeIcon(savedTheme);
    }

    /**
     * 切换主题
     */
    toggleTheme() {
        const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
        const newTheme = currentTheme === 'light' ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('config-theme', newTheme);
        this.updateThemeIcon(newTheme);
    }

    updateThemeIcon(theme) {
        const btn = document.querySelector('.theme-toggle');
        if (btn) {
            btn.textContent = theme === 'light' ? '☀️' : '🌙';
        }
    }

    /**
     * 加载配置
     */
    async loadConfig() {
        try {
            const response = await fetch('/api/config/');
            const result = await response.json();
            if (result.success) {
                this.config = result.data;
                this.renderConfig();
            } else {
                this.showToast('加载配置失败', 'error');
            }
        } catch (error) {
            console.error('加载配置失败:', error);
            this.showToast('加载配置失败', 'error');
        }
    }

    /**
     * 渲染配置
     */
    renderConfig() {
        if (!this.config) return;

        // 渲染提供商配置
        this.renderProviderConfig();

        // 渲染 Agent 配置
        this.renderAgentConfigs();
    }

    /**
     * 渲染提供商配置
     */
    renderProviderConfig() {
        const siliconflowKeyInput = document.getElementById('siliconflow-api-key');
        const siliconflowBaseUrlInput = document.getElementById('siliconflow-base-url');
        const localApiKeyInput = document.getElementById('local-api-key');
        const localBaseUrlInput = document.getElementById('local-base-url');

        if (siliconflowKeyInput && this.config.providers.siliconflow) {
            siliconflowKeyInput.value = this.config.providers.siliconflow.api_key || '';
            siliconflowBaseUrlInput.value = this.config.providers.siliconflow.base_url || '';
        }

        if (localApiKeyInput && this.config.providers.local) {
            localApiKeyInput.value = this.config.providers.local.api_key || '';
            localBaseUrlInput.value = this.config.providers.local.base_url || '';
        }
    }

    /**
     * 渲染 Agent 配置
     */
    renderAgentConfigs() {
        const agents = ['planner', 'schedule', 'weather', 'talker'];
        const agentDescriptions = {
            planner: '规划器 - 高智能模型',
            schedule: '行程规划 - 标准模型',
            weather: '天气查询 - 标准模型',
            talker: '语音润色 - 创意模型'
        };

        const container = document.getElementById('agent-configs');
        if (!container) return;

        container.innerHTML = '';

        agents.forEach(agent => {
            const config = this.config.agents[agent] || this.config.agents.default;
            const item = document.createElement('div');
            item.className = 'agent-item';
            item.innerHTML = `
                <div class="agent-header">
                    <div>
                        <span class="agent-name">${this.capitalize(agent)}</span>
                        <span class="agent-description">${agentDescriptions[agent]}</span>
                    </div>
                </div>
                <div class="agent-controls">
                    <div class="form-group">
                        <label class="form-label">提供商</label>
                        <select class="form-select" id="agent-${agent}-provider" data-key="MODEL_${agent.toUpperCase()}_PROVIDER">
                            <option value="siliconflow" ${config.provider === 'siliconflow' ? 'selected' : ''}>SiliconFlow (云端)</option>
                            <option value="local" ${config.provider === 'local' ? 'selected' : ''}>本地模型</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label class="form-label">模型</label>
                        <input type="text" class="form-input" id="agent-${agent}-model"
                               value="${config.model}" data-key="MODEL_${agent.toUpperCase()}"
                               placeholder="模型名称">
                    </div>
                    <div class="form-group">
                        <label class="form-label">温度</label>
                        <div class="slider-container">
                            <input type="range" class="slider" id="agent-${agent}-temp"
                                   min="0" max="2" step="0.1" value="${config.temperature}"
                                   data-key="MODEL_${agent.toUpperCase()}_TEMP">
                            <span class="slider-value">${config.temperature}</span>
                        </div>
                    </div>
                    <div class="form-group">
                        <label class="form-label">最大 Token</label>
                        <input type="number" class="form-input" id="agent-${agent}-max-tokens"
                               value="${config.max_tokens}" min="1" max="32768"
                               data-key="MODEL_${agent.toUpperCase()}_MAX_TOKENS">
                    </div>
                </div>
            `;
            container.appendChild(item);
        });

        // 绑定滑块事件
        this.bindSliderEvents();
    }

    /**
     * 绑定滑块事件
     */
    bindSliderEvents() {
        document.querySelectorAll('.slider').forEach(slider => {
            slider.addEventListener('input', (e) => {
                const valueDisplay = e.target.nextElementSibling;
                valueDisplay.textContent = e.target.value;
            });
        });
    }

    /**
     * 绑定事件
     */
    bindEvents() {
        // 主题切换
        const themeToggle = document.querySelector('.theme-toggle');
        if (themeToggle) {
            themeToggle.addEventListener('click', () => this.toggleTheme());
        }

        // 保存配置
        const saveBtn = document.getElementById('save-config');
        if (saveBtn) {
            saveBtn.addEventListener('click', () => this.saveConfig());
        }

        // 返回按钮
        const backBtn = document.getElementById('back-to-chat');
        if (backBtn) {
            backBtn.addEventListener('click', () => {
                window.location.href = '/';
            });
        }

        // 测试 SiliconFlow 连接
        const testSiliconflowBtn = document.getElementById('test-siliconflow');
        if (testSiliconflowBtn) {
            testSiliconflowBtn.addEventListener('click', () => this.testConnection('siliconflow'));
        }

        // 测试本地模型连接
        const testLocalBtn = document.getElementById('test-local');
        if (testLocalBtn) {
            testLocalBtn.addEventListener('click', () => this.testConnection('local'));
        }
    }

    /**
     * 保存配置
     */
    async saveConfig() {
        const updates = {};

        // 收集提供商配置
        const siliconflowKey = document.getElementById('siliconflow-api-key').value;
        const siliconflowBaseUrl = document.getElementById('siliconflow-base-url').value;
        const localApiKey = document.getElementById('local-api-key').value;
        const localBaseUrl = document.getElementById('local-base-url').value;

        if (siliconflowKey) updates['SILICONFLOW_API_KEY'] = siliconflowKey;
        if (siliconflowBaseUrl) updates['SILICONFLOW_BASE_URL'] = siliconflowBaseUrl;
        updates['LOCAL_API_KEY'] = localApiKey;
        updates['LOCAL_BASE_URL'] = localBaseUrl;

        // 收集 Agent 配置
        document.querySelectorAll('[data-key]').forEach(el => {
            const key = el.dataset.key;
            let value = el.value;

            // 检查是否为空
            if (value === '' && (key.includes('API_KEY') || key.includes('MODEL'))) {
                // 空值不更新
                return;
            }

            updates[key] = value;
        });

        try {
            const response = await fetch('/api/config/update', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ updates })
            });

            const result = await response.json();

            if (result.success) {
                this.showToast(result.message, 'success');
            } else {
                this.showToast('保存配置失败', 'error');
            }
        } catch (error) {
            console.error('保存配置失败:', error);
            this.showToast('保存配置失败', 'error');
        }
    }

    /**
     * 测试连接
     */
    async testConnection(provider) {
        const btnId = provider === 'siliconflow' ? 'test-siliconflow' : 'test-local';
        const btn = document.getElementById(btnId);

        btn.textContent = '测试中...';
        btn.classList.add('testing');

        try {
            const response = await fetch('/api/config/test', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ provider })
            });

            const result = await response.json();

            btn.classList.remove('testing');

            if (result.success) {
                btn.textContent = '连接成功 ✓';
                btn.classList.add('success');
                this.showToast(result.message, 'success');

                setTimeout(() => {
                    btn.textContent = '测试连接';
                    btn.classList.remove('success');
                }, 3000);
            } else {
                btn.textContent = '连接失败 ✗';
                btn.classList.add('error');
                this.showToast(result.message, 'error');

                setTimeout(() => {
                    btn.textContent = '测试连接';
                    btn.classList.remove('error');
                }, 3000);
            }
        } catch (error) {
            console.error('测试连接失败:', error);
            btn.classList.remove('testing');
            btn.textContent = '连接失败 ✗';
            btn.classList.add('error');
            this.showToast('测试连接失败', 'error');

            setTimeout(() => {
                btn.textContent = '测试连接';
                btn.classList.remove('error');
            }, 3000);
        }
    }

    /**
     * 显示 Toast 提示
     */
    showToast(message, type = 'info') {
        let toast = document.querySelector('.toast');
        if (!toast) {
            toast = document.createElement('div');
            toast.className = 'toast';
            document.body.appendChild(toast);
        }

        toast.textContent = message;
        toast.className = `toast ${type} show`;

        setTimeout(() => {
            toast.classList.remove('show');
        }, 3000);
    }

    /**
     * 首字母大写
     */
    capitalize(str) {
        return str.charAt(0).toUpperCase() + str.slice(1);
    }
}

// 初始化配置管理器
document.addEventListener('DOMContentLoaded', () => {
    new ConfigManager();
});
