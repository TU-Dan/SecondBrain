const BASE = '';
const search = document.getElementById('search');
const articles = document.getElementById('articles');
const message = document.getElementById('message');
const more = document.getElementById('more');
const count = document.getElementById('count');
let offset = 0;
let currentQuery = '';
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
  const source = document.createElement('small');
  source.textContent = item.source_type || '知识笔记';
  const title = document.createElement('h3');
  title.textContent = item.title || '未命名文章';
  const summary = document.createElement('p');
  summary.textContent = item.summary || '点击查看与编辑正文';
  const tags = document.createElement('div');
  tags.className = 'tags';
  for (const value of parsedTags(item.tags).slice(0, 4)) {
    const tag = document.createElement('span');
    tag.className = 'tag';
    tag.textContent = value;
    tags.appendChild(tag);
  }
  card.append(source, title, summary, tags);
  articles.appendChild(card);
}

async function load(reset = false) {
  if (reset) {
    offset = 0;
    currentQuery = search.value.trim();
    articles.replaceChildren();
  }
  const sequence = ++requestNumber;
  message.textContent = '加载中…';
  more.hidden = true;
  try {
    const params = new URLSearchParams({q: currentQuery, offset: String(offset)});
    const response = await fetch(`${BASE}/api/articles?${params}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (sequence !== requestNumber) return;
    for (const item of data.articles) addCard(item);
    offset += data.articles.length;
    count.textContent = `已显示 ${offset} 篇`;
    more.hidden = !data.has_more;
    message.textContent = offset ? '' : '没有找到文章。';
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
load(true);
