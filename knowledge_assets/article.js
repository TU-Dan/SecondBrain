const BASE = '';
const id = document.body.dataset.articleId;
const api = `${BASE}/api/articles/${encodeURIComponent(id)}`;
const title = document.getElementById('title');
const tags = document.getElementById('tags');
const editor = document.getElementById('editor');
const preview = document.getElementById('preview');
const status = document.getElementById('status');
const saveButton = document.getElementById('save');
const editToggle = document.getElementById('edit-toggle');
const doneButton = document.getElementById('done');
const editorPane = document.getElementById('editor-pane');
const displayTags = document.getElementById('display-tags');
let revision = '';
let dirty = false;
editToggle.disabled = true;

function setStatus(message, state = '') {
  status.textContent = message;
  status.dataset.state = state;
}

function setMode(editing) {
  document.body.classList.toggle('is-editing', editing);
  editorPane.hidden = !editing;
  editToggle.hidden = editing;
  saveButton.hidden = !editing;
  doneButton.hidden = !editing;
  document.getElementById('mode-label').textContent = editing ? '编辑与实时预览' : '阅读模式';
  document.getElementById('preview-note').textContent = editing ? '实时预览' : '文章内容';
  if (editing) title.focus();
}

function showTags(values) {
  displayTags.replaceChildren();
  for (const value of values) {
    const chip = document.createElement('span');
    chip.className = 'display-tag';
    chip.textContent = value;
    displayTags.appendChild(chip);
  }
}

function parsedTags(value) {
  try {
    const result = JSON.parse(value || '[]');
    return Array.isArray(result) ? result.filter(tag => typeof tag === 'string') : [];
  } catch (_) {
    return [];
  }
}

function asset(url) {
  return typeof url === 'string' && url.startsWith('/static/images/') ? `${BASE}${url}` : url;
}

function render() {
  document.getElementById('word-count').textContent = `${editor.value.length} 字符`;
  if (!window.marked || !window.DOMPurify) {
    preview.textContent = editor.value;
    return;
  }
  preview.innerHTML = DOMPurify.sanitize(marked.parse(editor.value));
  for (const image of preview.querySelectorAll('img')) image.src = asset(image.getAttribute('src'));
  for (const link of preview.querySelectorAll('a')) {
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
  }
}

async function load() {
  try {
    const [articleResponse, contentResponse] = await Promise.all([fetch(api), fetch(`${api}/content`)]);
    if (!articleResponse.ok || !contentResponse.ok) throw new Error('文章不可用');
    const article = await articleResponse.json();
    const content = await contentResponse.json();
    document.title = `${article.title} · Second Brain`;
    document.getElementById('heading').textContent = article.title || '未命名文章';
    document.getElementById('toolbar-title').textContent = article.title || '未命名文章';
    document.getElementById('source').textContent = article.source_type || '知识笔记';
    document.getElementById('date').textContent = article.created_at ? article.created_at.slice(0, 10) : '';
    title.value = article.title || '';
    const tagValues = parsedTags(article.tags);
    tags.value = tagValues.join('，');
    showTags(tagValues);
    editor.value = content.content;
    revision = content.revision;
    document.getElementById('fallback-note').hidden = !content.fallback;
    if (article.image_url) {
      const cover = document.getElementById('cover');
      cover.src = asset(article.image_url);
      cover.hidden = false;
    }
    if (article.source_url && /^https?:\/\//i.test(article.source_url)) {
      const link = document.getElementById('source-link');
      link.href = article.source_url;
      link.hidden = false;
    }
    editToggle.disabled = false;
    setStatus('已加载');
    render();
  } catch (_) {
    setStatus('加载失败，请刷新页面重试', 'error');
    saveButton.disabled = true;
  }
}

async function send(url, method, body) {
  const response = await fetch(url, {
    method,
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body)
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}

async function save() {
  const newTitle = title.value.trim();
  const newTags = tags.value.split(/[,，]/).map(tag => tag.trim()).filter(Boolean);
  if (!newTitle) {
    setStatus('标题不能为空', 'error');
    title.focus();
    return false;
  }
  if (newTags.length > 20 || newTags.some(tag => tag.length > 40)) {
    setStatus('最多 20 个标签，每个不超过 40 字', 'error');
    return false;
  }
  saveButton.disabled = true;
  doneButton.disabled = true;
  setStatus('保存中…');
  try {
    const content = await send(`${api}/content`, 'PUT', {content: editor.value, revision});
    revision = content.revision;
    await send(api, 'PATCH', {title: newTitle, tags: newTags});
    document.getElementById('heading').textContent = newTitle;
    document.getElementById('toolbar-title').textContent = newTitle;
    document.title = `${newTitle} · Second Brain`;
    showTags(newTags);
    document.getElementById('fallback-note').hidden = true;
    dirty = false;
    setStatus('已保存', 'saved');
    return true;
  } catch (error) {
    setStatus(error.message, 'error');
    return false;
  } finally {
    saveButton.disabled = false;
    doneButton.disabled = false;
  }
}

for (const field of [title, tags, editor]) field.addEventListener('input', () => {
  dirty = true;
  setStatus('有未保存的修改', 'dirty');
});
editor.addEventListener('input', render);
saveButton.addEventListener('click', save);
editToggle.addEventListener('click', () => setMode(true));
doneButton.addEventListener('click', async () => {
  if (!dirty || await save()) setMode(false);
});
window.addEventListener('beforeunload', (event) => {
  if (dirty) {
    event.preventDefault();
    event.returnValue = '';
  }
});
load();
