/* Web calculator: steps 3-8 of the tank-vessel-design workflow in the browser.
   The calculation is the pv_design engine itself (Python, run by Pyodide from
   engine.json); this file only moves data between the form, the engine, the PDF
   renderer and the downloads. */
(function () {
  'use strict';
  const PYODIDE = 'https://cdn.jsdelivr.net/pyodide/v314.0.7/full/';
  const RENDERER = 'pdfmake 0.2.23 + html-to-pdfmake 2.5.34 (browser)';
  const $ = id => document.getElementById(id);
  const esc = s => String(s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
  let py = null, booting = null, last = null;

  const STEPS = [
    ['boot', 'Nạp Python và engine pv_design'],
    ['validate', 'Bước 3 · Kiểm tra dữ liệu đầu vào'],
    ['calc', 'Bước 4–6 · Cơ sở thiết kế, tính toán, verification'],
    ['gate', 'Bước 7 · Cổng xét duyệt (release gate)'],
    ['pdf', 'Bước 8 · Xuất calculation PDF'],
    ['zip', 'Đóng gói chuyển tiếp cho bước 9–12'],
  ];
  const state = {};
  function step(id, st, note) {
    state[id] = {st, note};
    $('calcSteps').innerHTML = STEPS.map(([k, t]) => {
      const s = state[k] || {st: 'wait'};
      return `<li class="s-${s.st}"><span class="dot" aria-hidden="true"></span><span>${esc(t)}</span>` +
        (s.note ? ` <span class="sn">${esc(s.note)}</span>` : '') + '</li>';
    }).join('');
  }
  const log = m => { $('calcLog').textContent = m; };

  function loadScript(src) {
    return new Promise((ok, bad) => {
      if (document.querySelector(`script[src="${src}"]`)) return ok();
      const s = document.createElement('script');
      s.src = src; s.onload = ok; s.onerror = () => bad(new Error('không tải được ' + src));
      document.head.appendChild(s);
    });
  }

  const PY_GLUE = `
import json, shutil
from pathlib import Path
from pressure_vessel import __version__
from pressure_vessel.package.pipeline import InputRejected, calculate
from pressure_vessel.reporting.calc_report import build_html
from pressure_vessel.handoff import engine_fingerprint, make_handoff

ROOT = Path('/work')

def web_calc(input_name, input_json, register_md):
    shutil.rmtree(ROOT, ignore_errors=True)
    (ROOT / 'in').mkdir(parents=True)
    inp = ROOT / 'in' / input_name
    inp.write_text(input_json, encoding='utf-8')
    pkg = ROOT / 'pkg'
    try:
        r = calculate(inp, pkg)
    except InputRejected as exc:
        return json.dumps({'rejected': str(exc), 'validation': exc.report.to_dict()}, default=str)
    (pkg / '00_INPUT' / 'source_register.md').write_text(register_md, encoding='utf-8')
    res = r['results']
    pj = res['project']
    stem = f"{pj['project_id']}_{pj['equipment_tag']}_Design_Calculation_Rev{pj['revision']}"
    shown = dict(res, _raw_process=json.loads(input_json).get('process', {}))   # as reporting.generate_report
    html = build_html(shown, r['geometry'], r['verification'])
    (pkg / '01_CALCULATION' / f'{stem}.html').write_text(html, encoding='utf-8')
    v = json.loads((pkg / '00_INPUT' / 'validation_report.json').read_text(encoding='utf-8'))
    return json.dumps({
        'stem': stem, 'html': html, 'project': pj, 'design_code': res['code']['design_code'],
        'stage': res['gate']['stage'], 'blockers': res['gate']['blockers'], 'fails': res['gate'].get('fails', []),
        'counts': res['summary']['counts'], 'mawp_MPa': res.get('mawp_MPa'),
        'verification': res['verification_summary'], 'questions': res['questions'], 'validation': v,
        'input_hash': res['input_hash'], 'results_hash': res['results_hash'],
        'header': f"{pj['project_id']} / {pj['equipment_tag']} - Design Calculation Rev {pj['revision']} - {res['gate']['stage']}",
        'footer': f"NOT FOR FABRICATION. Results {res['results_hash'][:12]}, input {res['input_hash'][:12]}",
        'records': [[x['calc_id'], x['title'], x['status']] for x in res['records']],
    }, default=str)

def web_handoff(stem, pdf_bytes, renderer):
    pkg = ROOT / 'pkg'
    data = pdf_bytes.to_bytes() if hasattr(pdf_bytes, 'to_bytes') else bytes(pdf_bytes)
    (pkg / '01_CALCULATION' / f'{stem}.pdf').write_bytes(data)
    z = ROOT / 'handoff.zip'
    h = make_handoff(pkg, z, tool='tank-vessel-design web calculator', pdf_renderer=renderer)
    return json.dumps({'files': len(h['files']), 'fingerprint': h['engine']['fingerprint']})
`;

  async function boot() {
    if (py) return py;
    if (booting) return booting;
    booting = (async () => {
      step('boot', 'run', 'đang tải Pyodide…');
      log('Đang tải Python trong trình duyệt (lần đầu mất khoảng 10–30 giây)…');
      await loadScript(PYODIDE + 'pyodide.js');
      const p = await window.loadPyodide({indexURL: PYODIDE});
      step('boot', 'run', 'đang nạp engine…');
      const eng = await (await fetch('engine.json', {cache: 'no-cache'})).json();
      for (const f of eng.files) {
        const path = '/engine/' + f.path;
        p.FS.mkdirTree(path.slice(0, path.lastIndexOf('/')));
        p.FS.writeFile(path, f.text);
      }
      p.runPython("import sys; sys.dont_write_bytecode = True; sys.path.insert(0, '/engine/src')");
      p.runPython(PY_GLUE);
      const fp = p.runPython('engine_fingerprint()');
      if (fp !== eng.fingerprint) throw new Error('engine.json bị hỏng: dấu vân tay engine không khớp');
      const ver = p.runPython('__version__');
      step('boot', 'ok', `pressure_vessel ${ver} · ${eng.files.length} file · ${fp.slice(0, 12)}`);
      py = p;
      return p;
    })();
    try { return await booting; } catch (e) { booting = null; throw e; }
  }

  /* ---- PDF: the engine's report HTML, laid out by pdfmake ---- */
  function reportDoc(r) {
    const doc = new DOMParser().parseFromString(r.html, 'text/html');
    doc.querySelectorAll('style,script,link,meta,title').forEach(n => n.remove());
    doc.querySelectorAll('[style*="page-break-before"]').forEach(n => n.setAttribute('data-pdfmake', '{"pageBreak":"before"}'));
    const content = window.htmlToPdfmake(doc.body.innerHTML, {
      tableAutoSize: true,
      defaultStyles: {h1: {fontSize: 17, bold: true, marginBottom: 6}, h2: {fontSize: 13, bold: true, marginTop: 10, marginBottom: 4},
        h3: {fontSize: 11, bold: true, marginTop: 8, marginBottom: 3}, p: {margin: [0, 2, 0, 4]},
        th: {bold: true, fillColor: '#e8eeec'}, td: {}, code: {fontSize: 7.5}, pre: {fontSize: 7.5}},
    });
    return {
      pageSize: 'A4', pageMargins: [42, 56, 42, 50],
      info: {title: r.header, author: 'pressure_vessel (automated, unreviewed)', subject: r.footer},
      defaultStyle: {fontSize: 8.5, lineHeight: 1.15},
      header: () => ({margin: [42, 24, 42, 0], stack: [{text: r.header, fontSize: 7.5},
        {canvas: [{type: 'line', x1: 0, y1: 4, x2: 511, y2: 4, lineWidth: 0.5}]}]}),
      footer: (i, n) => ({margin: [42, 6, 42, 0], stack: [{canvas: [{type: 'line', x1: 0, y1: 0, x2: 511, y2: 0, lineWidth: 0.5}]},
        {columns: [{text: r.footer, fontSize: 7}, {text: `Page ${i} of ${n}`, fontSize: 7.5, alignment: 'right', width: 70}], margin: [0, 4, 0, 0]}]}),
      content,
    };
  }
  const pdfBytes = dd => new Promise((ok, bad) => {
    try { window.pdfMake.createPdf(dd).getBuffer(b => ok(new Uint8Array(b))); } catch (e) { bad(e); }
  });

  function save(name, bytes, mime) {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([bytes], {type: mime}));
    a.download = name; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  }
  const safe = s => String(s || '').replace(/[^A-Za-z0-9_.-]+/g, '_');

  /* ---- results panel ---- */
  const BADGE = {PASS: 'ok', FAIL: 'bad', NOT_EVALUATED: 'warn', OUT_OF_SCOPE: 'mute', NEEDS_ENGINEERING_REVIEW: 'warn', COMPUTED: 'mute'};
  function list(items, cls) { return items.length ? `<ul class="${cls || ''}">${items.map(x => `<li>${esc(x)}</li>`).join('')}</ul>` : '<p class="hint">(không có)</p>'; }
  function vmsg(x) { return typeof x === 'string' ? x : `${x.field ? x.field + ': ' : ''}${x.message || JSON.stringify(x)}`; }
  function showRejected(r) {
    const v = r.validation || {};
    $('calcDetail').innerHTML = `<div class="notice demo"><b>Engine từ chối file đầu vào</b> (${(v.errors || []).length} lỗi). Sửa các mục dưới đây trong phiếu rồi tính lại.</div>` +
      `<h3>Lỗi</h3>${list((v.errors || []).map(vmsg), 'errs')}<h3>Câu hỏi</h3>${list((v.questions || []).map(vmsg))}` +
      `<h3>Cảnh báo</h3>${list((v.warnings || []).map(vmsg))}`;
  }
  function showResult(r) {
    const c = r.counts, order = ['PASS', 'FAIL', 'NEEDS_ENGINEERING_REVIEW', 'NOT_EVALUATED', 'OUT_OF_SCOPE', 'COMPUTED'];
    const v = r.verification;
    $('calcDetail').innerHTML =
      `<div class="kpis">` +
      `<div class="kpi"><span class="kl">Giai đoạn</span><b class="st-${r.stage === 'CALCULATION_VERIFIED' ? 'ok' : 'warn'}">${esc(r.stage)}</b></div>` +
      `<div class="kpi"><span class="kl">MAWP</span><b>${r.mawp_MPa == null ? '—' : esc((+r.mawp_MPa).toFixed(4)) + ' MPa(g)'}</b></div>` +
      `<div class="kpi"><span class="kl">Verification</span><b class="st-${v.passed ? 'ok' : 'bad'}">${v.passed ? 'đạt' : 'KHÔNG ĐẠT'} · ${v.n_checks - v.n_failed}/${v.n_checks}</b></div>` +
      `<div class="kpi"><span class="kl">Mã thiết kế</span><b>${esc(r.design_code)}</b></div></div>` +
      `<div class="counts">${order.filter(k => c[k] != null).map(k => `<span class="badge b-${c[k] ? BADGE[k] : 'mute'}">${esc(k)} <b>${c[k]}</b></span>`).join('')}</div>` +
      `<p class="hint">Không có kết quả nào là “đủ điều kiện chế tạo”. Giai đoạn cao nhất phần mềm có thể đạt là <code>CALCULATION_VERIFIED</code>; phát hành chế tạo cần kỹ sư có thẩm quyền xem xét và ký.</p>` +
      `<h3>Điểm chặn tại cổng xét duyệt</h3>${list(r.blockers)}` +
      (r.fails.length ? `<h3>FAIL</h3>${list(r.fails, 'errs')}` : '') +
      `<details><summary>Câu hỏi còn mở (${r.questions.length})</summary>${list(r.questions)}</details>` +
      `<details><summary>Các phép tính (${r.records.length})</summary><div class="tw"><table class="rec"><thead><tr><th>Mã</th><th>Nội dung</th><th>Trạng thái</th></tr></thead><tbody>` +
      r.records.map(([id, t, s]) => `<tr><td><code>${esc(id)}</code></td><td>${esc(t)}</td><td><span class="badge b-${BADGE[s] || 'mute'}">${esc(s)}</span></td></tr>`).join('') +
      `</tbody></table></div></details>` +
      `<div class="notice" style="margin-top:14px"><b>Làm tiếp bước 9–12 trong Claude Code:</b> tải file <code>.zip</code>, đặt vào thư mục dự án và nói với Claude: ` +
      `“dùng /tank_design làm tiếp từ file handoff này”. Claude chạy <code>python pv_design/pv.py resume &lt;file.zip&gt; --out pv_design/output/${esc(safe(r.project.project_id))}</code>, ` +
      `tính lại bằng engine cục bộ, so khớp từng kết quả rồi mới dựng mô hình FreeCAD, bản vẽ 2D, BOM và gói hồ sơ.` +
      (r.design_code === 'ASME_VIII_1' ? '' : ' Với bồn API 650, engine hiện tại chỉ làm tiếp báo cáo và gói hồ sơ; mô hình 3D, bản vẽ và BOM chưa có.') + `</div>` +
      `<p class="hint mono">input ${esc(r.input_hash.slice(0, 16))} · results ${esc(r.results_hash.slice(0, 16))}</p>`;
  }

  async function run() {
    const btn = $('bCalc');
    btn.disabled = true; $('bPdf').disabled = true; $('bZip').disabled = true;
    last = null; $('calcDetail').innerHTML = '';
    STEPS.forEach(([k]) => { if (k !== 'boot' || !py) delete state[k]; });
    try {
      const f = window.pvForm, o = f.outputs(), miss = f.missing();
      const p = await boot();
      step('validate', 'run'); log('Đang kiểm tra dữ liệu và tính toán…');
      await new Promise(r => setTimeout(r, 30));
      const name = (f.kind() === 'tank' ? 'tank_input' : 'vessel_input') + '.json';
      const r = JSON.parse(p.globals.get('web_calc')(name, o.json, o.reg));
      if (r.rejected) {
        step('validate', 'bad', `${(r.validation.errors || []).length} lỗi`);
        showRejected(r);
        log(`Engine từ chối đầu vào. ${miss.length ? `Phiếu còn thiếu ${miss.length} mục bắt buộc.` : ''}`);
        return;
      }
      const w = (r.validation.warnings || []).length, q = (r.validation.questions || []).length;
      step('validate', 'ok', `0 lỗi · ${w} cảnh báo · ${q} câu hỏi`);
      step('calc', r.verification.passed ? 'ok' : 'bad', `${r.records.length} phép tính · verification ${r.verification.n_checks - r.verification.n_failed}/${r.verification.n_checks}`);
      step('gate', r.stage === 'CALCULATION_VERIFIED' ? 'ok' : 'warn', `${r.stage} · ${r.blockers.length} điểm chặn`);
      showResult(r);
      step('pdf', 'run'); log('Đang dựng calculation PDF…');
      await new Promise(res => setTimeout(res, 30));
      const pdf = await pdfBytes(reportDoc(r));
      step('pdf', 'ok', `${Math.round(pdf.length / 1024)} kB`);
      step('zip', 'run');
      const h = JSON.parse(p.globals.get('web_handoff')(r.stem, pdf, RENDERER));
      const zip = p.FS.readFile('/work/handoff.zip');
      step('zip', 'ok', `${h.files} file + HANDOFF.json`);
      const base = `${safe(r.project.project_id)}_${safe(r.project.equipment_tag)}`;
      last = {pdf, zip, pdfName: safe(r.stem) + '.pdf', zipName: `${base}_tank-vessel-design_handoff.zip`};
      $('bPdf').disabled = false; $('bZip').disabled = false;
      log(`Xong: ${r.stage}. Tải PDF tính toán và gói chuyển tiếp bên dưới.`);
    } catch (e) {
      const k = STEPS.map(([k]) => k).find(k => state[k] && state[k].st === 'run') || 'boot';
      step(k, 'bad', 'lỗi');
      log('Lỗi: ' + (e && e.message ? e.message.split('\n').slice(-3).join(' ') : e));
      console.error(e);
    } finally { btn.disabled = false; }
  }

  step('boot', 'wait');
  $('bCalc').addEventListener('click', run);
  $('bPdf').addEventListener('click', () => last && save(last.pdfName, last.pdf, 'application/pdf'));
  $('bZip').addEventListener('click', () => last && save(last.zipName, last.zip, 'application/zip'));
})();
