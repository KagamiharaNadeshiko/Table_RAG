const apiBase = '';

function $(sel) { return document.querySelector(sel) }

function createEl(tag, props = {}, children = []) {
    const el = document.createElement(tag);
    Object.assign(el, props);
    children.forEach(c => el.appendChild(typeof c === 'string' ? document.createTextNode(c) : c));
    return el
}

// Tabs
document.querySelectorAll('nav.tabs button').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('nav.tabs button').forEach(b => b.classList.remove('active'))
        btn.classList.add('active')
        const tab = btn.dataset.tab
        document.querySelectorAll('.tab').forEach(sec => sec.classList.remove('visible'))
        $('#tab-' + tab).classList.add('visible')
    })
})

// Helpers
async function waitTaskUntilDone(kind, taskId, onUpdate) {
    const url = `${apiBase}/${kind}/tasks/${taskId}`
    while (true) {
        const r = await fetch(url)
        if (!r.ok) { throw new Error('任务查询失败') }
        const data = await r.json()
        if (onUpdate) onUpdate(data)
        if (data.status === 'succeeded' || data.status === 'failed') return data
        await new Promise(res => setTimeout(res, 1000))
    }
}

function setProgress(el, msg) { el.textContent = msg }

// Upload - single
$('#single-upload-form').addEventListener('submit', async(e) => {
    e.preventDefault()
    const file = $('#single-file').files[0]
    const excelDir = $('#single-excel-dir').value.trim() || ''
    if (!file) { return setProgress($('#single-upload-progress'), '请选择文件') }
    const form = new FormData()
    form.append('file', file)
    if (excelDir) form.append('excel_dir', excelDir)
    setProgress($('#single-upload-progress'), '上传中...')
    const resp = await fetch(`${apiBase}/data/upload`, { method: 'POST', body: form })
    if (!resp.ok) { setProgress($('#single-upload-progress'), '上传失败'); return }
    const info = await resp.json()
    setProgress($('#single-upload-progress'), `已提交导入任务：${info.task_id}，轮询中...`)
    try {
        const done = await waitTaskUntilDone('data', info.task_id, (d) => {
            setProgress($('#single-upload-progress'), `任务状态：${d.status}`)
        })
        setProgress($('#single-upload-progress'), `完成：${done.status}`)
    } catch (err) {
        setProgress($('#single-upload-progress'), `错误：${err}`)
    }
})

// Upload - multi
$('#multi-upload-form').addEventListener('submit', async(e) => {
    e.preventDefault()
    const files = Array.from($('#multi-files').files)
    const excelDir = $('#multi-excel-dir').value.trim() || ''
    if (files.length === 0) { return setProgress($('#multi-upload-progress'), '请选择文件') }
    const form = new FormData()
    for (const f of files) { form.append('files', f) }
    if (excelDir) form.append('excel_dir', excelDir)
    setProgress($('#multi-upload-progress'), '批量上传中...')
    const resp = await fetch(`${apiBase}/data/upload_many`, { method: 'POST', body: form })
    if (!resp.ok) { setProgress($('#multi-upload-progress'), '上传失败'); return }
    const info = await resp.json()
    setProgress($('#multi-upload-progress'), `已提交导入任务：${info.task_id}，轮询中...`)
    try {
        const done = await waitTaskUntilDone('data', info.task_id, (d) => {
            setProgress($('#multi-upload-progress'), `任务状态：${d.status}`)
        })
        setProgress($('#multi-upload-progress'), `完成：${done.status}`)
    } catch (err) {
        setProgress($('#multi-upload-progress'), `错误：${err}`)
    }
})

// Files list
async function refreshTables() {
    const docDir = $('#tables-doc-dir').value.trim()
    const params = new URLSearchParams()
    if (docDir) params.set('doc_dir', docDir)
    params.set('include_meta', 'true')
    const r = await fetch(`${apiBase}/tables?${params.toString()}`)
    if (!r.ok) { $('#tables-meta').textContent = '获取失败'; return }
    const data = await r.json()
    if (!data.meta || data.meta.length === 0) { $('#tables-meta').textContent = '无表格'; return }
    const table = createEl('table')
    const thead = createEl('thead')
    thead.appendChild(createEl('tr', {}, [
        createEl('th', { textContent: '表格ID' }),
        createEl('th', { textContent: '原始Excel' }),
        createEl('th', { textContent: '操作' }),
    ]))
    table.appendChild(thead)
    const tbody = createEl('tbody')
    for (const m of data.meta) {
        const tr = createEl('tr')
        const tTable = m.table || m.table_name || ''
        const original = m.original_filename || ''
        tr.appendChild(createEl('td', { textContent: tTable }))
        tr.appendChild(createEl('td', { textContent: original }))
        const btn = createEl('button', { textContent: '清理此文件' })
        btn.addEventListener('click', () => doCleanup(original))
        tr.appendChild(createEl('td', {}, [btn]))
        tbody.appendChild(tr)
    }
    table.appendChild(tbody)
    const wrap = $('#tables-meta')
    wrap.innerHTML = ''
    wrap.appendChild(table)
}

$('#refresh-tables').addEventListener('click', refreshTables)

// Cleanup
async function doCleanup(filename) {
    if (!filename) { setProgress($('#cleanup-progress'), '请填写原始文件名'); return }
    setProgress($('#cleanup-progress'), '提交清理任务中...')
    const resp = await fetch(`${apiBase}/cleanup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ targets: [filename], yes: true, dry_run: false })
    })
    if (!resp.ok) { setProgress($('#cleanup-progress'), '提交失败'); return }
    const info = await resp.json()
    try {
        const done = await waitTaskUntilDone('cleanup', info.task_id, (d) => {
            setProgress($('#cleanup-progress'), `任务状态：${d.status}`)
        })
        setProgress($('#cleanup-progress'), `完成：${done.status}`)
        refreshTables().catch(() => {})
    } catch (err) {
        setProgress($('#cleanup-progress'), `错误：${err}`)
    }
}

$('#do-cleanup').addEventListener('click', () => {
    const name = $('#cleanup-target').value.trim()
    doCleanup(name)
})

// Chat
$('#send-question').addEventListener('click', async() => {
    const question = $('#chat-question').value.trim()
    if (!question) { $('#chat-answer').textContent = '请输入问题'; return }
    const payload = {
        question,
        table_id: $('#chat-table-id').value.trim() || 'auto',
        backbone: $('#chat-backbone').value.trim() || undefined,
        embedding_policy: $('#chat-policy').value.trim() || undefined,
        doc_dir: $('#chat-doc-dir').value.trim() || undefined,
        excel_dir: $('#chat-excel-dir').value.trim() || undefined,
        bge_dir: $('#chat-bge-dir').value.trim() || undefined,
    }
    $('#chat-answer').textContent = '提问中...'
    const r = await fetch(`${apiBase}/chat/ask`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
    if (!r.ok) { $('#chat-answer').textContent = '请求失败'; return }
    const data = await r.json()
    $('#chat-answer').textContent = data.answer || ''
})

// Initial
refreshTables().catch(() => {})