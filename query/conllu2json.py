#!/usr/bin/env python3

import argparse
import json
from collections import defaultdict

parser = argparse.ArgumentParser()
parser.add_argument('infile', action='store')
parser.add_argument('outfile', action='store')
args = parser.parse_args()

all_feats = defaultdict(set)

feat_freq = defaultdict(lambda: defaultdict(lambda: 0))

def make_feat_dict(*strs):
    global all_feats, feat_freq
    dct = {}
    for s in strs:
        if s == '_':
            continue
        for op in s.split('|'):
            k, v = op.split('=')
            dct[k] = v
            all_feats[k].add(v)
            feat_freq[k][v] += 1
    return dct

order = []
sents = {}
with open(args.infile) as fin:
    for block in fin.read().strip().split('\n\n'):
        cur_sent = {
            'document': 'NO_DOC',
            'id': 'NO_ID',
            'order': [],
            'words': {},
            'trans': None,
        }
        sid = 'NO_DOC:NO_ID'
        markers = defaultdict(list)
        for line in block.split('\n'):
            if '# sent_id' in line:
                sid = line.split()[-1]
                cur_sent['document'], cur_sent['id'] = sid.split(':')
            elif '# text[en]' in line:
                cur_sent['trans'] = line.split('=')[1].strip()
            else:
                ls = line.split('\t')
                if len(ls) != 10:
                    continue
                word = {
                    'id': ls[0],
                    'form': ls[1],
                    'lemma': ls[2],
                    'upos': ls[3],
                    'xpos': ls[4],
                    'feats': make_feat_dict(ls[5], ls[9]),
                    'head': ls[6],
                    'rel': ls[7],
                    'edeps': ls[8],
                }
                cur_sent['words'][word['id']] = word
                cur_sent['order'].append(word['id'])
                if word['rel'] == 'case':
                    markers[word['head']].append(word['form'].lower())
        for k in markers:
            val = ','.join(sorted(set(markers[k])))
            all_feats['Markers'].add(val)
            cur_sent['words'][k]['feats']['Markers'] = val
        order.append(sid)
        sents[sid] = cur_sent
with open(args.outfile, 'w') as fout:
    fout.write(json.dumps({
        'sentences': sents,
        'order': order,
        'feats': {k:sorted(v) for k,v in all_feats.items()},
        'feat_freq': feat_freq,
    }))
