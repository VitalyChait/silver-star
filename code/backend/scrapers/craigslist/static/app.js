const chatEl = document.getElementById('chat');
const composer = document.getElementById('composer');
const inputEl = document.getElementById('user-input');
const suggestions = document.getElementById('suggestions');
const intentSection = document.getElementById('intent-editor');
const intentTextarea = document.getElementById('intent-json');
const searchBtn = document.getElementById('search-btn');
const resetBtn = document.getElementById('reset-btn');
const resultsSection = document.getElementById('results');
const summaryEl = document.getElementById('summary');
const cardsEl = document.getElementById('cards');

let conversationLog = [];
let answers = { role: '', location: '', salary: '' };
let stage = 0; // 0=start, 1=location, 2=salary, 3=ready

function addMsg(role, text){
  const row = document.createElement('div');
  row.className = 'message ' + (role === 'user' ? 'user' : 'bot');
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = text;
  row.appendChild(bubble);
  chatEl.appendChild(row);
  chatEl.scrollTop = chatEl.scrollHeight;
  conversationLog.push({ role, text });
}

async function postJSON(url, body){
  const res = await fetch(url, {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function runIntentCollection(){
  const text = `
  I'm looking for: ${answers.role}.
  Location: ${answers.location}.
  Salary: ${answers.salary}.
  `;
  try {
    const intentResp = await postJSON('/intent', { user_responses: text });
    addMsg('bot', 'Here’s the intent I built. You can tweak it below and click "Search jobs".');
    intentTextarea.value = JSON.stringify(intentResp.intent_json, null, 2);
    intentSection.classList.remove('hidden');
  } catch (err) {
    console.error(err);
    addMsg('bot', 'Sorry, I couldn’t interpret that. Try describing the role again.');
  }
}

// Handle the conversation flow
composer.addEventListener('submit', async (e) => {
  e.preventDefault();
  const text = inputEl.value.trim();
  if (!text) return;
  inputEl.value = '';
  addMsg('user', text);

  if (stage === 0) {
    answers.role = text;
    stage = 1;
    addMsg('bot', 'Got it. How many hours a week are you available?');
  } else if (stage === 1) {
    answers.location = text;
    stage = 2;
    addMsg('bot', 'Great. Anything else to know?');
  } else if (stage === 2) {
    answers.salary = text;
    stage = 3;
    addMsg('bot', 'Perfect. Let me process that...');
    await runIntentCollection();
  } else {
    addMsg('bot', 'You can refine your intent or click "Search jobs" below.');
  }
});

// Initial greeting
window.addEventListener('DOMContentLoaded', () => {
  addMsg('bot', "👋 Hi there! What kind of job are you looking for?");
});


searchBtn.addEventListener('click', async () => {
  let intentObj;
  try { intentObj = JSON.parse(intentTextarea.value); }
  catch { addMsg('bot','Your intent JSON is invalid. Please fix and try again.'); return; }

  addMsg('bot','Searching now...');
  try{
    const searchResp = await postJSON('/search', { intent_json: intentObj });
    resultsSection.classList.remove('hidden');
    const srcCount = Object.keys(searchResp.fetch_summary || {}).length;
    summaryEl.innerHTML = '<div class="small">Found ' + searchResp.jobs_found + ' job(s) from ' + srcCount + ' source(s).</div>';
    cardsEl.innerHTML = '';

    (searchResp.jobs || []).forEach(j => {
      const c = document.createElement('div');
      c.className = 'card';
      const title = document.createElement('h4');
      const link = document.createElement('a');
      link.href = j.apply_url || '#';
      link.target = '_blank'; link.rel='noopener noreferrer';
      link.textContent = j.title || 'Untitled';
      title.appendChild(link);

      const meta = document.createElement('div');
      meta.className = 'small';
      const loc = j.location || '—';
      const company = j.company || 'Unknown';
      const posted = j.posted_at ? new Date(j.posted_at).toLocaleDateString() : '—';
      meta.textContent = company + ' • ' + loc + ' • ' + posted;

      const badges = document.createElement('div');
      badges.className = 'badges';
      (j.badges || []).forEach(b => {
        const badge = document.createElement('span');
        badge.className = 'badge';
        badge.textContent = b;
        badges.appendChild(badge);
      });

      const snippet = document.createElement('div');
      snippet.className = 'small';
      snippet.innerHTML = (j.snippet || '').slice(0, 300);

      c.appendChild(title);
      c.appendChild(meta);
      c.appendChild(badges);
      c.appendChild(snippet);
      cardsEl.appendChild(c);
    });
    addMsg('bot','I’ve listed the best matches. Want to refine and search again?');
  } catch(err){
    console.error(err);
    addMsg('bot','Search failed. Check your intent or try again.');
  }
});

resetBtn.addEventListener('click', () => {
  intentDraft = null;
  conversationLog = [];
  pendingQuestion = null;
  intentTextarea.value = '';
  intentSection.classList.add('hidden');
  resultsSection.classList.add('hidden');
  summaryEl.textContent = '';
  cardsEl.innerHTML = '';
  suggestions.classList.remove('hidden');
  chatEl.innerHTML = '';
  addMsg('bot', "Hi again! Tell me about the job you're after, or tap a suggestion to start.");
});
