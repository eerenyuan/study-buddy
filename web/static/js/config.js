// 配置页面 JavaScript

let ruleIndex = 0;

// 添加规则
function addRule() {
    const container = document.getElementById('rules-container');
    const ruleDiv = document.createElement('div');
    ruleDiv.className = 'rule-item';
    ruleDiv.innerHTML = `
        <input type="text"
               name="rule_key_${ruleIndex}"
               placeholder="字段名"
               class="input-field">
        <input type="text"
               name="rule_regexp_${ruleIndex}"
               placeholder="正则表达式"
               class="input-field regexp-field">
        <button type="button" class="btn btn-danger btn-sm" onclick="removeRule(this)">
            ✕
        </button>
    `;
    container.appendChild(ruleDiv);
    ruleIndex++;
}

// 移除规则
function removeRule(button) {
    const ruleItem = button.parentElement;
    ruleItem.remove();
}

// 收集规则数据
function collectRules() {
    const rules = [];
    const ruleItems = document.querySelectorAll('.rule-item');

    ruleItems.forEach(item => {
        const keyInput = item.querySelector('input[name^="rule_key_"]');
        const regexpInput = item.querySelector('input[name^="rule_regexp_"]');

        if (keyInput && regexpInput && keyInput.value && regexpInput.value) {
            rules.push({
                key: keyInput.value,
                regexp: regexpInput.value
            });
        }
    });

    return rules;
}

// 保存配置
async function saveConfig() {
    const form = document.getElementById('config-form');
    const formData = new FormData(form);

    const config = {
        rules: collectRules()
    };

    // 收集其他字段
    formData.forEach((value, key) => {
        if (!key.startsWith('rule_key_') && !key.startsWith('rule_regexp_')) {
            if (key === 'enable_preview' || key === 'enable_time_scheduler') {
                config[key] = form.querySelector(`[name="${key}"]`).checked;
            } else {
                config[key] = value;
            }
        }
    });

    try {
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(config)
        });

        const result = await response.json();

        if (result.success) {
            alert('配置已保存！');
            // 可以选择跳转回主页
            // window.location.href = '/';
        } else {
            alert('保存失败: ' + result.message);
        }
    } catch (error) {
        console.error('保存配置失败:', error);
        alert('保存配置失败: ' + error.message);
    }
}

// 绑定事件
document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('config-form').addEventListener('submit', function(e) {
        e.preventDefault();
        saveConfig();
    });
});
