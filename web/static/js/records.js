// 记录页面 JavaScript

// 加载今天的记录
async function loadTodayRecords() {
    try {
        const response = await fetch('/api/records/today');
        const result = await response.json();

        if (result.success) {
            displayRecords(result.data, result.count);
        } else {
            alert('加载失败: ' + result.message);
        }
    } catch (error) {
        console.error('加载记录失败:', error);
        alert('加载记录失败: ' + error.message);
    }
}

// 加载最近的记录
async function loadRecentRecords() {
    try {
        const response = await fetch('/api/records/recent');
        const result = await response.json();

        if (result.success) {
            displayRecords(result.data, result.count);
        } else {
            alert('加载失败: ' + result.message);
        }
    } catch (error) {
        console.error('加载记录失败:', error);
        alert('加载记录失败: ' + error.message);
    }
}

// 显示记录
function displayRecords(records, count) {
    const container = document.getElementById('records-container');

    if (count === 0) {
        container.innerHTML = '<p class="text-muted">暂无记录</p>';
        return;
    }

    let html = `<p class="text-muted">共 ${count} 条记录</p>`;
    html += '<div class="records-grid">';

    records.forEach(record => {
        const isValid = record.is_valid === 1;
        const issues = record.issues ? JSON.parse(record.issues) : [];
        const imagePath = record.image_path;

        html += `
            <div class="record-item ${isValid ? '' : 'invalid'}">
                <div class="record-header">
                    <div class="time">${record.timestamp}</div>
                    <div class="status ${isValid ? 'valid' : 'invalid-status'}">
                        ${isValid ? '✓ 合格' : '✗ 不合格'}
                    </div>
                </div>

                ${imagePath ? `
                    <div class="record-image">
                        <img src="/image?path=${encodeURIComponent(imagePath)}"
                             alt="检测图片"
                             onclick="window.open(this.src)"
                             onerror="this.parentElement.innerHTML='<p class=\\'text-muted\\'>图片不可用</p>'">
                    </div>
                ` : ''}

                ${issues.length > 0 ? `
                    <div class="issues">
                        <strong>检测失败的项目:</strong>
                        <ul class="issues-list">
                            ${issues.map(issue => `<li>${issue}</li>`).join('')}
                        </ul>
                    </div>
                ` : ''}

                ${record.should_notify === 1 ? '<div class="notify-badge">已通知</div>' : ''}
            </div>
        `;
    });

    html += '</div>';
    container.innerHTML = html;
}
