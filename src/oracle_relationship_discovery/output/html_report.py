"""Self-contained interactive HTML report with explicit light and dark themes."""

from __future__ import annotations

import html as html_lib
import json
from pathlib import Path

from oracle_relationship_discovery.models import AnalysisStats, RelationshipCandidate
from oracle_relationship_discovery.output.csv_report import candidate_row
from oracle_relationship_discovery.output.erd_models import ErdExportResult


def _safe_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False).replace("<", "\\u003c")


def write_html(
    path: Path,
    candidates: list[RelationshipCandidate],
    stats: AnalysisStats,
    analysis_mode: str = "",
    generated_at: str = "",
    erd_exports: list[ErdExportResult] | None = None,
) -> None:
    rows = [candidate_row(candidate, analysis_mode, generated_at) for candidate in candidates]
    exports = []
    export_cards = []
    for result in erd_exports or []:
        try:
            export_path = result.path.relative_to(path.parent).as_posix()
        except ValueError:
            export_path = result.path.name
        exports.append(
            {
                "path": export_path,
                "format": result.format.upper(),
                "scope": result.scope,
                "minConfidence": result.min_confidence,
                "relationships": result.relationship_count,
                "omitted": result.omitted_by_limit,
            }
        )
        label = html_lib.escape(export_path)
        href = html_lib.escape(export_path, quote=True)
        detail = (
            f"{result.format.upper()} · {result.scope} · "
            f"{result.relationship_count} relationships · "
            f"confidence ≥ {result.min_confidence:g}"
        )
        if result.omitted_by_limit:
            detail += f" · {result.omitted_by_limit} omitted"
        export_cards.append(
            f'<a class="erd-file" href="{href}" download><b>{label}</b>'
            f"<small>{html_lib.escape(detail)}</small></a>"
        )
    erd_section = ""
    if export_cards:
        erd_section = (
            '<section class="panel erd-panel"><div class="section-title">'
            "<h2>ERD exports</h2><span>DBML · inferred relationships</span></div>"
            f'<div class="erd-grid">{"".join(export_cards)}</div></section>'
        )
    data = _safe_json(rows)
    summary = _safe_json(
        {
            "schemas": stats.schemas,
            "tables": stats.tables,
            "columns": stats.columns,
            "generated": stats.candidates_generated,
            "validated": stats.candidates_validated,
            "skipped": stats.candidates_skipped_by_limit,
            "reported": len(rows),
            "mode": analysis_mode or "unknown",
            "generatedAt": generated_at,
            "erdExports": exports,
        }
    )
    html_document = (
        r"""<!doctype html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Oracle Relationship Discovery Report</title>
<style>
:root{color-scheme:light;--bg:#f3f6fb;--bg2:#e9eef8;--panel:#fff;--panel2:#f8faff;--text:#172033;--muted:#667085;--faint:#98a2b3;--line:#e1e7f0;--accent:#5b5bd6;--accent2:#7c3aed;--accentSoft:#ededff;--high:#087a55;--highSoft:#e7f8f1;--medHigh:#3164c6;--medHighSoft:#eaf1ff;--medium:#a15c05;--mediumSoft:#fff4df;--low:#b42318;--lowSoft:#ffebe9;--shadow:0 16px 42px rgba(29,41,57,.08);--header:rgba(255,255,255,.88)}
html[data-theme="dark"]{color-scheme:dark;--bg:#090d18;--bg2:#111827;--panel:#121827;--panel2:#171f31;--text:#edf2ff;--muted:#aab4c8;--faint:#768197;--line:#283349;--accent:#9897ff;--accent2:#c084fc;--accentSoft:#292750;--high:#55d6a5;--highSoft:#12372e;--medHigh:#82aaff;--medHighSoft:#172b52;--medium:#f4bd61;--mediumSoft:#3b2b12;--low:#ff8b83;--lowSoft:#441f25;--shadow:0 18px 46px rgba(0,0,0,.28);--header:rgba(18,24,39,.9)}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;min-height:100vh;background:radial-gradient(circle at 10% 0,var(--accentSoft),transparent 28%),linear-gradient(145deg,var(--bg),var(--bg2));color:var(--text);font:14px/1.5 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;transition:background .25s,color .25s}.shell{max-width:1680px;margin:auto;padding:28px}.hero{position:relative;overflow:hidden;padding:28px;border:1px solid var(--line);border-radius:22px;background:linear-gradient(130deg,var(--panel),var(--panel2));box-shadow:var(--shadow);margin-bottom:18px}.hero:after{content:"";position:absolute;width:260px;height:260px;border-radius:50%;right:-70px;top:-120px;background:linear-gradient(140deg,var(--accent),var(--accent2));opacity:.12}.topline{display:flex;justify-content:space-between;align-items:flex-start;gap:20px}.brand{display:flex;gap:14px;align-items:center}.logo{display:grid;place-items:center;width:48px;height:48px;border-radius:14px;color:white;background:linear-gradient(135deg,var(--accent),var(--accent2));box-shadow:0 10px 28px color-mix(in srgb,var(--accent) 30%,transparent)}h1{font-size:clamp(23px,3vw,34px);line-height:1.15;letter-spacing:-.035em;margin:0}.subtitle{color:var(--muted);margin:6px 0 0;max-width:760px}.actions{display:flex;gap:8px;z-index:1}.button{display:inline-flex;align-items:center;justify-content:center;gap:7px;border:1px solid var(--line);border-radius:11px;padding:9px 12px;background:var(--panel);color:var(--text);cursor:pointer;font:inherit;font-weight:650}.button:hover{border-color:var(--accent);color:var(--accent)}.runmeta{display:flex;flex-wrap:wrap;gap:8px;margin-top:20px}.pill{display:inline-flex;align-items:center;gap:7px;padding:6px 10px;border:1px solid var(--line);border-radius:999px;background:var(--panel2);color:var(--muted);font-size:12px}.dot{width:7px;height:7px;border-radius:50%;background:var(--accent)}.cards{display:grid;grid-template-columns:repeat(7,minmax(130px,1fr));gap:11px;margin:18px 0}.card,.panel{border:1px solid var(--line);background:var(--panel);box-shadow:var(--shadow)}.card{padding:16px;border-radius:16px;min-height:92px}.card strong{display:block;font-size:25px;letter-spacing:-.03em}.card span{color:var(--muted);font-size:12px}.overview{display:grid;grid-template-columns:minmax(280px,1fr) 2fr;gap:14px;margin-bottom:14px}.panel{border-radius:18px}.chart{padding:18px}.section-title{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}.section-title h2{font-size:15px;margin:0}.section-title span{color:var(--muted);font-size:12px}.bars{display:grid;gap:10px}.barrow{display:grid;grid-template-columns:100px 1fr 34px;gap:10px;align-items:center;font-size:12px}.track,.matchtrack{height:8px;border-radius:999px;background:var(--line);overflow:hidden}.fill{height:100%;border-radius:999px;background:linear-gradient(90deg,var(--accent),var(--accent2))}.notice{padding:18px;display:flex;gap:13px;align-items:flex-start}.notice-icon{flex:0 0 auto;display:grid;place-items:center;width:36px;height:36px;border-radius:11px;background:var(--mediumSoft);color:var(--medium);font-weight:800}.notice h2{font-size:15px;margin:0 0 4px}.notice p{color:var(--muted);margin:0}.erd-panel{padding:18px;margin-bottom:14px}.erd-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px}.erd-file{display:block;padding:13px;border:1px solid var(--line);border-radius:12px;background:var(--panel2);color:var(--text);text-decoration:none}.erd-file:hover{border-color:var(--accent);transform:translateY(-1px)}.erd-file b{display:block;color:var(--accent);margin-bottom:3px}.erd-file small{display:block}.toolbar{padding:14px;margin-bottom:14px}.filters{display:grid;grid-template-columns:minmax(220px,2fr) repeat(5,minmax(125px,1fr)) auto;gap:9px}.field input,.field select{width:100%;height:40px;padding:0 11px;border:1px solid var(--line);border-radius:10px;background:var(--panel2);color:var(--text);font:inherit;outline:none}.field input:focus,.field select:focus{border-color:var(--accent);box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 15%,transparent)}.filter-foot{display:flex;justify-content:space-between;color:var(--muted);font-size:12px;margin-top:11px}.table-panel{overflow:hidden}.table-scroll{overflow:auto;max-height:72vh}table{width:100%;border-collapse:separate;border-spacing:0;min-width:1280px}th,td{padding:12px 14px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}th{position:sticky;top:0;z-index:2;background:var(--header);backdrop-filter:blur(12px);font-size:11px;text-transform:uppercase;letter-spacing:.055em;color:var(--muted);white-space:nowrap;cursor:default}th[data-key]{cursor:pointer}th[data-key]:hover{color:var(--accent)}tbody tr{transition:background .15s}tbody tr:hover{background:var(--panel2)}.entity{font-weight:720;white-space:nowrap}.column{color:var(--muted);margin-top:2px}.type{color:var(--faint);font-size:11px}.badge{display:inline-flex;align-items:center;padding:3px 8px;border-radius:999px;font-size:10px;font-weight:750;letter-spacing:.03em;margin-top:6px}.key{background:var(--accentSoft);color:var(--accent)}.status{background:var(--panel2);color:var(--muted);border:1px solid var(--line)}.scorebox{display:flex;align-items:center;gap:10px}.score-ring{--score:0;display:grid;place-items:center;width:46px;height:46px;border-radius:50%;background:conic-gradient(var(--ring) calc(var(--score)*1%),var(--line) 0);position:relative}.score-ring:after{content:"";position:absolute;inset:5px;border-radius:50%;background:var(--panel)}.score-ring b{position:relative;z-index:1;font-size:12px}.label{font-size:11px;font-weight:800}.label.high{color:var(--high)}.label.medium-high{color:var(--medHigh)}.label.medium{color:var(--medium)}.label.low,.label.very-low{color:var(--low)}.quality{font-weight:700}.quality.strong{color:var(--high)}.quality.moderate{color:var(--medHigh)}.quality.limited{color:var(--medium)}.quality.none{color:var(--faint)}.matchtrack{margin-top:6px;width:110px}.matchfill{height:100%;background:var(--high);border-radius:999px}.muted{color:var(--muted)}small{color:var(--muted)}details{max-width:440px}summary{cursor:pointer;color:var(--accent);font-weight:650;list-style:none}summary::-webkit-details-marker{display:none}.breakdown{display:grid;grid-template-columns:1fr auto;gap:5px 15px;margin:11px 0;padding:11px;border-radius:10px;background:var(--panel2);color:var(--muted)}.explanation{color:var(--muted);margin:8px 0;font-size:12px}.empty{padding:50px;text-align:center;color:var(--muted)}.footer{display:flex;justify-content:space-between;gap:20px;color:var(--muted);font-size:12px;padding:18px 4px}@media(max-width:1250px){.cards{grid-template-columns:repeat(4,1fr)}.filters{grid-template-columns:repeat(3,1fr)}.field.search{grid-column:span 2}}@media(max-width:800px){.shell{padding:13px}.hero{padding:20px}.topline,.footer{flex-direction:column}.cards{grid-template-columns:repeat(2,1fr)}.overview{grid-template-columns:1fr}.filters{grid-template-columns:1fr}.field.search{grid-column:auto}.actions{position:absolute;right:14px;top:14px}.actions .button span{display:none}}
</style>
</head>
<body><main class="shell">
<header class="hero"><div class="topline"><div class="brand"><div class="logo" aria-hidden="true"><svg width="25" height="25" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/></svg></div><div><h1>Relationship Discovery</h1><p class="subtitle">Explainable, read-only Oracle relationship inference with privacy-preserving aggregate evidence.</p></div></div><div class="actions"><button class="button" id="theme" type="button" aria-label="Toggle color theme"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3a9 9 0 1 0 9 9c-5 2-11-4-9-9Z"/></svg><span>Theme</span></button></div></div><div class="runmeta"><span class="pill"><i class="dot"></i><b id="mode"></b></span><span class="pill" id="generated"></span><span class="pill">No sampled values persisted</span></div></header>
<section class="cards" id="cards"></section>
<section class="overview"><div class="panel chart"><div class="section-title"><h2>Confidence distribution</h2><span>reported rows</span></div><div class="bars" id="bars"></div></div><div class="panel notice"><div class="notice-icon">!</div><div><h2>Interpret scores as evidence, not proof</h2><p>Small samples are discounted. Overlap with a repeating non-key target receives only limited weight. Review ambiguous and non-key relationships before using them in an ERD or migration.</p></div></div></section>
__ERD__<section class="panel toolbar"><div class="filters"><div class="field search"><input id="search" placeholder="Search schema, table, column, explanation…"></div><div class="field"><select id="schema"><option value="">All schemas</option></select></div><div class="field"><select id="confidence"><option value="">All confidence</option></select></div><div class="field"><select id="cardinality"><option value="">All cardinalities</option></select></div><div class="field"><select id="key"><option value="">All target keys</option></select></div><div class="field"><select id="validation"><option value="">All validation</option></select></div><button class="button" id="clear" type="button">Clear</button></div><div class="filter-foot"><span id="count"></span><span>Click a column heading to sort</span></div></section>
<section class="panel table-panel"><div class="table-scroll"><table><thead><tr><th data-key="source_table">Source ↕</th><th data-key="target_table">Target ↕</th><th data-key="confidence_score">Confidence ↕</th><th data-key="match_ratio">Overlap ↕</th><th data-key="sample_size">Sample ↕</th><th data-key="cardinality">Cardinality ↕</th><th data-key="validation_status">Status ↕</th><th>Evidence</th></tr></thead><tbody id="body"></tbody></table><div id="empty" class="empty" hidden>No relationships match the current filters.</div></div></section>
<footer class="footer"><span>This tool discovers probable logical relationships. It never creates or modifies constraints.</span><span>Self-contained report · no external assets</span></footer>
</main>
<script>
const rows=__DATA__,stats=__SUMMARY__;let sortKey='confidence_score',sortAsc=false;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const slug=s=>String(s).toLowerCase().replaceAll(' ','-');
const num=v=>v===''||v==null?-1:Number(v);
const formatDate=value=>{if(!value)return 'Generation time unavailable';const d=new Date(value);return Number.isNaN(d.valueOf())?value:d.toLocaleString()};
const confidenceColor=label=>label==='HIGH'?'var(--high)':label==='MEDIUM-HIGH'?'var(--medHigh)':label==='MEDIUM'?'var(--medium)':'var(--low)';
const quality=n=>n<=0?['No sample','none']:n<30?['Limited sample','limited']:n<100?['Moderate sample','moderate']:['Strong sample','strong'];
function setTheme(theme){document.documentElement.dataset.theme=theme;localStorage.setItem('ord-theme',theme)}
const stored=localStorage.getItem('ord-theme');setTheme(stored||((matchMedia('(prefers-color-scheme:dark)').matches)?'dark':'light'));
document.getElementById('theme').addEventListener('click',()=>setTheme(document.documentElement.dataset.theme==='dark'?'light':'dark'));
document.getElementById('mode').textContent=stats.mode==='metadata-only'?'Metadata only':'Sampled validation';document.getElementById('generated').textContent=formatDate(stats.generatedAt);
const cardData=[['Schemas',stats.schemas],['Tables',stats.tables],['Columns',stats.columns],['Generated',stats.generated],['Validated',stats.validated],['Reported',stats.reported],['High confidence',rows.filter(r=>r.confidence_label==='HIGH').length]];
document.getElementById('cards').innerHTML=cardData.map(([k,v])=>`<article class="card"><strong>${v}</strong><span>${k}</span></article>`).join('');
const labels=['HIGH','MEDIUM-HIGH','MEDIUM','LOW','VERY LOW'],maxCount=Math.max(1,...labels.map(l=>rows.filter(r=>r.confidence_label===l).length));
document.getElementById('bars').innerHTML=labels.map(l=>{const n=rows.filter(r=>r.confidence_label===l).length;return `<div class="barrow"><span>${l}</span><div class="track"><div class="fill" style="width:${n/maxCount*100}%;background:${confidenceColor(l)}"></div></div><b>${n}</b></div>`}).join('');
function options(id,values){const e=document.getElementById(id);[...new Set(values.filter(Boolean))].sort().forEach(v=>e.insertAdjacentHTML('beforeend',`<option value="${esc(v)}">${esc(v)}</option>`))}
options('schema',rows.flatMap(r=>[r.source_schema,r.target_schema]));options('confidence',rows.map(r=>r.confidence_label));options('cardinality',rows.map(r=>r.cardinality));options('key',rows.map(r=>r.target_key_type));options('validation',rows.map(r=>r.validation_status));
function render(){const q=document.getElementById('search').value.toLowerCase(),schema=document.getElementById('schema').value,conf=document.getElementById('confidence').value,card=document.getElementById('cardinality').value,key=document.getElementById('key').value,validation=document.getElementById('validation').value;
 let filtered=rows.filter(r=>Object.values(r).join(' ').toLowerCase().includes(q)&&(!schema||(r.source_schema===schema||r.target_schema===schema))&&(!conf||r.confidence_label===conf)&&(!card||r.cardinality===card)&&(!key||r.target_key_type===key)&&(!validation||r.validation_status===validation));
 filtered.sort((a,b)=>{let x=a[sortKey],y=b[sortKey];if(['confidence_score','match_ratio','sample_size'].includes(sortKey)){x=num(x);y=num(y)}else{x=String(x).toLowerCase();y=String(y).toLowerCase()}return(x<y?-1:x>y?1:0)*(sortAsc?1:-1)});
 document.getElementById('count').textContent=`Showing ${filtered.length} of ${rows.length} reported relationships`;document.getElementById('empty').hidden=filtered.length>0;
 document.getElementById('body').innerHTML=filtered.map(r=>{const [qLabel,qClass]=quality(Number(r.sample_size));const match=num(r.match_ratio);return `<tr><td><div class="entity">${esc(r.source_schema)}.${esc(r.source_table)}</div><div class="column">${esc(r.source_column)} <span class="type">${esc(r.source_datatype)}</span></div></td><td><div class="entity">${esc(r.target_schema)}.${esc(r.target_table)}</div><div class="column">${esc(r.target_column)}</div><span class="badge key">${esc(r.target_key_type)}</span></td><td><div class="scorebox"><div class="score-ring" style="--score:${r.confidence_score};--ring:${confidenceColor(r.confidence_label)}"><b>${Math.round(r.confidence_score)}</b></div><span class="label ${slug(r.confidence_label)}">${esc(r.confidence_label)}</span></div></td><td>${match<0?'<span class="muted">Not sampled</span>':`<b>${match.toFixed(2)}%</b><div class="matchtrack"><div class="matchfill" style="width:${Math.max(0,Math.min(100,match))}%"></div></div><small>${r.matched_samples} of ${r.sample_size} rows</small>`}</td><td><span class="quality ${qClass}">${qLabel}</span><br><b>${r.sample_size}</b> <small>source rows</small>${r.target_sample_size?`<br><small>${r.target_sample_size} target rows</small>`:''}</td><td><b>${esc(r.cardinality)}</b><br><small>${r.cardinality_confidence}% confidence</small></td><td><span class="badge status">${esc(r.validation_status)}</span></td><td><details><summary>View score details</summary><div class="breakdown"><span>Name semantics</span><b>${r.name_score}</b><span>Datatype</span><b>${r.datatype_score}</b><span>Target key</span><b>${r.key_score}</b><span>Data overlap</span><b>${r.data_overlap_score}</b><span>Sample consistency</span><b>${r.consistency_score}</b><span>Structure</span><b>${r.structure_score}</b></div><p class="explanation">${esc(r.explanation)}</p></details></td></tr>`}).join('')}
['search','schema','confidence','cardinality','key','validation'].forEach(id=>document.getElementById(id).addEventListener('input',render));document.querySelectorAll('th[data-key]').forEach(th=>th.addEventListener('click',()=>{if(sortKey===th.dataset.key)sortAsc=!sortAsc;else{sortKey=th.dataset.key;sortAsc=true}render()}));document.getElementById('clear').addEventListener('click',()=>{['search','schema','confidence','cardinality','key','validation'].forEach(id=>document.getElementById(id).value='');render()});render();
</script></body></html>""".replace("__DATA__", data)
        .replace("__SUMMARY__", summary)
        .replace("__ERD__", erd_section)
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html_document, encoding="utf-8")
