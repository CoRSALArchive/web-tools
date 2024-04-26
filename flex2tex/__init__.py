from flask import Blueprint, request, make_response
import xml.etree.ElementTree as ET
import os

app = Blueprint('flex2tex', __name__,
                static_folder=os.path.join(os.path.dirname(__file__), 'static'))

def gloss_concat(a, b, gloss):
    b_app = (b or '').replace('==', '=')
    if gloss and b and b.upper() == b:
        b_app = '\\textsc{'+b_app.lower()+'}'
    if not b:
        return a
    if not a:
        return b_app
    if a.rstrip('}')[-1] in '=-' or b[0] in '=-':
        return a + b_app
    else:
        return a + '-' + b_app

def process_flextext_file(infile):
    tree = ET.parse(infile).getroot()
    ret = []
    for phrase in tree.iter('phrase'):
        text = phrase.findall('./item[@type="txt"]')[0].text
        ft = phrase.findall('./item[@type="gls"]')[0].text
        a = []
        b = []
        c = []
        for word in phrase.iter('word'):
            ls = word.findall('./item[@type="txt"]')
            if not ls:
                continue
            a.append(ls[0].text)
            bm = ''
            cm = ''
            for morph in word.iter('morph'):
                for item in morph:
                    if item.attrib['type'] == 'txt':
                        bm = gloss_concat(bm, item.text, False)
                    elif item.attrib['type'] == 'gls':
                        cm = gloss_concat(cm, item.text, True)
            b.append(bm)
            c.append(cm)
        ret.append(f'''\\ex
\\begingl[lingstyle=somestyle]
\\glpreamble {text} //
\\gla {' '.join(a)} //
\\glb {' '.join(b)} //
\\glc {' '.join(c)} //
\\glft `{ft}' //
\\endgl
\\xe''')
    preamble = '''\\documentclass[10pt]{article}

\\usepackage{expex} % generate glosses
\\usepackage{fullpage} % have reasonable margins
\\pagenumbering{arabic} % use arabic numerals for page numbers
%\\setcounter{page}{3} % first page is page 3 (remove initial % to enable)

\\begin{document}

\\definelingstyle{somestyle}{everygla={},everyglpreamble=\\it,glhangindent=0pt}

'''
    return preamble + '\n\n'.join(ret) + '\n\n\\end{document}'

@app.route('/', methods=['GET', 'POST'])
def flex2tex():
    if request.method == 'POST':
        for fname in request.files:
            txt = process_flextext_file(request.files[fname])
            resp = make_response(txt)
            resp.headers.set('Content-Type', 'text/plain')
            resp.headers.set('Content-Disposition',
                             'attachment',
                             filename='converted.tex')
            return resp
    return app.send_static_file('index.html')
