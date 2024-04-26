from flask import Blueprint, request
import os
from collections import defaultdict
import unicodedata
import math

app = Blueprint('scrabble', __name__,
                static_folder=os.path.join(os.path.dirname(__file__), 'static'))

def tokenize_str(s_, digraphs):
    if not digraphs:
        yield from s_.upper()
    else:
        i = 0
        s = s_.upper()
        while i < len(s):
            for d in digraphs:
                if s[i:i+len(d)] == d:
                    yield d
                    i += len(d)
                    break
            else:
                yield s[i]
                i += 1

def tokenize(s, digraphs):
    if isinstance(s, str):
        yield from tokenize_str(s, digraphs)
    elif isinstance(s, list):
        for p in s:
            if isinstance(p, str):
                yield from tokenize_str(p, digraphs)
            elif isinstance(p, tuple):
                w, freq = p
                for i in range(min(freq, 1)):
                    yield from tokenize_str(w, digraphs)

def count(s, digraphs, lim=0.0005):
    dct = defaultdict(lambda: 0)
    N = 0
    dls = digraphs.upper().split()
    dls.sort(key=len, reverse=True)
    for c in tokenize(s, dls):
        if c in dls or unicodedata.category(c)[0] == 'L':
            dct[c] += 1
            N += 1
    ret = {}
    for c in dct:
        d = dct[c] / N
        if d >= lim:
            ret[c] = d
    return ret, dct

def optimize_count(text_dist, N=98):
    rem = N - len(text_dist)
    tile_dist = {c:1 for c in text_dist}
    while rem > 0:
        mc = None
        md = 0.0
        for ch in tile_dist:
            ct = tile_dist[ch]
            rc = text_dist[ch]
            d = abs((ct / N) - rc) - abs(((ct + 1) / N) - rc)
            if not mc or d > md:
                mc = ch
                md = d
        tile_dist[mc] += 1
        rem -= 1
    return tile_dist

def optimize_score(tile_count, text_dist, N=98, BUCKET_COUNT=12):
    score_dist = {ch: [ct, 1] for ch, ct in tile_count.items()}
    mxf = max(text_dist.values())
    mnf = min(text_dist.values())
    w = math.log(mxf - mnf) / math.sqrt(BUCKET_COUNT)
    for l, f in text_dist.items():
        bk = max(0, min(int((math.log(f) - math.log(mxf)) / w), BUCKET_COUNT)-1)
        score_dist[l][1] += bk
    score_dist['[blank]'] = [2,0]
    return score_dist

def table(score_dist, frac_freq, abs_freq):
    ret = ['<html><head></head><body><table border=1>']
    t = []
    for i in range(max(x[1] for x in score_dist.values()) + 2):
        l = []
        for j in range(max(x[0] for x in score_dist.values())+1):
            l.append([])
        t.append(l)
    for i in range(len(t)-1):
        t[i+1][0].append(str(i))
    for i in range(len(t[0])-1):
        t[0][i+1].append('×' + str(i+1))
    cols = [0]
    rows = [0]
    for ch, (ct, sc) in score_dist.items():
        t[sc+1][ct].append(ch)
        cols.append(ct)
        rows.append(sc+1)
    cols = sorted(set(cols))
    rows = sorted(set(rows))
    col_w = [0]*len(cols)
    for i, c in enumerate(cols):
        for r in rows:
            col_w[i] = max(col_w[i], len(' '.join(t[r][c])))
    for r in rows:
        l = []
        for c, w in zip(cols, col_w):
            s = ' '.join(sorted(t[r][c]))
            l.append('<td>' + s + '</td>')
        ret.append('<tr>' + '   '.join(l) + '</tr>')
    ret.append('</table>')
    ret.append('<h3>Letter Frequency</h3>')
    ret.append('<ul>')
    for c, p in sorted(frac_freq.items()):
        ret.append('<li>'+c+' '+str(abs_freq[c])+' ('+str(round(p*100, 2))+'%)</li>')
    ret.append('</ul>')
    ret.append('</body></html>')
    return '\n'.join(ret)

def scrabble_readfile(fin, mode):
    if mode == 'txt':
        return fin.read().decode('utf-8')
    elif mode == 'flextsv':
        lns = fin.read().decode('utf-8').splitlines()
        if len(lns) < 2:
            return ''
        cols = lns[0].split('\t')
        widx = cols.index('Wordforms')
        fidx = cols.index('NumberInCorpus')
        ret = []
        for ln in lns[1:]:
            ls = ln.split('\t')
            ret.append((ls[widx], int(ls[fidx])))
        return ret
    elif mode == 'database':
        lns = fin.read().decode('utf-8').splitlines()
        ret = []
        for ln in lns:
            if ln.startswith('\\lx '):
                ret.append(ln[4:].strip())
        return ' '.join(ret)
    return ''

@app.route('/', methods=['GET', 'POST'])
def scrabble():
    if request.method == 'POST':
        for fname in request.files:
            txt = scrabble_readfile(request.files[fname], request.form['filetype'])
            d, letter_counts = count(txt, request.form['digraphs'])
            tiles = int(request.form['tiles'])
            buckets = int(request.form['buckets'])
            t = optimize_count(d, tiles-2)
            s = optimize_score(t, d, tiles-2, buckets)
            return table(s, d, letter_counts)
    return app.send_static_file('index.html')
