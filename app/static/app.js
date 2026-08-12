const $ = (id) => document.getElementById(id);
const MAX_FILE_SIZE = 50 * 1024 * 1024;
const validExtensions = new Set(['pdf','docx','pptx','xlsx','html','htm','txt','md','csv','json','xml','jpg','jpeg','png']);
let result = null;
const themeToggle = $('themeToggle');
function setTheme(theme) {
  if (theme) document.documentElement.dataset.theme = theme; else delete document.documentElement.dataset.theme;
  const isDark = theme === 'dark' || (!theme && matchMedia('(prefers-color-scheme: dark)').matches);
  const label = `Switch to ${isDark ? 'light' : 'dark'} mode`;
  themeToggle.textContent = isDark ? '☼' : '☾';
  themeToggle.setAttribute('aria-label', label);
  themeToggle.title = label;
}
let savedTheme = null;
try { savedTheme = localStorage.getItem('theme'); } catch {}
setTheme(savedTheme === 'light' || savedTheme === 'dark' ? savedTheme : null);
themeToggle.addEventListener('click', () => {
  const current = document.documentElement.dataset.theme || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  const next = current === 'dark' ? 'light' : 'dark';
  setTheme(next);
  try { localStorage.setItem('theme', next); } catch {}
});

const states = [$('uploadState'), $('convertingState'), $('resultState'), $('errorState')];
const errorCopy = { empty_file:'That file is empty.', unsupported_type:"That file type isn't supported.", file_too_large:'Files must be 50 MB or smaller.', request_too_large:'That upload request is too large.', conversion_busy:'Another conversion is running. Try again in a moment.', conversion_failed:"Couldn't convert this file.", conversion_timeout:'The file took too long to convert.', output_too_large:'The converted Markdown is too large to return.' };
function show(state) { states.forEach((item) => { item.hidden = item !== state; }); }
function reset() { result = null; $('fileInput').value = ''; $('errorMessage').textContent = ''; show($('uploadState')); }
function extension(file) { return file.name.toLowerCase().split('.').pop(); }
function clientError(file) {
  if (!file || !validExtensions.has(extension(file))) return 'That file type isn\'t supported.';
  if (file.size > MAX_FILE_SIZE) return 'Files must be 50 MB or smaller.';
  if (!file.size) return 'That file is empty.';
  return null;
}
function renderError(message) { $('errorMessage').textContent = message; $('status').textContent = message; show($('errorState')); }

async function convert(file) {
  if (!file) return;
  const invalid = clientError(file);
  if (invalid) { renderError(invalid); return; }
  $('convertingName').textContent = `Converting ${file.name}`;
  $('status').textContent = `Converting ${file.name}`;
  show($('convertingState'));
  const form = new FormData(); form.append('file', file);
  try {
    const response = await fetch('/api/convert', { method:'POST', body:form });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error?.code || 'unknown');
    result = data;
    $('outputName').textContent = data.outputFilename;
    $('resultStats').textContent = `${data.words.toLocaleString()} words · ${data.characters.toLocaleString()} characters`;
    $('markdownSource').textContent = data.markdown;
    $('preview').innerHTML = data.previewAvailable ? DOMPurify.sanitize(marked.parse(data.markdown), {FORBID_TAGS:['script','iframe','form','object','embed'], FORBID_ATTR:['style','onclick','onerror'], ALLOWED_URI_REGEXP:/^(?:(?:https?|mailto):|#|\/(?!\/)|\.(?:\/|$)|[^:/?#]+(?:[/?#]|$))/i}) : '';
    $('preview').querySelectorAll('a').forEach((link) => { link.target = '_blank'; link.rel = 'noopener noreferrer'; });
    $('largeNotice').hidden = data.previewAvailable;
    if (!data.previewAvailable) selectTab('markdown'); else selectTab('preview');
    $('status').textContent = `Converted — ${data.outputFilename}`;
    show($('resultState'));
  } catch (err) { renderError(errorCopy[err.message] || 'Something went wrong. Try again.'); }
}
function selectTab(name) {
  const preview = name === 'preview';
  $('previewTab').classList.toggle('active', preview); $('markdownTab').classList.toggle('active', !preview);
  $('previewTab').setAttribute('aria-selected', String(preview)); $('markdownTab').setAttribute('aria-selected', String(!preview));
  $('previewTab').tabIndex = preview ? 0 : -1; $('markdownTab').tabIndex = preview ? -1 : 0;
  $('previewPanel').hidden = !preview; $('markdownPanel').hidden = preview;
}

const dropZone = $('dropZone');
dropZone.addEventListener('dragover', (event) => { event.preventDefault(); dropZone.classList.add('dragging'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragging'));
dropZone.addEventListener('drop', (event) => { event.preventDefault(); dropZone.classList.remove('dragging'); convert(event.dataTransfer.files[0]); });
$('fileInput').addEventListener('change', () => convert($('fileInput').files[0]));
dropZone.addEventListener('keydown', (event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); $('fileInput').click(); } });
$('previewTab').addEventListener('click', () => selectTab('preview')); $('markdownTab').addEventListener('click', () => selectTab('markdown'));
document.querySelectorAll('[role="tab"]').forEach((tab) => tab.addEventListener('keydown', (event) => { if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') { event.preventDefault(); selectTab(tab === $('previewTab') ? 'markdown' : 'preview'); $(tab === $('previewTab') ? 'markdownTab' : 'previewTab').focus(); } }));
$('retryButton').addEventListener('click', reset); $('anotherButton').addEventListener('click', reset);
$('copyButton').addEventListener('click', async () => { try { await navigator.clipboard.writeText(result.markdown); $('copyButton').textContent = 'Copied'; $('copyButton').classList.add('success'); setTimeout(() => { $('copyButton').textContent = 'Copy'; $('copyButton').classList.remove('success'); }, 2000); } catch { selectTab('markdown'); $('copyButton').textContent = 'Press ⌘C to copy'; } });
$('downloadButton').addEventListener('click', () => { const link = document.createElement('a'); link.href = URL.createObjectURL(new Blob([result.markdown], {type:'text/markdown'})); link.download = result.outputFilename; link.click(); URL.revokeObjectURL(link.href); });
