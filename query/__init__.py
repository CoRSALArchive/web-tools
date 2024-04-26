from flask import Blueprint, request, render_template
import os
import subprocess
from tempfile import NamedTemporaryFile

base_dir = os.path.dirname(__file__)
app = Blueprint('query', __name__,
                static_folder=os.path.join(base_dir, 'static'),
                static_url_path='',
                template_folder=os.path.join(base_dir, 'templates'))

def run_query(query_text):
    with NamedTemporaryFile() as fout:
        fout.write(query_text.encode('utf-8'))
        fout.flush()
        proc = subprocess.run(
            ['grew', 'grep',
             '-i', os.path.join(base_dir, 'data.conllu'),
             '-request', fout.name],
            capture_output=True,
        )
        return proc.stdout.decode('utf-8')

@app.route('/', methods=['GET', 'POST'])
def main():
    if request.method == 'POST':
        match = run_query(request.form['query'])
        params = request.form['query-params']
    else:
        match = '[]'
        params = '{}'
    try:
        with open(os.path.join(base_dir, 'data.json')) as fin:
            data = fin.read()
    except:
        data = '{"sentences": {}, "order": [], "feats": {}}';
    return render_template('index.html', data=data, match=match, params=params)
