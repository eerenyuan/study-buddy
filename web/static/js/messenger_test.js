// Messenger 测试页面 JavaScript

let recipientCount = 0;

// 添加收件人输入框（带初始值）
function addRecipient(value = '', isNew = false) {
    const container = document.getElementById('recipients-container');

    // 如果是第一个收件人且不是新添加的，清空"加载中..."
    if (recipientCount === 0 && !isNew) {
        container.innerHTML = '';
    }

    const div = document.createElement('div');
    div.className = 'recipient-item';
    div.id = `recipient-${recipientCount}`;

    div.innerHTML = `
        <input type="text"
               id="recipient-input-${recipientCount}"
               placeholder="输入企业微信 userid"
               value="${value}"
               class="input-field"
               onchange="markAsModified()">
        <button type="button"
                class="btn btn-primary test-btn"
                onclick="testRecipient(${recipientCount})">
            🧪 测试
        </button>
        <span id="result-${recipientCount}" class="test-result"></span>
        <button type="button"
                class="btn btn-danger btn-sm"
                onclick="removeRecipient(${recipientCount})">
            ✕
        </button>
    `;

    container.appendChild(div);
    recipientCount++;
}

// 添加新收件人
function addNewRecipient() {
    addRecipient('', true);
}

// 移除收件人
function removeRecipient(id) {
    const element = document.getElementById(`recipient-${id}`);
    if (element) {
        element.remove();
    }
}

// 标记为已修改（可选功能，用于提示用户保存）
function markAsModified() {
    // 可以在这里添加UI提示，比如显示"未保存"提示
}

// 测试单个收件人
async function testRecipient(id) {
    const input = document.getElementById(`recipient-input-${id}`);
    const resultSpan = document.getElementById(`result-${id}`);
    const testBtn = input.parentElement.querySelector('.test-btn');

    const recipientId = input.value.trim();

    if (!recipientId) {
        showResult(resultSpan, 'error', '请输入收件人ID');
        return;
    }

    // 显示测试中状态
    showResult(resultSpan, 'testing', '测试中...');
    testBtn.disabled = true;

    try {
        const response = await fetch('/api/messenger/test', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                recipient_id: recipientId
            })
        });

        const result = await response.json();

        if (result.success) {
            let message = '✓ 成功';
            if (result.data) {
                message += ` (文字:${result.data.text ? '✓' : '✗'}, 图片:${result.data.image ? '✓' : '✗'})`;
            }
            showResult(resultSpan, 'success', message);
        } else {
            showResult(resultSpan, 'error', '✗ ' + (result.message || '发送失败'));
        }
    } catch (error) {
        console.error('测试失败:', error);
        showResult(resultSpan, 'error', '✗ 请求失败: ' + error.message);
    } finally {
        testBtn.disabled = false;
    }
}

// 保存收件人列表到配置文件
async function saveRecipients() {
    // 收集所有输入框的值
    const inputs = document.querySelectorAll('[id^="recipient-input-"]');
    const recipients = [];

    inputs.forEach(input => {
        const value = input.value.trim();
        if (value) {
            recipients.push(value);
        }
    });

    if (recipients.length === 0) {
        alert('请至少添加一个收件人ID');
        return;
    }

    // 用 | 连接多个收件人
    const recipientsStr = recipients.join('|');

    try {
        const response = await fetch('/api/messenger/save_recipients', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                recipients: recipientsStr
            })
        });

        const result = await response.json();

        if (result.success) {
            alert('保存成功！\n\n收件人列表:\n' + recipients.join('\n'));
            // 刷新页面显示更新后的配置
            location.reload();
        } else {
            alert('保存失败: ' + result.message);
        }
    } catch (error) {
        console.error('保存失败:', error);
        alert('保存失败: ' + error.message);
    }
}

// 显示测试结果
function showResult(element, status, message) {
    element.className = `test-result ${status}`;
    element.textContent = message;
}

// 页面加载时初始化收件人列表
document.addEventListener('DOMContentLoaded', function() {
    // 从全局变量获取当前收件人列表（由模板引擎渲染）
    const currentRecipients = window.currentRecipients || '';

    // 清空容器
    const container = document.getElementById('recipients-container');
    container.innerHTML = '';

    if (currentRecipients && currentRecipients !== 'None' && currentRecipients !== '') {
        // 解析 | 分隔的收件人列表
        const recipients = currentRecipients.split('|');
        recipients.forEach(recipient => {
            const trimmed = recipient.trim();
            if (trimmed) {
                addRecipient(trimmed);
            }
        });

        if (recipientCount === 0) {
            container.innerHTML = '<p class="text-muted">当前没有配置收件人</p>';
        }
    } else {
        // 如果没有配置，添加一个空输入框
        container.innerHTML = '<p class="text-muted">当前没有配置收件人，请添加</p>';
        addRecipient('', true);
    }
});
