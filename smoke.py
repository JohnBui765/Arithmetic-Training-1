import sys, os, re, json, glob, traceback

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8000/'
if not BASE.endswith('/'):
    BASE += '/'
HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, 'fixtures', 'v1-localstorage.json'), encoding='utf-8') as _f:
    FIXTURE = json.load(_f)

OPS = ['+', '−', '×', '÷']
MINUS = '−'
TIMES = '×'
DIV = '÷'


# ---------------------------------------------------------------- helpers
def boot(page, cfg=None, store=None, query=''):
    page.goto(BASE + query)
    page.evaluate(
        """([cfg, store]) => {
            localStorage.clear();
            if (cfg) localStorage.setItem('drill.cfg', JSON.stringify(cfg));
            for (const k of Object.keys(store || {})) localStorage.setItem(k, JSON.stringify(store[k]));
        }""", [cfg, store or {}])
    page.reload()
    page.wait_for_selector('#home.on', timeout=8000)


def tap(page, k):
    page.tap(f'#pad button[data-k="{k}"]')


def type_answer(page, value, go=True):
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    s = str(value)
    if s.startswith('-'):
        tap(page, 'neg')
        s = s[1:]
    for ch in s:
        tap(page, 'dot' if ch == '.' else ch)
    if go:
        tap(page, 'go')


def wait_ready(page):
    page.wait_for_function('window.__drill && window.__drill.ready()', timeout=5000)


def cur(page):
    return page.evaluate('window.__drill.current()')


def start(page):
    page.tap('#startBtn')
    page.wait_for_selector('#practice.on', timeout=5000)
    wait_ready(page)


def mark_qid(page):
    page.evaluate('window.__qid = window.__drill.qid()')


def wait_next(page, timeout=6000):
    page.wait_for_function(
        "(window.__drill.qid() !== window.__qid && window.__drill.ready()) || !!document.querySelector('#summary.on')",
        timeout=timeout)


def answer(page, correct=True, go=True, delta=1):
    """Answer the current question; returns the question dict."""
    q = cur(page)
    mark_qid(page)
    val = q['answer'] if correct else q['answer'] + delta
    type_answer(page, val, go=go)
    return q


def answer_and_next(page, correct=True, go=True):
    q = answer(page, correct, go)
    wait_next(page)
    return q


def state(page):
    return page.evaluate('JSON.parse(JSON.stringify(window.__drill.state()))')


def verdict_has(page, cls):
    return page.evaluate(f"document.querySelector('#verdict').classList.contains('{cls}')")


def num(x):
    return int(x) if isinstance(x, float) and x.is_integer() else x


# ---------------------------------------------------------------- runner
results = []
_browser = {}


def launch(p):
    try:
        return p.chromium.launch()
    except Exception:
        exe = os.environ.get('DRILL_CHROMIUM')
        if not exe:
            cands = sorted(glob.glob('/opt/pw-browsers/chromium-*/chrome-linux/chrome'))
            if not cands:
                raise
            exe = cands[-1]
        return p.chromium.launch(executable_path=exe)


def run(name, fn):
    errs = []
    ctxs = []
    browser = _browser['b']

    def mk(viewport=None, color_scheme=None, dsf=3, mobile=True, touch=True):
        kw = dict(viewport=viewport or {'width': 375, 'height': 812}, device_scale_factor=dsf,
                  is_mobile=mobile, has_touch=touch, timezone_id='Asia/Ho_Chi_Minh',
                  locale='en-GB', service_workers='block')
        if color_scheme:
            kw['color_scheme'] = color_scheme
        ctx = browser.new_context(**kw)
        ctxs.append(ctx)
        ctx.set_default_timeout(8000)
        page = ctx.new_page()
        page.on('pageerror', lambda e: errs.append('pageerror: ' + str(e)))
        page.on('console', lambda m: errs.append('console.error: ' + m.text) if m.type == 'error' else None)
        return page

    try:
        fn(mk)
        if errs:
            raise AssertionError('errors collected: ' + ' | '.join(errs[:3]))
        results.append((name, None))
        print('PASS ' + name, flush=True)
    except Exception:
        last = traceback.format_exc().strip().splitlines()[-1]
        results.append((name, last))
        print(f'FAIL {name}: {last}', flush=True)
    finally:
        for c in ctxs:
            try:
                c.close()
            except Exception:
                pass


# ---------------------------------------------------------------- scenarios
def t_enter_key(mk):
    page = mk()
    boot(page, {'autoSubmit': False, 'ops': [TIMES], 'shape': 'facts', 'mode': 'count', 'sound': False})
    start(page)
    go = page.locator('#pad button[data-k="go"]')
    assert go.is_visible(), 'go key not visible'
    assert go.is_enabled(), 'go key disabled'
    q = cur(page)
    type_answer(page, q['answer'], go=False)
    page.wait_for_timeout(300)
    assert not verdict_has(page, 'g'), 'submitted without pressing go'
    tap(page, 'go')
    page.wait_for_selector('#verdict.g', timeout=1500)


def t_negative_touch(mk):
    page = mk()
    boot(page, {'autoSubmit': False, 'allowNeg': True, 'ops': [MINUS], 'shape': 'facts',
                'mode': 'endless', 'noTrivial': True, 'sound': False})
    start(page)
    assert page.locator('#pad button[data-k="neg"]').is_enabled(), 'neg key disabled'
    for _ in range(40):
        q = cur(page)
        if q['answer'] < 0:
            mark_qid(page)
            type_answer(page, q['answer'])
            page.wait_for_selector('#verdict.g', timeout=1500)
            return
        answer_and_next(page)
    raise AssertionError('no negative-answer question within 40')


def t_decimal_touch(mk):
    page = mk()
    sets = [{'name': 'Halves', 'raw': '7 / 2', 'items': [{'prompt': '7 ÷ 2 =', 'answer': 3.5, 'key': '7÷2'}]}]
    boot(page, {'sound': False}, {'drill.sets': sets})
    page.tap('#toSets')
    page.tap('[data-play="0"]')
    page.wait_for_selector('#practice.on')
    wait_ready(page)
    assert page.locator('#pad button[data-k="dot"]').is_enabled(), 'dot key disabled'
    type_answer(page, 3.5)
    page.wait_for_selector('#verdict.g', timeout=1500)


def t_local_date(mk):
    page = mk()
    page.clock.set_fixed_time('2026-10-14T23:30:00Z')
    boot(page, {'sound': False})
    t = page.evaluate('window.__drill.today()')
    assert t == '2026-10-15', f'today() = {t}'


def t_streak_midnight(mk):
    page = mk()
    page.clock.set_fixed_time('2026-10-14T16:30:00Z')
    boot(page, {'mode': 'endless', 'ops': ['+'], 'shape': 'facts', 'sound': False})
    start(page)
    answer_and_next(page, go=False)
    page.tap('#quitBtn')
    page.wait_for_selector('#summary.on')
    page.clock.set_fixed_time('2026-10-14T17:30:00Z')
    page.tap('#sumDone')
    page.wait_for_selector('#home.on')
    start(page)
    answer_and_next(page, go=False)
    page.tap('#quitBtn')
    page.wait_for_selector('#summary.on')
    st = state(page)['streak']
    assert st == {'last': '2026-10-15', 'n': 2}, f'streak = {st}'


def t_session_limit(mk):
    page = mk()
    boot(page, {'mode': 'count', 'count': 20, 'ops': ['+'], 'shape': 'facts',
                'autoSubmit': False, 'repeat': True, 'sound': False})
    start(page)
    for i in range(20):
        answer(page, correct=(i < 18))
        wait_next(page, timeout=8000)
        info = page.evaluate("""() => {
            const pb = document.querySelector('#progBar'), tm = document.querySelector('#timer');
            const m = pb ? /scaleX\\(([\\d.]+)\\)/.exec(pb.style.transform) : null;
            return {w: m ? (parseFloat(m[1]) * 100) + '%' : null, t: tm ? tm.textContent : null,
                    sum: !!document.querySelector('#summary.on')};
        }""")
        if info['w'] is not None and info['w'] != '':
            assert float(info['w'].replace('%', '')) <= 100.0001, f"progBar {info['w']} after answer {i + 1}"
        if info['t']:
            m = re.match(r'\s*(\d+)\s*/', info['t'])
            if m:
                assert int(m.group(1)) <= 20, f"timer {info['t']!r} after answer {i + 1}"
    page.wait_for_selector('#summary.on', timeout=5000)
    sc = re.sub(r'\s+', ' ', page.inner_text('#sumScore')).strip()
    assert sc == '18 / 20', f'sumScore {sc!r}'
    mc = page.inner_text('#mCount').strip()
    assert mc == '20', f'mCount {mc!r}'


def t_input_lock(mk):
    page = mk()
    boot(page, {'autoSubmit': False, 'ops': ['+'], 'shape': 'facts', 'mode': 'endless', 'sound': False})
    start(page)
    q = cur(page)
    mark_qid(page)
    type_answer(page, q['answer'])
    tap(page, '7')
    tap(page, '7')
    wait_next(page)
    t = page.evaluate('window.__drill.typed()')
    assert t == '', f'typed() = {t!r} after lock'


def t_fastest_correct_only(mk):
    page = mk()
    boot(page, {'autoSubmit': False, 'ops': ['+'], 'shape': 'facts', 'mode': 'endless', 'sound': False})
    start(page)
    answer_and_next(page, correct=False)
    page.wait_for_timeout(1300)
    answer_and_next(page, correct=True)
    page.tap('#quitBtn')
    page.wait_for_selector('#summary.on')
    txt = page.inner_text('#mBest')
    m = re.search(r'\d+(\.\d+)?', txt)
    assert m, f'mBest {txt!r} not numeric'
    assert float(m.group(0)) >= 1.0, f'mBest {txt!r} < 1.0 (wrong answer counted?)'


def t_show_length(mk):
    page = mk()
    boot(page, {'ops': [TIMES], 'shape': 'facts', 'showLen': True, 'sound': False})
    start(page)
    q = cur(page)
    n = page.locator('#aText .ph').count()
    assert n == len(str(num(q['answer']))), f'showLen true: {n} placeholders for answer {q["answer"]}'
    page2 = mk()
    boot(page2, {'ops': [TIMES], 'shape': 'facts', 'showLen': False, 'sound': False})
    start(page2)
    n2 = page2.locator('#aText .ph').count()
    assert n2 == 0, f'showLen false: {n2} placeholders'


def t_single_tap(mk):
    page = mk()
    boot(page, {'autoSubmit': False, 'ops': [TIMES], 'shape': 'facts', 'sound': False})
    start(page)
    tap(page, '5')
    t = page.evaluate('window.__drill.typed()')
    assert t == '5', f'typed() = {t!r} after one tap'
    tap(page, 'del')
    t = page.evaluate('window.__drill.typed()')
    assert t == '', f'typed() = {t!r} after del'


def t_haptics(mk):
    page = mk()
    boot(page, {'autoSubmit': False, 'haptics': True, 'sound': False})
    page.wait_for_selector('#hapt input[type=checkbox][switch]', state='attached')
    start(page)
    n0 = page.evaluate('window.__drill.hapticCount()')
    tap(page, '3')
    n1 = page.evaluate('window.__drill.hapticCount()')
    assert n1 == n0 + 1, f'hapticCount {n0} -> {n1}'
    page2 = mk()
    boot(page2, {'autoSubmit': False, 'haptics': False, 'sound': False})
    start(page2)
    m0 = page2.evaluate('window.__drill.hapticCount()')
    tap(page2, '3')
    m1 = page2.evaluate('window.__drill.hapticCount()')
    assert m1 == m0, f'haptics off but hapticCount {m0} -> {m1}'


def t_lefty(mk):
    page = mk()
    boot(page, {'lefty': True, 'sound': False})
    start(page)
    assert 'lefty' in (page.get_attribute('#pad', 'class') or ''), '#pad lacks lefty class'
    go = page.locator('#pad button[data-k="go"]').bounding_box()
    one = page.locator('#pad button[data-k="1"]').bounding_box()
    assert go['x'] < one['x'], f"lefty: go x {go['x']} not < key1 x {one['x']}"
    page2 = mk()
    boot(page2, {'lefty': False, 'sound': False})
    start(page2)
    go = page2.locator('#pad button[data-k="go"]').bounding_box()
    three = page2.locator('#pad button[data-k="3"]').bounding_box()
    assert go['x'] > three['x'], f"righty: go x {go['x']} not > key3 x {three['x']}"


def shape_fits(shape, q, mn=20, mx=30):
    d = q['data']
    op = d['op']
    if op == DIV:
        x, y = d['b'], num(q['answer'])
    else:
        x, y = d['a'], d['b']
    lo, hi = min(x, y), max(x, y)
    rng = lambda v, a, b: a <= v <= b
    if shape == 'facts':
        return rng(x, 2, 12) and rng(y, 2, 12)
    if shape == 'teens':
        return rng(hi, 11, 19) and rng(lo, 2, 19)
    if shape == 'd21':
        return (rng(x, 10, 99) and rng(y, 2, 9)) or (rng(y, 10, 99) and rng(x, 2, 9))
    if shape == 'd22':
        return rng(x, 10, 99) and rng(y, 10, 99)
    if shape == 'd31':
        return (rng(x, 100, 999) and rng(y, 2, 9)) or (rng(y, 100, 999) and rng(x, 2, 9))
    if shape == 'd33':
        return rng(x, 100, 999) and rng(y, 100, 999)
    if shape == 'squares':
        return op == TIMES and d['a'] == d['b'] and rng(d['a'], 11, 99) and '²' in q['prompt']
    if shape == 'custom':
        return rng(x, mn, mx) and rng(y, mn, mx)
    return False


def t_shapes(mk):
    bad = []
    for shape in ['facts', 'teens', 'd21', 'd22', 'd31', 'd33', 'squares', 'custom']:
        page = mk()
        cfg = {'ops': OPS, 'shape': shape, 'mode': 'endless', 'autoSubmit': False,
               'allowNeg': False, 'sound': False}
        if shape == 'custom':
            cfg['min'] = 20
            cfg['max'] = 30
        boot(page, cfg, query='?seed=11')
        start(page)
        for i in range(12):
            q = cur(page)
            ok = shape_fits(shape, q)
            if ok and q['data']['op'] == MINUS and q['answer'] < 0:
                ok = False
            if not ok:
                bad.append(f"{shape}: {q['prompt']} data={q['data']} ans={q['answer']}")
                break
            answer_and_next(page)
    if bad:
        raise AssertionError('shape violations; first: ' + bad[0] + (f' (+{len(bad) - 1} more shapes)' if len(bad) > 1 else ''))


def t_seeded(mk):
    runs = []
    for _ in range(2):
        page = mk()
        boot(page, {'ops': [TIMES], 'shape': 'd22', 'mode': 'endless', 'autoSubmit': False, 'sound': False},
             query='?seed=5')
        start(page)
        prompts = []
        for _i in range(5):
            q = answer_and_next(page)
            prompts.append(q['prompt'])
        runs.append(prompts)
    assert runs[0] == runs[1], f'seed=5 sequences differ: {runs[0]} vs {runs[1]}'


def t_srs_rules(mk):
    page = mk()
    page.clock.set_fixed_time('2026-10-15T03:00:00Z')
    boot(page, {'sound': False})
    steps = [
        ((False, 900, 2500), [0, '2026-10-15']),
        ((True, 900, 2500), [1, '2026-10-16']),
        ((True, 900, 2500), [2, '2026-10-18']),
        ((True, 9000, 2500), [2, '2026-10-18']),
        ((True, 900, 2500), [3, '2026-10-22']),
        ((True, 900, 2500), [4, '2026-11-05']),
        ((True, 900, 2500), [5, '2026-10-15']),
    ]
    for i, (args, want) in enumerate(steps):
        got = page.evaluate('([k,o,m,t]) => window.__drill.srsUpdate(k,o,m,t)', ['7' + TIMES + '8', *args])
        assert list(got) == want, f'step {i + 1} {args}: got {got}, want {want}'


def t_srs_seed_v1(mk):
    page = mk()
    page.clock.set_fixed_time('2026-10-15T03:00:00Z')
    store = {k: v for k, v in FIXTURE.items() if k != 'drill.srs'}
    boot(page, None, store)
    s = state(page)
    for key, f in FIXTURE['drill.facts'].items():
        want = [0, '2026-10-15'] if f['ok'] / f['n'] < 0.8 else [2, '2026-10-18']
        got = s['srs'].get(key)
        assert got == want, f'srs[{key}] = {got}, want {want}'
    assert s['sets'] == FIXTURE['drill.sets'], 'sets changed'
    assert s['history'] == FIXTURE['drill.history'], 'history changed'
    assert s['streak'] == FIXTURE['drill.streak'], 'streak changed'
    assert s['facts'] == FIXTURE['drill.facts'], 'facts changed'
    meta = page.evaluate("localStorage.getItem('drill.meta')")
    assert meta is None, f'drill.meta written: {meta}'


def t_srs_due_first(mk):
    page = mk()
    page.clock.set_fixed_time('2026-10-15T03:00:00Z')
    boot(page, {'ops': [TIMES], 'shape': 'facts', 'sound': False},
         {'drill.srs': {'7' + TIMES + '8': [0, '2026-10-14'], '2' + TIMES + '3': [1, '2026-10-20']}})
    start(page)
    k = cur(page)['key']
    assert k == '7' + TIMES + '8', f'first key {k!r}'


def t_srs_miss(mk):
    page = mk()
    boot(page, {'ops': [TIMES], 'shape': 'facts', 'autoSubmit': False, 'sound': False})
    start(page)
    q = answer(page, correct=False)
    page.wait_for_selector('#verdict.b', timeout=2000)
    e = state(page)['srs'].get(q['key'])
    assert e is not None and e[0] == 0, f'srs[{q["key"]}] = {e}'


def t_import_v1(mk):
    page = mk()
    boot(page, {'sound': False})
    page.tap('#toStats')
    page.wait_for_selector('#stats.on')
    backup = {'v': 1, 'cfg': FIXTURE['drill.cfg'], 'facts': FIXTURE['drill.facts'],
              'history': FIXTURE['drill.history'], 'sets': FIXTURE['drill.sets'],
              'streak': FIXTURE['drill.streak']}
    text = json.dumps(backup, ensure_ascii=False)

    def on_dialog(d):
        if d.type == 'prompt':
            d.accept(text)
        else:
            d.accept()
    page.on('dialog', on_dialog)
    page.tap('#importBtn')
    n = len(FIXTURE['drill.facts'])
    page.wait_for_function(
        f"window.__drill && Object.keys(window.__drill.state().srs).length >= {n}", timeout=5000)
    s = state(page)
    assert s['sets'] == FIXTURE['drill.sets'], 'imported sets differ'
    missing = [k for k in FIXTURE['drill.facts'] if k not in s['srs']]
    assert not missing, f'srs missing for {missing}'
    assert len(s['srs']) == n, f'srs has {len(s["srs"])} entries, want {n}'


def t_sw(mk):
    page = mk()
    r = page.context.request.get(BASE + 'sw.js')
    assert r.ok, f'sw.js status {r.status}'
    t = r.text()
    assert "CACHE = 'drill-v5'" in t, "sw.js lacks CACHE = 'drill-v5'"
    assert "cache: 'reload'" in t, "sw.js lacks cache: 'reload'"
    assert "k.startsWith('drill-')" in t, "sw.js would delete other apps' caches on the same site"


def t_negatives(mk):
    page = mk()
    boot(page, {'autoSubmit': False, 'signed': True, 'ops': ['+', MINUS, '×', '÷'], 'shape': 'facts',
                'mode': 'endless', 'sound': False}, query='?seed=21')
    assert page.locator('#signChip[aria-pressed="true"]').count() == 1, 'sign chip not pressed'
    start(page)
    assert page.locator('#pad button[data-k="neg"]').is_enabled(), 'neg key disabled'
    calc = {'+': lambda a, b: a + b, MINUS: lambda a, b: a - b, '×': lambda a, b: a * b, '÷': lambda a, b: a / b}
    with_neg = 0
    for _ in range(16):
        q = cur(page)
        d = q['data']
        a, b = d['a'], d['b']
        assert num(calc[d['op']](a, b)) == num(q['answer']), f'wrong answer for {q}'
        assert float(q['answer']).is_integer(), f'answer not whole: {q}'
        if b < 0:
            assert '(−' in q['prompt'], f'negative second number not bracketed: {q["prompt"]}'
        with_neg += a < 0 or b < 0
        mark_qid(page)
        type_answer(page, q['answer'])
        page.wait_for_selector('#verdict.g', timeout=1500)
        wait_next(page)
    assert with_neg >= 8, f'only {with_neg}/16 questions had a negative number'
    # auto-submit must not give the sign away: the digits alone submit, and without the sign that is wrong
    page2 = mk()
    boot(page2, {'autoSubmit': True, 'signed': True, 'ops': ['×'], 'shape': 'facts', 'mode': 'endless',
                 'sound': False}, query='?seed=4')
    start(page2)
    for _ in range(30):
        q = cur(page2)
        if q['answer'] < 0:
            mark_qid(page2)
            type_answer(page2, -q['answer'], go=False)
            page2.wait_for_selector('#verdict.b', timeout=1500)
            return
        answer_and_next(page2)
    raise AssertionError('no negative answer within 30 questions')


def t_layout(mk):
    for vw, vh in [(320, 568), (375, 812)]:
        for scheme in ['light', 'dark']:
            tag = f'{vw}x{vh}/{scheme}'
            page = mk(viewport={'width': vw, 'height': vh}, color_scheme=scheme)
            boot(page, {'ops': [TIMES], 'shape': 'd33', 'sound': False})
            sw_ = page.evaluate('[document.documentElement.scrollWidth, innerWidth]')
            assert sw_[0] <= sw_[1], f'{tag} home overflow {sw_}'
            b = page.locator('#startBtn').bounding_box()
            assert b['y'] + b['height'] <= vh + 0.5, f'{tag} startBtn bottom {b["y"] + b["height"]} > {vh}'
            start(page)
            sw_ = page.evaluate('[document.documentElement.scrollWidth, innerWidth]')
            assert sw_[0] <= sw_[1], f'{tag} practice overflow {sw_}'
            bad = page.evaluate("""(vh) => {
                const out = [];
                document.querySelectorAll('#pad button').forEach(b => {
                    const r = b.getBoundingClientRect();
                    if (r.width === 0 || r.height === 0 || getComputedStyle(b).visibility === 'hidden') return;
                    if (r.height < 43.99) out.push(b.dataset.k + ' h=' + r.height);
                    if (r.bottom > vh + 0.5) out.push(b.dataset.k + ' bottom=' + r.bottom);
                });
                const q = document.querySelector('#qText');
                if (q && q.scrollWidth > q.parentElement.clientWidth + 1)
                    out.push('qText scrollWidth ' + q.scrollWidth + ' > parent ' + q.parentElement.clientWidth);
                return out;
            }""", vh)
            assert not bad, f'{tag}: ' + '; '.join(bad[:4])


def t_screenshot(mk):
    page = mk(viewport={'width': 790, 'height': 812}, color_scheme='light', dsf=2, mobile=False, touch=False)
    page.goto(BASE)
    page.evaluate("""() => {
        localStorage.clear();
        localStorage.setItem('drill.cfg', JSON.stringify({ops: ['\\u00d7'], shape: 'd22', signed: true, mode: 'count', autoSubmit: true, sound: false}));
        localStorage.setItem('drill.streak', JSON.stringify({last: null, n: 0}));
    }""")
    src = BASE + '?seed=3'
    page.set_content(
        '<!doctype html><html><head><link rel="icon" href="data:,"><style>html,body{margin:0;padding:0;background:#fff}'
        'body{display:flex;gap:40px;width:790px;height:812px}'
        'iframe{width:375px;height:812px;border:0;flex:none}</style></head><body>'
        f'<iframe id="f1" src="{src}"></iframe><iframe id="f2" src="{src}"></iframe></body></html>')
    frames = []
    for fid in ('f1', 'f2'):
        h = page.wait_for_selector('#' + fid)
        fr = h.content_frame()
        fr.wait_for_selector('#home.on', timeout=8000)
        frames.append(fr)
    frames[1].evaluate("document.querySelector('#startBtn').click()")
    page.wait_for_timeout(400)
    # show the wrong-answer feedback: tap a first digit that cannot lead to the answer
    frames[1].evaluate("""() => {
        const q = window.__drill.current(), want = (q.answer < 0 ? '-' : '') + Math.abs(q.answer);
        const k = ['1', '2'].find(d => d !== want[0]);
        document.querySelector('#pad button[data-k="' + k + '"]')
            .dispatchEvent(new PointerEvent('pointerdown', {bubbles: true, pointerType: 'touch', isPrimary: true}));
    }""")
    page.wait_for_timeout(250)
    out = os.path.join(HERE, 'shots')
    os.makedirs(out, exist_ok=True)
    page.screenshot(path=os.path.join(out, 'iphone-xs.png'))


# ---------------------------------------------------------------- judge-as-you-type checks
def find_q(page, pred, go=False, limit=40, what='suitable'):
    """Answer questions correctly until pred(current) holds; returns that question."""
    for _ in range(limit):
        q = cur(page)
        if pred(q):
            return q
        answer_and_next(page, go=go)
    raise AssertionError(f'no {what} question within {limit}')


def other_digit(d):
    return '9' if d != '9' else '8'


def arm_seen(page):
    """Record every class #verdict / #aText take (correct verdicts may be very short-lived)."""
    page.evaluate("""() => {
        window.__seen = [];
        const rec = () => {
            const v = document.querySelector('#verdict'), a = document.querySelector('#aText');
            window.__seen.push({v: v ? [...v.classList] : [], a: a ? [...a.classList] : [], t: performance.now()});
        };
        if (window.__seenObs) window.__seenObs.disconnect();
        window.__seenObs = new MutationObserver(rec);
        window.__seenObs.observe(document.documentElement,
            {subtree: true, childList: true, attributes: true, attributeFilter: ['class']});
        rec();
    }""")


def wait_seen(page, el, cls, timeout=1500):
    page.wait_for_function(
        "([el, cls]) => (window.__seen || []).some(s => s[el].includes(cls))", arg=[el, cls], timeout=timeout)


def ever_seen(page, el, cls):
    return page.evaluate("([el, cls]) => (window.__seen || []).some(s => s[el].includes(cls))", [el, cls])


def go_text(page):
    return page.inner_text('#pad button[data-k="go"]').strip()


def t_fail_fast_positive(mk):
    page = mk()
    boot(page, {'autoSubmit': True, 'ops': ['+'], 'shape': 'facts', 'mode': 'endless', 'sound': False},
         query='?seed=31')
    start(page)
    q = find_q(page, lambda q: num(q['answer']) >= 10, what='answer >= 10')
    mark_qid(page)
    tap(page, other_digit(str(num(q['answer']))[0]))
    page.wait_for_selector('#verdict.b', timeout=1000)
    assert page.locator('#aText.bad').count() == 1, '#aText lacks class bad'


def t_fail_fast_negative(mk):
    page = mk()
    boot(page, {'autoSubmit': True, 'signed': True, 'ops': [MINUS], 'shape': 'facts', 'mode': 'endless',
                'sound': False}, query='?seed=32')
    start(page)
    q = find_q(page, lambda q: num(q['answer']) <= -10, what='answer <= -10')
    s = str(abs(num(q['answer'])))
    mark_qid(page)
    arm_seen(page)
    tap(page, 'neg')
    tap(page, s[0])
    page.wait_for_timeout(400)
    assert not ever_seen(page, 'v', 'b') and not ever_seen(page, 'v', 'g'), f'judged early on -{s[0]} (answer {q["answer"]})'
    assert page.evaluate('window.__drill.ready()'), 'not ready after -' + s[0]
    t = page.evaluate('window.__drill.typed()')
    assert t == s[0], f'typed() = {t!r}, want {s[0]!r}'
    tap(page, other_digit(s[1]))
    page.wait_for_selector('#verdict.b', timeout=1000)
    wait_next(page)
    q = find_q(page, lambda q: num(q['answer']) < 0, what='second negative-answer')
    mark_qid(page)
    arm_seen(page)
    type_answer(page, num(q['answer']), go=False)
    wait_seen(page, 'v', 'g')


def t_sign_first(mk):
    page = mk()
    boot(page, {'autoSubmit': True, 'signed': True, 'ops': [MINUS], 'shape': 'facts', 'mode': 'endless',
                'sound': False}, query='?seed=33')
    start(page)
    q = find_q(page, lambda q: num(q['answer']) < 0, what='negative-answer')
    mark_qid(page)
    tap(page, str(abs(num(q['answer'])))[0])
    page.wait_for_selector('#verdict.b', timeout=1000)
    wait_next(page)
    q = find_q(page, lambda q: num(q['answer']) > 0, what='positive-answer')
    mark_qid(page)
    tap(page, 'neg')
    page.wait_for_selector('#verdict.b', timeout=1000)
    wait_next(page)
    page.tap('#quitBtn')
    page.wait_for_selector('#summary.on')
    was = page.evaluate("[...document.querySelectorAll('#missList .was')].map(e => e.textContent)")
    assert any('you put −' in w for w in was), f'miss texts {was}'


def t_wrong_feedback(mk):
    page = mk()
    boot(page, {'autoSubmit': False, 'ops': ['×'], 'shape': 'facts', 'mode': 'endless', 'sound': False},
         query='?seed=34')
    start(page)
    q = cur(page)
    a = num(q['answer'])
    type_answer(page, a + 1)
    page.wait_for_selector('#verdict.b', timeout=1500)
    tv = page.evaluate('performance.now()')
    assert page.locator('#aText.bad').count() == 1, '#aText lacks class bad'
    vt = page.inner_text('#verdict').strip()
    assert vt == str(a), f'verdict text {vt!r}, want {str(a)!r}'
    assert go_text(page) == 'Next', f'go key text {go_text(page)!r}'
    page.wait_for_timeout(500)
    mark_qid(page)
    tap(page, 'go')
    wait_next(page, timeout=600)
    t1 = page.evaluate('performance.now()')
    assert t1 - tv < 1100, f'next question {t1 - tv:.0f} ms after verdict (Next key ignored?)'
    assert go_text(page) == '↵', f'go key text {go_text(page)!r} on next question'
    cls = page.get_attribute('#aText', 'class') or ''
    assert 'bad' not in cls.split() and 'ok' not in cls.split(), f'#aText class {cls!r}'


def t_fast_pace(mk):
    page = mk()
    boot(page, {'autoSubmit': True, 'ops': ['×'], 'shape': 'facts', 'mode': 'endless', 'sound': False},
         query='?seed=35')
    start(page)
    for i in range(3):
        s = str(num(cur(page)['answer']))
        mark_qid(page)
        for ch in s[:-1]:
            tap(page, ch)
        t0 = page.evaluate('performance.now()')
        tap(page, s[-1])
        wait_next(page)
        t1 = page.evaluate('performance.now()')
        assert t1 - t0 < 450, f'question {i + 1}: next after {t1 - t0:.0f} ms'


def t_review_tag(mk):
    page = mk()
    boot(page, {'ops': ['×'], 'shape': 'facts', 'autoSubmit': False, 'mode': 'endless', 'sound': False},
         {'drill.srs': {'7×8': [0, '2000-01-01']}})
    start(page)
    k = cur(page)['key']
    assert k == '7×8', f'first key {k!r}'
    tag = (page.text_content('#qTag') or '').strip()
    assert tag == 'Review', f'qTag {tag!r} on due item'
    answer_and_next(page)
    tag = (page.text_content('#qTag') or '').strip()
    assert tag == '', f'qTag {tag!r} on generated question'


def t_summary_srs(mk):
    page = mk()
    boot(page, {'autoSubmit': False, 'ops': ['+'], 'shape': 'facts', 'mode': 'count', 'count': 20,
                'sound': False})
    start(page)
    q1 = answer_and_next(page, correct=False)
    assert cur(page)['key'] != q1['key'], 'missed fact re-asked immediately'
    answer_and_next(page)
    page.tap('#quitBtn')
    page.wait_for_selector('#summary.on')
    t = re.sub(r'\s+', ' ', page.inner_text('#sumSrs')).strip()
    assert re.match(r'^\d+ facts? back to review · \d+ due tomorrow$', t), f'sumSrs {t!r}'
    assert t.startswith('1 fact back to review'), f'sumSrs {t!r}'


def t_no_pinch(mk):
    page = mk()
    boot(page, {'sound': False})
    start(page)
    ta = page.evaluate("""() => [getComputedStyle(document.querySelector('#pad')).touchAction,
        getComputedStyle(document.querySelector('#practice .body')).touchAction]""")
    assert ta == ['none', 'none'], f'touch-action #pad/#practice .body = {ta}'


def t_neg_placeholders(mk):
    page = mk()
    boot(page, {'signed': True, 'showLen': True, 'autoSubmit': True, 'ops': ['×'], 'shape': 'facts',
                'mode': 'endless', 'sound': False}, query='?seed=36')
    start(page)
    q = find_q(page, lambda q: num(q['answer']) < 0, what='negative-answer')
    n = page.locator('#aText .ph').count()
    want = len(str(abs(num(q['answer']))))
    assert n == want, f'{n} placeholders for answer {q["answer"]}, want {want}'


CHECKS = [
    ('enter-key', t_enter_key), ('negative-touch', t_negative_touch), ('decimal-touch', t_decimal_touch),
    ('local-date', t_local_date), ('streak-midnight', t_streak_midnight), ('session-limit', t_session_limit),
    ('input-lock', t_input_lock), ('fastest-correct-only', t_fastest_correct_only),
    ('show-length', t_show_length), ('single-tap', t_single_tap), ('haptics', t_haptics),
    ('lefty', t_lefty), ('shapes', t_shapes), ('seeded', t_seeded), ('srs-rules', t_srs_rules),
    ('srs-seed-v1', t_srs_seed_v1), ('srs-due-first', t_srs_due_first), ('srs-miss', t_srs_miss),
    ('import-v1', t_import_v1), ('negatives', t_negatives),
    ('fail-fast-positive', t_fail_fast_positive), ('fail-fast-negative', t_fail_fast_negative),
    ('sign-first', t_sign_first), ('wrong-feedback', t_wrong_feedback), ('fast-pace', t_fast_pace),
    ('review-tag', t_review_tag), ('summary-srs', t_summary_srs), ('no-pinch', t_no_pinch),
    ('neg-placeholders', t_neg_placeholders), ('sw', t_sw), ('layout', t_layout), ('screenshot', t_screenshot),
]


def main():
    with sync_playwright() as p:
        _browser['b'] = launch(p)
        try:
            for name, fn in CHECKS:
                run(name, fn)
        finally:
            _browser['b'].close()
    failed = sum(1 for _, e in results if e)
    print(f'{len(results) - failed} passed, {failed} failed')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
