const BASE = '/brain';
const id = document.body.dataset.articleId;
const api = `${BASE}/api/articles/${encodeURIComponent(id)}`;
const title = document.getElementById('title');
const tags = document.getElementById('tags');
const editor = document.getElementById('editor');
const preview = document.getElementById('preview');
const status = document.getElementById('status');
const saveButton = document.getElementById('save');
let revision = '';

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
    document.title = `${article.title} · 我的知识库`;
    document.getElementById('heading').textContent = article.title || '未命名文章';
    document.getElementById('source').textContent = article.source_type || '知识笔记';
    title.value = article.title || '';
    tags.value = parsedTags(article.tags).join('，');
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
    status.textContent = '已加载';
    render();
  } catch (_) {
    status.textContent = '加载失败，请刷新页面重试';
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
    status.textContent = '标题不能为空';
    title.focus();
    return;
  }
  if (newTags.length > 20 || newTags.some(tag => tag.length > 40)) {
    status.textContent = '最多 20 个标签，每个不超过 40 字';
    return;
  }
  saveButton.disabled = true;
  status.textContent = '保存中…';
  try {
    const content = await send(`${api}/content`, 'PUT', {content: editor.value, revision});
    revision = content.revision;
    await send(api, 'PATCH', {title: newTitle, tags: newTags});
    document.getElementById('heading').textContent = newTitle;
    document.title = `${newTitle} · 我的知识库`;
    document.getElementById('fallback-note').hidden = true;
    status.textContent = '已保存';
  } catch (error) {
    status.textContent = error.message;
  } finally {
    saveButton.disabled = false;
  }
}

for (const field of [title, tags, editor]) field.addEventListener('input', () => { status.textContent = '有未保存的修改'; });
editor.addEventListener('input', render);
saveButton.addEventListener('click', save);
load();
