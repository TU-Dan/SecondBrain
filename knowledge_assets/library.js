const BASE = '';
const search = document.getElementById('search');
const tagFilter = document.getElementById('tag-filter');
const articles = document.getElementById('articles');
const message = document.getElementById('message');
const more = document.getElementById('more');
const count = document.getElementById('count');
const sidebarCount = document.getElementById('sidebar-count');
const filterSummary = document.getElementById('filter-summary');
let offset = 0;
let currentQuery = '';
let currentTag = '';
let requestNumber = 0;

function parsedTags(value) {
  try {
    const tags = JSON.parse(value || '[]');
    return Array.isArray(tags) ? tags.filter(tag => typeof tag === 'string') : [];
  } catch (_) {
    return [];
  }
}

function addCard(item) {
  const card = document.createElement('a');
  card.className = 'card';
  card.href = `${BASE}/article/${encodeURIComponent(item.id)}`;
  const top = document.createElement('div');
  top.className = 'card-top';
  const index = document.createElement('span');
  index.className = 'card-index';
  index.textContent = String(articles.children.length + 1).padStart(3, '0');
  const source = document.createElement('span');
  source.className = 'card-source';
  source.textContent = item.source_type || '知识笔记';
  top.append(index, source);
  const title = document.createElement('h3');
  title.className = 'card-title';
  title.textContent = item.title || '未命名文章';
  const summary = document.createElement('p');
  summary.className = 'card-summary';
  summary.textContent = item.summary || '点击查看与编辑正文';
  const tags = document.createElement('div');
  tags.className = 'card-tags';
  for (const value of parsedTags(item.tags).slice(0, 4)) {
    const tag = document.createElement('span');
    tag.className = 'tag';
    tag.textContent = value;
    tags.appendChild(tag);
  }
  if (!tags.children.length && item.created_at) {
    const date = document.createElement('span');
    date.className = 'tag';
    date.textContent = item.created_at.slice(0, 10);
    tags.appendChild(date);
  }
  const footer = document.createElement('div');
  footer.className = 'card-footer';
  const arrow = document.createElement('span');
  arrow.className = 'card-arrow';
  arrow.setAttribute('aria-hidden', 'true');
  arrow.textContent = '↗';
  footer.append(tags, arrow);
  card.append(top, title, summary, footer);
  articles.appendChild(card);
}

async function loadTags() {
  try {
    const response = await fetch(`${BASE}/api/tags`);
    if (!response.ok) return;
    const data = await response.json();
    for (const item of data.tags.slice(0, 30)) {
      const option = document.createElement('option');
      option.value = item.tag;
      option.textContent = `${item.tag} (${item.count})`;
      tagFilter.appendChild(option);
    }
  } catch (_) {
    // The article list remains usable if tag metadata is unavailable.
  }
}

async function load(reset = false) {
  if (reset) {
    offset = 0;
    currentQuery = search.value.trim();
    currentTag = tagFilter.value;
    articles.replaceChildren();
  }
  const sequence = ++requestNumber;
  message.textContent = '加载中…';
  more.hidden = true;
  try {
    const params = new URLSearchParams({q: currentQuery, tag: currentTag, offset: String(offset)});
    const response = await fetch(`${BASE}/api/articles?${params}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (sequence !== requestNumber) return;
    for (const item of data.articles) addCard(item);
    offset += data.articles.length;
    count.textContent = `已显示 ${offset}${data.has_more ? '+' : ''} 篇文章`;
    sidebarCount.textContent = `${offset}${data.has_more ? '+' : ''}`;
    more.hidden = !data.has_more;
    message.textContent = offset ? '' : '没有找到文章。';
    filterSummary.hidden = !currentTag;
    filterSummary.textContent = currentTag ? `当前标签：${currentTag}` : '';
  } catch (_) {
    if (sequence === requestNumber) message.textContent = '加载失败，请刷新页面重试。';
  }
}

let timer;
search.addEventListener('input', () => {
  clearTimeout(timer);
  timer = setTimeout(() => load(true), 250);
});
more.addEventListener('click', () => load());
tagFilter.addEventListener('change', () => load(true));
loadTags();
load(true);
