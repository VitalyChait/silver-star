// ====== Elements ======
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

// ====== State ======
let conversationLog = [];
let answers = { role: '', hours: '', notes: '' };
let stage = 0;                   // 0 -> ask role, 1 -> hours, 2 -> notes, 3 -> ready
let pendingQuestion = null;      // server-driven follow-ups (location, work_type, etc.)
let intentDraft = null;          // latest parsed intent JSON

// Server-provided follow-ups (keys from /intent: missing_fields)
const FOLLOWUP_QUESTIONS = {
  location:  "Do you prefer remote, hybrid, or onsite? Any city or time zone?",
  work_type: "What work type fits—full-time, contract, or part-time?",
  seniority: "What seniority level should I target (junior/mid/senior/lead/staff/principal)?",
  salary_min:"Do you have a salary minimum in mind (and currency)?"
};

// ====== Utils ======
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

function pretty(obj){ return JSON.stringify(obj, null, 2); }

async function postJSON(url, body){
  const res = await fetch(url, {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const t = await res.text().catch(()=> '');
    throw new Error(t || (res.status + ' ' + res.statusText));
  }
  return res.json();
}

// Build a single string for the LLM collector
function buildIntentFreeText(){
  // Your 3-stage answers first, then the raw user turns (for extra signal)
  const staged = `
I'm looking for: ${answers.role || ''}.
Availability (hours/week): ${answers.hours || ''}.
Notes: ${answers.notes || ''}.
`.trim();
  const turns = conversationLog.filter(m => m.role === 'user').map(m => m.text).join('\n');
  return [staged, turns].filter(Boolean).join('\n');
}

// ====== Core flow ======
async function sendToIntentAndMaybeAskFollowup(){
  try {
    const combined = buildIntentFreeText();
    const resp = await postJSON('/intent', { user_responses: combined });
    intentDraft = resp.intent_json;

    const missing = Array.isArray(resp.missing_fields) ? resp.missing_fields : [];
    // Prefer server-driven follow-ups (one at a time)
    const nextKey = missing.find(k => FOLLOWUP_QUESTIONS[k]);
    if (nextKey) {
      pendingQuestion = nextKey;
      addMsg('bot', FOLLOWUP_QUESTIONS[nextKey]);
      return; // wait for the user's answer
    }

    // Otherwise show the editor
    addMsg('bot', 'Great — I drafted an intent below. You can tweak it and click "Search jobs".');
    intentTextarea.value = pretty(intentDraft);
    intentSection.classList.remove('hidden');
    suggestions && suggestions.classList.add('hidden');
  } catch (err) {
    console.error(err);
    addMsg('bot', 'Hmm, I couldn’t turn that into an intent yet. Try adding role, location, and key details.');
  }
}

composer.addEventListener('submit', async (e) => {
  e.preventDefault();
  const text = inputEl.value.trim();
  if (!text) return;
  inputEl.value = '';
  addMsg('user', text);

  // First honor any pending server-driven follow-up (fills into notes to keep it simple)
  if (pendingQuestion) {
    // Append the answer into notes so the LLM sees it next call
    answers.notes = [answers.notes, `${pendingQuestion}: ${text}`].filter(Boolean).join(' | ');
    pendingQuestion = null;
    await sendToIntentAndMaybeAskFollowup();
    return;
  }

  // Otherwise follow your 3-stage conversation
  if (stage === 0) {
    answers.role = text;
    stage = 1;
    addMsg('bot', 'Got it. How many hours a week are you available?');
  } else if (stage === 1) {
    answers.hours = text;
    stage = 2;
    addMsg('bot', 'Great. Anything else to know?');
  } else if (stage === 2) {
    answers.notes = text;
    stage = 3;
    addMsg('bot', 'Perfect. Let me process that...');
    await sendToIntentAndMaybeAskFollowup();
  } else {
    // Past stage 3, treat messages as refinements: push to notes and re-run
    answers.notes = [answers.notes, text].filter(Boolean).join(' | ');
    await sendToIntentAndMaybeAskFollowup();
  }
});

// Search button -> call /search
searchBtn.addEventListener('click', async () => {
  let intentObj;
  try { intentObj = JSON.parse(intentTextarea.value); }
  catch { addMsg('bot','Your intent JSON is invalid. Please fix it and try again.'); return; }

  addMsg('bot','Searching now...');
  try {
    const searchResp = await postJSON('/search', { intent_json: intentObj });
    resultsSection.classList.remove('hidden');
    const srcCount = Object.keys(searchResp.fetch_summary || {}).length;
    summaryEl.innerHTML = `<div class="small">Found ${searchResp.jobs_found} job(s) from ${srcCount} source(s).</div>`;
    cardsEl.innerHTML = '';

    (searchResp.jobs || []).forEach(j => {
      const c = document.createElement('div');
      c.className = 'card';
      const title = document.createElement('h4');
      const link = document.createElement('a');
      link.href = j.apply_url || '#';
      link.target = '_blank'; link.rel = 'noopener noreferrer';
      link.textContent = j.title || 'Untitled';
      title.appendChild(link);

      const meta = document.createElement('div');
      meta.className = 'small';
      const loc = j.location || '—';
      const company = j.company || 'Unknown';
      const posted = j.posted_at ? new Date(j.posted_at).toLocaleDateString() : '—';
      meta.textContent = `${company} • ${loc} • ${posted}`;

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

    addMsg('bot','I’ve listed the best matches below. Want to refine your intent and search again?');
  } catch (err) {
    console.error(err);
    addMsg('bot','Search failed. Check your intent JSON or try again.');
  }
});

// Reset button
resetBtn.addEventListener('click', () => {
  conversationLog = [];
  answers = { role: '', hours: '', notes: '' };
  stage = 0;
  pendingQuestion = null;
  intentDraft = null;

  intentTextarea.value = '';
  intentSection.classList.add('hidden');
  resultsSection.classList.add('hidden');
  summaryEl.textContent = '';
  cardsEl.innerHTML = '';

  chatEl.innerHTML = '';
  suggestions && suggestions.classList.remove('hidden');

  addMsg('bot', "👋 Hi again! What kind of job are you looking for?");
});

// Suggestions (if present)
document.querySelectorAll('.chip').forEach(btn => {
  btn.addEventListener('click', () => {
    const t = btn.dataset.text;
    inputEl.value = t;
    suggestions && suggestions.classList.add('hidden');
    composer.dispatchEvent(new Event('submit'));
  });
});

// Initial greeting
window.addEventListener('DOMContentLoaded', () => {
  addMsg('bot', "👋 Hi there! What kind of job are you looking for?");
});
