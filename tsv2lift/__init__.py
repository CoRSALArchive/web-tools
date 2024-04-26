from flask import Blueprint, request
import csv
from xml.sax.saxutils import escape as xml_escape
from collections import defaultdict
import os

app = Blueprint('tsv2lift', __name__,
                static_folder=os.path.join(os.path.dirname(__file__), 'static'))

def t(x):
    return f'<text>{xml_escape(x)}</text>'

def line(n, t1, t2, lg, v):
    return '  '*n + f'<{t1}><{t2} lang="{lg}">{t(v)}</{t2}></{t1}>\n'

class Entry:
    def __init__(self, eid):
        self.eid = eid
        self.fields = defaultdict(list)
        self.senses = []
        self.notes = []
    def generate(self, vlang, alang):
        ret = f'  <entry id="e{self.eid}">\n'
        for f, v in self.fields.items():
            for k in v:
                if f == 'form':
                    ret += line(2, 'lexical-unit', 'form', vlang, k)
                    break
                elif f == 'cite':
                    ret += line(2, 'citation', 'form', vlang, k)
                    break
                elif f == 'phon':
                    ret += line(2, 'pronunciation', 'form', vlang, k)
                elif f == 'var':
                    ret += line(2, 'variant', 'form', vlang, k)
        for s in self.senses:
            ret += s.generate(vlang, alang)
        for n in self.notes:
            ret += line(2, 'note', 'form', alang, n)
        ret += '  </entry>\n'
        return ret

class Sense:
    def __init__(self, eid):
        self.eid = eid
        self.fields = defaultdict(list)
        self.examples = []
        self.notes = []
    def generate(self, vlang, alang):
        ret = f'    <sense id="s{self.eid}">\n'
        for f, v in self.fields.items():
            for k in v:
                if f == 'gloss':
                    ret += f'      <gloss lang="{alang}">{t(k)}</gloss>\n'
                    break
                elif f == 'def':
                    ret += line(3, 'definition', 'form', alang, k)
                    break
                elif f == 'pos':
                    ret += f'      <grammatical-info value="{k}"></grammatical-info>\n'
                    break
        for src, tgt in self.examples:
            ret += '      <example>\n'
            ret += f'        <form lang="{vlang}">{t(src)}</form>\n'
            ret += line(4, 'translation', 'form', alang, tgt)
            ret += '      </example>\n'
        for n in self.notes:
            ret += line(3, 'note', 'form', alang, n)
        ret += '    </sense>\n'
        return ret

ENTRY_FIELDS = ['form', 'cite', 'phon', 'var']
SENSE_FIELDS = ['gloss', 'def', 'pos']

def process_reader(rd, fields, vlang, alang, add_sense='+', add_ex='&'):
    eid = 0
    ents = []
    cur_ent = None
    cur_sense = None
    ex = None
    extrans = None
    def proc_row(row, do_ent=True, do_sense=True):
        nonlocal cur_ent, cur_sense, ex, extrans
        for field, interp in zip(row, fields):
            v = field.strip()
            if not v:
                continue
            if interp[0] in ENTRY_FIELDS:
                if not do_ent:
                    continue
                if interp[1]:
                    cur_ent.fields[interp[0]] += v.split(interp[1])
                else:
                    cur_ent.fields[interp[0]].append(v)
            elif interp[0] in SENSE_FIELDS:
                if not do_sense:
                    continue
                if interp[1]:
                    cur_sense.fields[interp[0]] += v.split(interp[1])
                else:
                    cur_sense.fields[interp[0]].append(v)
            elif interp[0] == 'ex':
                ex = v
            elif interp[0] == 'extrans':
                extrans = v
            elif interp[0] == 'note':
                if do_ent:
                    cur_ent.notes.append(v)
                elif do_sense:
                    cur_sense.notes.append(v)
        if ex and extrans:
            cur_sense.examples.append((ex, extrans))
    for row in rd:
        ex = None
        extrans = None
        if row[0] == add_ex:
            if cur_sense is None:
                continue
            proc_row(row, do_ent=False, do_sense=False)
        elif row[0] == add_sense:
            if cur_ent is None:
                continue
            if cur_ent.notes:
                # if we have multiple senses, interpret notes as per-sense rather than per-entry
                cur_sense.notes = cur_ent.notes[:]
                cur_ent.notes = []
            eid += 1
            cur_sense = Sense(eid)
            cur_ent.senses.append(cur_sense)
            proc_row(row, do_ent=False)
        elif row[0]:
            eid += 1
            cur_ent = Entry(eid)
            ents.append(cur_ent)
            eid += 1
            cur_sense = Sense(eid)
            cur_ent.senses.append(cur_sense)
            proc_row(row)
    ret = '<?xml version="1.0" encoding="UTF-8" ?>\n<lift producer="Daniel on ehecatl" version="0.13">\n'
    ret += ''.join(e.generate(vlang, alang) for e in ents)
    ret += '</lift>\n'
    return ret

def process(lines, fields, vlang, alang, skip_header=True, csvsep=',', csvquote='"', **kwargs):
    rd = csv.reader(lines, delimiter=csvsep, quotechar=csvquote)
    if skip_header:
        next(rd)
    return process_reader(rd, fields, vlang, alang, **kwargs)

@app.route('/', methods=['GET', 'POST'])
def tsv2lift():
    if request.method == 'POST':
        fdata = request.files['spreadsheet'].read().decode('utf-8').splitlines()
        import tsv2lift
        fields = []
        print(request.form.keys())
        for k in request.form:
            if k.startswith('type'):
                n = int(k[4:])
                t = request.form[k]
                s = request.form['sep'+k[4:]]
                if t in ['form', 'cite']:
                    s = None
                fields.append((n, t, s))
        fields.sort()
        ret = tsv2lift.process(
            lines=fdata,
            fields=[(p[1], p[2]) for p in fields],
            vlang=request.form['lang1'],
            alang=request.form['lang2'],
            add_sense=request.form['add_sense'],
            add_ex=request.form['add_ex'],
            skip_header=request.form['header'],
            csvsep=(request.form['csvsep'].strip() or ','),
            csvquote=(request.form['csvquote'].strip() or '"'),
        )
        resp = make_response(ret)
        resp.headers.set('Content-Type', 'application/xml-dtd')
        resp.headers.set('Content-Disposition',
                         'attachment',
                         filename='converted.lift')
        return resp
    return app.send_static_file('index.html')
