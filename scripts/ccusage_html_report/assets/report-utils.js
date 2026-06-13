function fmt(n) {
  n = Number(n || 0);
  if (Math.abs(n) >= 1e9) return (n / 1e9).toFixed(2) + 'B';
  if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(2) + 'M';
  if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(1) + 'K';
  return String(Math.round(n));
}
function money(n) {
  if (n === undefined || n === null || Number.isNaN(Number(n))) return 'n/a';
  return '$' + Number(n).toFixed(2);
}
function compactMoney(n) {
  n = Number(n || 0);
  const sign = n < 0 ? '-' : '';
  const abs = Math.abs(n);
  if (abs >= 1e9) return sign + '$' + (abs / 1e9).toFixed(2) + 'B';
  if (abs >= 1e6) return sign + '$' + (abs / 1e6).toFixed(2) + 'M';
  if (abs >= 1e3) return sign + '$' + (abs / 1e3).toFixed(2) + 'K';
  return sign + '$' + abs.toFixed(2);
}
function priceMoney(n) {
  if (n === undefined || n === null || Number.isNaN(Number(n))) return 'n/a';
  const value = Number(n);
  if (Math.abs(value) >= 1) return '$' + value.toFixed(2);
  if (Math.abs(value) >= .01) return '$' + value.toFixed(3);
  return '$' + value.toFixed(4);
}
function metricFmt(metric, value) {
  return metric === 'costUSD' ? compactMoney(value) : fmt(value);
}
function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
}
function safeMarkdownUrl(url) {
  const value = String(url || '').trim();
  if (!value) return '';
  try {
    const parsed = new URL(value, window.location.href);
    if (!['http:', 'https:', 'mailto:'].includes(parsed.protocol)) return '';
  } catch (_) {
    return '';
  }
  return esc(value);
}
function renderInlineMarkdown(value) {
  const stash = [];
  const hold = html => {
    const token = `\u0000MD${stash.length}\u0000`;
    stash.push(html);
    return token;
  };
  let text = String(value ?? '');
  text = text.replace(/`([^`\n]+)`/g, (_, code) => hold(`<code>${esc(code)}</code>`));
  text = text.replace(/\[([^\]\n]+)\]\(([^)\s]+)(?:\s+"[^"]*")?\)/g, (match, label, url) => {
    const href = safeMarkdownUrl(url);
    if (!href) return match;
    return hold(`<a href="${href}" target="_blank" rel="noopener noreferrer">${renderInlineMarkdown(label)}</a>`);
  });
  let html = esc(text);
  html = html
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/__([^_]+)__/g, '<strong>$1</strong>')
    .replace(/\*([^*\s][^*]*?)\*/g, '<em>$1</em>')
    .replace(/_([^_\s][^_]*?)_/g, '<em>$1</em>')
    .replace(/~~([^~]+)~~/g, '<del>$1</del>');
  stash.forEach((stored, index) => {
    html = html.split(`\u0000MD${index}\u0000`).join(stored);
  });
  return html;
}
function splitTableRow(line) {
  return line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(cell => cell.trim());
}
function isMarkdownTableSeparator(line) {
  return /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line);
}
function markdownTableHtml(lines) {
  const header = splitTableRow(lines[0]);
  const body = lines.slice(2).map(splitTableRow);
  return `<table><thead><tr>${header.map(cell => `<th>${renderInlineMarkdown(cell)}</th>`).join('')}</tr></thead><tbody>${body.map(row => `<tr>${row.map(cell => `<td>${renderInlineMarkdown(cell)}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
}
function markdownToHtml(source) {
  const lines = String(source ?? '').replace(/\r\n?/g, '\n').split('\n');
  const html = [];
  let paragraph = [];
  let quote = [];
  let listType = null;
  let listItems = [];
  let fence = null;
  let fenceLang = '';
  let fenceLines = [];

  const flushParagraph = () => {
    if (!paragraph.length) return;
    html.push(`<p>${renderInlineMarkdown(paragraph.join(' '))}</p>`);
    paragraph = [];
  };
  const flushQuote = () => {
    if (!quote.length) return;
    html.push(`<blockquote>${quote.map(line => `<p>${renderInlineMarkdown(line)}</p>`).join('')}</blockquote>`);
    quote = [];
  };
  const flushList = () => {
    if (!listType) return;
    html.push(`<${listType}>${listItems.map(item => `<li>${renderInlineMarkdown(item)}</li>`).join('')}</${listType}>`);
    listType = null;
    listItems = [];
  };
  const flushFence = () => {
    const lang = fenceLang ? ` data-lang="${esc(fenceLang)}"` : '';
    html.push(`<pre><code${lang}>${esc(fenceLines.join('\n'))}</code></pre>`);
    fence = null;
    fenceLang = '';
    fenceLines = [];
  };

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    const trimmed = line.trim();

    if (fence) {
      if (trimmed.startsWith(fence)) flushFence();
      else fenceLines.push(line);
      continue;
    }

    const fenceMatch = trimmed.match(/^(```|~~~)\s*([A-Za-z0-9_-]+)?/);
    if (fenceMatch) {
      flushParagraph();
      flushQuote();
      flushList();
      fence = fenceMatch[1];
      fenceLang = fenceMatch[2] || '';
      continue;
    }

    if (!trimmed) {
      flushParagraph();
      flushQuote();
      flushList();
      continue;
    }

    if (line.includes('|') && lines[i + 1] && isMarkdownTableSeparator(lines[i + 1])) {
      const tableLines = [line, lines[i + 1]];
      i += 2;
      while (i < lines.length && lines[i].trim() && lines[i].includes('|')) {
        tableLines.push(lines[i]);
        i += 1;
      }
      i -= 1;
      flushParagraph();
      flushQuote();
      flushList();
      html.push(markdownTableHtml(tableLines));
      continue;
    }

    const heading = trimmed.match(/^(#{1,6})\s+(.+?)\s*#*$/);
    if (heading) {
      flushParagraph();
      flushQuote();
      flushList();
      const level = heading[1].length;
      html.push(`<h${level}>${renderInlineMarkdown(heading[2])}</h${level}>`);
      continue;
    }

    if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
      flushParagraph();
      flushQuote();
      flushList();
      html.push('<hr>');
      continue;
    }

    const quoteMatch = line.match(/^\s*>\s?(.*)$/);
    if (quoteMatch) {
      flushParagraph();
      flushList();
      quote.push(quoteMatch[1]);
      continue;
    }

    const listMatch = line.match(/^\s*((?:[-*+])|\d+\.)\s+(.+)$/);
    if (listMatch) {
      flushParagraph();
      flushQuote();
      const nextType = /\d+\./.test(listMatch[1]) ? 'ol' : 'ul';
      if (listType && listType !== nextType) flushList();
      listType = nextType;
      listItems.push(listMatch[2]);
      continue;
    }

    flushQuote();
    flushList();
    paragraph.push(trimmed);
  }

  if (fence) flushFence();
  flushParagraph();
  flushQuote();
  flushList();
  return html.join('');
}
function uniqueSorted(values) {
  return Array.from(new Set(values.map(v => String(v || '').trim()).filter(Boolean))).sort((a, b) => a.localeCompare(b));
}
function optionHtml(label, value = '') {
  return `<option value="${esc(value)}">${esc(label)}</option>`;
}
