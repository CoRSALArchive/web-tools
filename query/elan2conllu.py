#!/usr/bin/env python3

from xml.etree import ElementTree as ET
import re
from collections import defaultdict
import sys

class Tier:
    ALL = {}
    def __init__(self, name, parent_name=None):
        self.name = name
        self.parent_name = parent_name
        #print(f'Tier({name}, {parent_name})')
        self.annotations = []
        Tier.ALL[name] = self
    def get_by_parent(self, key):
        for a in self.annotations:
            if a.parent_id == key:
                yield a

class Annotation:
    ALL = {}
    def __init__(self, id, text, parent_id=None):
        self.id = id
        self.text = text
        self.parent_id = parent_id
        Annotation.ALL[id] = self

def read_file(fname):
    tree = ET.parse(fname)
    root = tree.getroot()
    for t_elem in root.iter('TIER'):
        t = Tier(t_elem.attrib['TIER_ID'], t_elem.attrib.get('PARENT_REF'))
        for a_elem in t_elem.iter('ANNOTATION'):
            for ae2 in a_elem:
                if ae2.tag in ['ALIGNABLE_ANNOTATION', 'REF_ANNOTATION']:
                    t.annotations.append(Annotation(
                        ae2.attrib['ANNOTATION_ID'],
                        ae2.find('ANNOTATION_VALUE').text,
                        ae2.attrib.get('ANNOTATION_REF')
                    ))
        #print(len(t.annotations))

class Sentence:
    def __init__(self, id, sent_id=None):
        self.id = id
        if sent_id:
            self.sent_id = sent_id
        else:
            self.sent_id = Annotation.ALL[id].text
        self.trans = None
        for a in Tier.ALL['A_phrase-gls-en'].get_by_parent(id):
            self.trans = a.text
        self.comments = []
        self.words = []
        self.aligned = False
        self.clause_children = defaultdict(set)
    def gather_words(self):
        for a in Tier.ALL['A_word-txt-qaa-x-dim'].get_by_parent(self.id):
            if a.text:
                self.words.append(Word(a.id))
    def process_functions(self):
        clause_stack = ['none']
        clause_number_stack = [0]
        function_map = {
            'v': 'verb',
            't': 'theme',
            'l': 'oblique',
            'a': 'agent',
            'p': 'patient',
            's': 'subject',
            'g': 'goal',
            '1': 'copsubj',
            '2': 'copobj',
        }
        clause_map = {
            '': 'main',
            'r': 'relative',
            'c': 'complement',
        }
        cl_num = 0
        for i, w in enumerate(self.words):
            w.idx = str(i+1)
            subclause = ''
            for c in w.function.lower():
                if c in function_map:
                    w.role = function_map[c]
                    w.clause_type = clause_stack[-1]
                    w.clause_number = clause_number_stack[-1]
                elif c in 'rc':
                    subclause = c
                elif c == '[':
                    clause_stack.append(clause_map[subclause])
                    cl_num += 1
                    self.clause_children[clause_number_stack[-1]].add(cl_num)
                    clause_number_stack.append(cl_num)
                elif c == ']':
                    clause_stack.pop()
                    clause_number_stack.pop()
                    if not clause_stack:
                        raise ValueError(f'Unbalanced brackets in Function tier for {self.sent_id}: unexpected close bracket at {w.surf}.')
            if len(clause_stack) > 1 and w.clause_number == 0:
                w.clause_type = clause_stack[-1]
                w.clause_number = clause_number_stack[-1]
        if len(clause_stack) > 1:
            raise ValueError(f'Unbalanced brackets in Function tier for {self.sent_id}: more open brackets than close brackets.')
    def process_phrase(self, words, role):
        idx = 0
        special = ['verb', 'relative', 'complement']
        for i, w in enumerate(words):
            if 'Access' in w.feats or 'Stative' in w.feats:
                idx = i
                break
        else:
            for i, w in enumerate(words):
                if w.surf.startswith('['):
                    idx = i
                    break
                if role not in special and w.upos in ['NOUN', 'PRON']:
                    idx = i
                    break
        for i, w in enumerate(words):
            if i == idx:
                continue
            w.head = words[idx].idx
            if w.upos == 'ADP':
                w.rel = 'case'
            elif w.upos == 'NUM':
                w.rel = 'nummod'
            elif w.upos == 'DET':
                w.rel = 'det'
            elif w.upos == 'ADJ':
                w.rel = 'amod'
            else:
                w.rel = 'dep'
        return words[idx]
    def process_clause(self, phrases):
        special = ['verb', 'relative', 'complement']
        if 'verb' not in phrases:
            raise ValueError(f'{self.sent_id} has clause with no verb.')
        if phrases['relative']:
            heads = [w for r, w in phrases.items() if r not in special]
            heads.sort(key=lambda w: int(w.idx), reverse=True)
            for wr in phrases['relative']:
                for wh in heads:
                    if int(wh.idx) < int(wr.idx):
                        wr.head = wh.idx
                        wr.rel = 'acl'
                        break
        if phrases['complement']:
            ch = phrases['complement'][0]
            for cd in phrases['complement'][1:]:
                cd.head = ch.idx
                cd.rel = 'conj'
            ch.head = phrases['verb'].idx
            ch.rel = 'complement'
        for role, word in phrases.items():
            if role not in special:
                word.head = phrases['verb'].idx
                word.rel = word.role
        return phrases['verb']
    def process_sentence(self):
        self.process_functions()
        groups = defaultdict(lambda: defaultdict(list))
        for w in self.words:
            groups[w.clause_number][w.role].append(w)
        clause_todo = []
        for clnum, phrase in groups.items():
            dct = {'relative': [], 'complement': []}
            for role, words in phrase.items():
                dct[role] = self.process_phrase(words, role)
            clause_todo.append((clnum, dct))
        done = set()
        clause_heads = {}
        while clause_todo:
            new_todo = []
            for clnum, phrases in clause_todo:
                if self.clause_children[clnum] <= done:
                    if clnum == 0:
                        break
                    for c in self.clause_children[clnum]:
                        w = clause_heads[c]
                        phrases[w.clause_type].append(clause_heads[c])
                    clause_heads[clnum] = self.process_clause(phrases)
                    done.add(clnum)
                else:
                    new_todo.append((clnum, phrases))
            clause_todo = new_todo
        ls = sorted(self.clause_children[0])
        if not ls:
            raise ValueError(f'No clauses found in {self.sent_id}.')
        r = clause_heads[ls[0]]
        r.head = '0'
        r.rel = 'root'
        for c in ls[1:]:
            clause_heads[c].head = r.idx
            clause_heads[c].rel = 'conj'
    def add_arcs(self):
        for i, w in enumerate(self.words):
            w.idx = str(i+1)
            if i == 0: continue
            if w.upos == 'NUM' and self.words[i-1].upos == 'NOUN':
                w.rel = 'nummod'
                w.head = str(i)
            elif w.gloss in ['LOC', 'GEN'] and self.words[i-1].upos in ['NOUN', 'PRON']:
                w.rel = 'case'
                w.head = str(i)
                self.words[i-1].other['locative'] = True
            elif w.upos == 'AUX' and self.words[i-1].upos == 'VERB':
                w.rel = 'aux'
                w.head = str(i)
            elif w.upos == 'VERB' and self.words[i-1].upos == 'VERB':
                w.rel = 'conj'
                w.head = str(i)
            #elif w.gloss == self.words[i-1].gloss:
            #    w.rel = 'redup'
            #    w.head = str(i)
        # copula promotion
        vb = [w for w in self.words if w.upos == 'VERB']
        aux = [w for w in self.words if w.upos == 'AUX']
        if len(vb) == 0 and len(aux) == 1:
            aux[0].upos = 'VERB'
        theta = []
        for i, w in enumerate(self.words, 1):
            if 'Theta' in w.feats:
                theta.append((i, w.feats['Theta']))
            elif w.upos == 'VERB':
                theta.append((i, w.upos))
        for j, (i, role) in enumerate(theta):
            for k in range(j+1, len(theta)):
                if theta[k][1] != role:
                    break
                self.words[theta[k][0]-1].rel = 'conj'
                self.words[theta[k][0]-1].head = str(i)
        self.align()
    def to_conllu(self):
        lns = [f'# sent_id = {self.sent_id}']
        lns += ['# '+l for l in self.comments]
        if self.trans:
            lns.append(f'# text[en] = {self.trans}')
        for w in self.words:
            lns.append(w.to_conllu())
        return '\n'.join(lns)

FEAT_RENAME = {
    'Access': {
        'previous subject': 'PrevSubj',
    },
    'Affected': {
        'high': 'High',
        'medium': 'Med',
        'low': 'Low',
    },
    'FocusScope': {
        'noun phrase': 'NP',
    },
}

class Word:
    def __init__(self, id):
        self.id = id
        self.idx = '_'
        self.surf = Annotation.ALL[self.id].text or '_'
        self.lem = '_'
        self.upos = '_'
        self.xpos = self.get_ann('A_word-pos-en') or '_'
        if self.xpos == '<Not Sure>':
            self.xpos = 'unk'
        if self.xpos == '_':
            ls = []
            for a in Tier.ALL['A_morph-txt-qaa-x-dim'].get_by_parent(self.id):
                for b in Tier.ALL['A_morph-msa-en'].get_by_parent(a.id):
                    ls.append(b)
            if len(ls) == 1 and ls[0].text:
                self.xpos = ls[0].text
        self.feats = {}
        self.head = '_'
        self.rel = '_'
        self.gloss = self.get_ann('A_word-gls-en')
        self.function = self.get_ann('Function') or ''
        self.role = 'none'
        self.clause_type = 'none'
        self.clause_number = 0
        self.other = {}
    def get_ann(self, tier):
        for a in Tier.ALL[tier].get_by_parent(self.id):
            if a.text:
                return a.text
    def add_feat(self, tier, feat):
        a = self.get_ann(tier)
        if a:
            b = FEAT_RENAME.get(feat, {}).get(a, a)
            if b and b not in ['not sure', 'not applicable']:
                self.feats[feat] = b
    def add_parent_feat(self, tier, feat):
        id = Annotation.ALL[self.id].parent_id
        for a in Tier.ALL[tier].get_by_parent(id):
            if a.text:
                b = FEAT_RENAME.get(feat, {}).get(a.text, a.text)
                if b and b not in ['not sure', 'not applicable']:
                    self.feats[feat] = b
                    return
    def gather_features(self):
        self.add_feat('Accessibility', 'Access')
        self.add_feat('Affectedness', 'Affected')
        self.add_feat('Agency', 'Agency')
        self.add_feat('Animacy', 'Animacy')
        self.add_feat('Definiteness', 'Definite')
        self.add_feat('Durativity', 'Durative')
        self.add_feat('Focus function', 'FocusFunc')
        self.add_feat('Focus scope', 'FocusScope')
        self.add_feat('Individuation', 'Individuation')
        self.add_feat('Stativity', 'Stative')
        self.add_feat('Telicity', 'Telic')
        self.add_feat('Thematic Role', 'Theta')
        self.add_feat('Topicality', 'Topic')
        self.add_feat('Valence', 'Valence')
        if 'Access' in self.feats:
            self.add_parent_feat('Situation', 'NSituation')
            self.add_parent_feat('Mood', 'NMood')
            self.add_parent_feat('Aspect', 'NAspect')
            self.add_parent_feat('Surprise', 'NSurprise')
            self.add_parent_feat('Sentence type', 'NSentenceType')
            self.add_parent_feat('Tense', 'NTense')
        if 'Stative' in self.feats:
            self.add_parent_feat('Situation', 'VSituation')
            self.add_parent_feat('Mood', 'VMood')
            self.add_parent_feat('Aspect', 'VAspect')
            self.add_parent_feat('Surprise', 'VSurprise')
            self.add_parent_feat('Sentence type', 'VSentenceType')
            self.add_parent_feat('Tense', 'VTense')
        pos = {
            'adj': 'ADJ',
            'adv': 'ADV',
            'Intj': 'INTJ',
            'n': 'NOUN',
            'num': 'NUM',
            'nprop': 'PROPN',
            'pro': 'PRON',
            'v': 'VERB',
            'TOP': 'ADP',
            'unk': 'X',
        }
        if self.gloss in ['LOC', 'GEN', 'ACC', 'COM', 'ABL']:
            self.upos = 'ADP'
        elif self.xpos == '<Not Sure>' and self.surf.lower() == 'ne':
            self.upos = 'ADP'
        elif self.gloss in ['BEN', 'CAUS', 'be']:
            self.upos = 'AUX'
        elif self.xpos in pos:
            self.upos = pos[self.xpos]
        elif self.surf == '[COPULA]':
            self.upos = 'AUX'
        elif self.gloss in ['the', 'DEM']:
            self.upos = 'DET'
    def to_conllu(self):
        ls = [self.idx, self.surf, self.lem, self.upos, self.xpos]
        ls.append('|'.join(sorted(f'{k}={v}' for k, v in self.feats.items())) or '_')
        ls += [self.head, self.rel, '_']
        ls.append(f'Gloss={self.gloss}' if self.gloss else '_')
        return '\t'.join(ls)

def make_sentences(docname):
    phr = Tier.ALL['A_phrase-segnum-en']
    segnum = True
    if phr.parent_name == 'A_phrase-txt-qaa-x-dim':
        phr = Tier.ALL['A_phrase-txt-qaa-x-dim']
        segnum = False
    for a in phr.annotations:
        i = a.text
        if not segnum:
            for ann in Tier.ALL['A_phrase-segnum-en'].get_by_parent(a.id):
                if ann.text:
                    i = ann.text
                    break
        s = Sentence(a.id, docname + ':' + i)
        s.gather_words()
        for w in s.words:
            w.gather_features()
        try:
            s.process_sentence()
        except ValueError as e:
            print(e, file=sys.stderr)
            continue
        yield s

if __name__ == '__main__':
    import sys
    read_file(sys.argv[1])
    docname = sys.argv[1].split('/')[-1].replace(' ', '_')
    if docname.endswith('.eaf'):
        docname = docname[:-4]
    #print(len(Tier.ALL))
    #print(len(Annotation.ALL))
    #print(sorted(Tier.ALL.keys()))
    #print(len(Tier.ALL['Word order'].annotations))
    #sys.exit(0)
    for s in make_sentences(docname):
        print(s.to_conllu())
        print('')
