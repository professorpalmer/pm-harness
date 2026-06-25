const $ = s => document.querySelector(s);
const stream = $("#stream"), artList = $("#artifact-list"),
      jobList = $("#job-list"), pill = $("#status-pill");
let running = false;

async function loadConfig(){
  const c = await (await fetch("/api/config")).json();
  $("#driver-name").textContent = c.driver;
  $("#driver-meta").textContent = `reach=${c.reach} · budget=${c.budget}`;
}

function setStatus(s){ pill.className = "pill " + s; pill.textContent = s; }

function el(cls, html){ const d=document.createElement("div"); d.className=cls;
  if(html!=null) d.innerHTML=html; return d; }

function addTurn(action, headHtml, bodyHtml){
  const t = el("turn");
  const h = el("turn-head");
  h.appendChild(el("badge "+action, action.replace("_"," ")));
  const lbl = document.createElement("span"); lbl.innerHTML = headHtml; h.appendChild(lbl);
  t.appendChild(h);
  if(bodyHtml!=null) t.appendChild(el("turn-body", bodyHtml));
  stream.appendChild(t); stream.scrollTop = stream.scrollHeight;
  return t;
}

function esc(s){ return (s||"").replace(/[&<>]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }

function pushArtifacts(arts){
  if(!arts || !arts.length) return;
  // clear the empty hint
  if(artList.querySelector(".empty")) artList.innerHTML="";
  for(const a of arts){
    const c = el("acard");
    c.innerHTML = `<div class="atype">${esc(a.type)}</div>`+
                  `<div class="ahead">${esc(a.headline)}</div>`+
                  (a.confidence!=null?`<div class="aconf">confidence ${a.confidence}</div>`:"");
    artList.appendChild(c);
  }
}

async function refreshJobs(){
  const jobs = await (await fetch("/api/jobs")).json();
  jobList.innerHTML="";
  for(const j of jobs.slice().reverse()){
    const it = el("job-item");
    it.innerHTML = `<div class="job-goal">${esc(j.goal||"(task)")}</div>`+
                   `<div class="job-meta">${esc(j.status.split('.').pop())} · ${j.artifacts} artifacts</div>`;
    it.onclick = async ()=>{
      const arts = await (await fetch("/api/artifacts?job_id="+encodeURIComponent(j.id))).json();
      artList.innerHTML=""; pushArtifacts(arts);
    };
    jobList.appendChild(it);
  }
}

function run(prompt){
  if(running) return; running = true; setStatus("running");
  $("#send").disabled = true;
  addTurn("run_swarm", `<span class="muted">you</span> &nbsp; ${esc(prompt)}`, null)
    .querySelector(".badge").className = "badge stop"; // user bubble styling reuse
  const es = new EventSource("/api/run?prompt="+encodeURIComponent(prompt));
  es.onmessage = (m)=>{
    const ev = JSON.parse(m.data);
    if(ev.kind==="done"){ es.close(); running=false; $("#send").disabled=false;
      if(pill.textContent==="running") setStatus("done"); refreshJobs(); return; }
    const d = ev.data||{};
    if(ev.kind==="intent"){
      if(d.action==="run_swarm")
        addTurn("run_swarm", `turn ${ev.turn} · <span class="muted">${d.tokens_out} tok</span>`,
          `<div class="goal">${esc(d.goal)}</div><div class="rationale">${esc(d.rationale)}</div>`);
      else
        addTurn(d.action, `turn ${ev.turn}`, `<div class="rationale">${esc(d.rationale)}</div>`);
    } else if(ev.kind==="executing"){
      addTurn("executing", `Puppetmaster running`, `<div class="goal">${esc(d.goal)}</div>`);
    } else if(ev.kind==="artifacts"){
      const body = (d.artifacts||[]).map(a=>
        `<div class="art"><span class="t">${esc(a.type)}</span>${esc(a.headline)}</div>`).join("");
      addTurn("run_swarm", `job ${esc(d.job_id)} · ${d.num} artifacts · ${esc((d.types||[]).join(", "))}`, body);
      pushArtifacts(d.artifacts);
    } else if(ev.kind==="final"){
      addTurn(d.action, `final · ${d.forced?"(forced) ":""}`, `<div class="rationale">${esc(d.rationale)}</div>`);
      setStatus("done");
    } else if(ev.kind==="error"){
      addTurn("error", `error`, `<div>${esc(d.error)}</div>`); setStatus("error");
    }
  };
  es.onerror = ()=>{ es.close(); running=false; $("#send").disabled=false;
    if(pill.textContent==="running") setStatus("error"); };
}

$("#composer").addEventListener("submit", e=>{
  e.preventDefault(); const p = $("#prompt").value.trim();
  if(!p) return; $("#prompt").value=""; run(p);
});

loadConfig(); refreshJobs();
