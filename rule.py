#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import string
import pattern
from copy import deepcopy

alpha = string.ascii_uppercase
alpha_lower = string.ascii_lowercase

translator = str.maketrans('', '', string.punctuation)

PREP_DICT = {'where': 'in', 'when': 'in', 'how': 'by', 'why': 'because'}
AUX_DO = ['do', 'does', 'did']
VERB_DO = ['do', 'does', 'did', 'done', 'doing']
SUBJ_WH = ['what', 'who', 'which', 'whom', 'whose']
AUX_BE = ['is', 'are', 'was', 'were', 'been', 'being', 'be']
AUX_HAVE = ['has', 'have', 'had']
PREPS = ['TO', 'IN', 'RP']
AUX = AUX_BE + AUX_DO + AUX_HAVE
TIME_WORDS = ['year', 'month', 'day', 'hour', 'decade', 'century', 'millenium']
DETS = ['the', 'a', 'an']

with open('preps.txt', 'r') as f:
    common_preps = f.read().splitlines()

def is_aux(tok):
    return (tok['form'].lower() in AUX or tok['xpostag'] == 'MD' or tok['form'] == 'there')

def is_verb(tok):
    return (tok['xpostag'].startswith('V') or tok['upostag'] in ['VERB', 'AUX'] or tok['xpostag'] == 'MD')


def add_affix(candidates, afxs, postag, pos='left'):
    assert(pos in ['left', 'right'])
    new_candidates = []
    for c in candidates:
        for afx in afxs:
            c_copy = deepcopy(c)
            c_copy.add_affix([{'form': afx, 'xpostag': postag}], pos)
            new_candidates.append(c_copy)
    return new_candidates

def lower(sent):
    return str(sent).lower().translate(translator).strip()


class Question:
    def __init__(self, question):
        self.question = self._preprocess(question)
        self.root = self._get_node('root')
        self.wh = self._get_wh()
        self.isvalid = self._is_valid()
        self.lastword_idx = self._lastword_idx()
        self.dangling_prep = self._dangling_prep()

        # Get the subject
        subj_nodes = self._get_children(self.root, ['nsubj', 'nsubj:pass', 'csubj'], 'anywhere')
        if len(subj_nodes) > 0:
            self.subj = subj_nodes[0]
        else:
            self.subj = None

        # Get auxiliary
        aux_nodes = self._get_children(self.root, ['aux', 'aux:pass'], 'anywhere')
        if len(aux_nodes) > 0:
            self.aux = aux_nodes[0]
        else:
            self.aux = None

        # Get copula
        self.cop = self._get_node('cop')

        if self.cop is not None and self.cop['form'] == 'be':
            aux_nodes = self._get_children(self.root, ['aux'], 'anywhere')
            if len(aux_nodes) > 0 and aux_nodes[0]['xpostag'] == 'MD':
                self.aux = aux_nodes[0]
                self.root = self.cop
                self.cop = None

        if self.cop is not None and self.aux is None and is_verb(self.root):
            self.aux = self.cop
            self.cop = None

        # Get all consecutive auxiliaries
        self.aux_toks = None
        if self.aux is not None:
            self.aux_toks = [self.aux]
            for tok in question[self.aux['id'] + 1:]:
                if is_aux(tok):
                    self.aux_toks.append(tok)
                else:
                    break

        self._answer_pos = None
        self._new_aux_pos = None

        if self.isvalid:
            self.wh_is_quantity = self._wh_is_quantity()
            self.wh_is_time = self._wh_is_time()
            self.wh_is_happened = self._wh_is_happened()
            self.wh_pos = self._get_wh_pos()
            self.aux_precedes_verb = self._aux_precedes_verb()
            self.wh_is_compl = self._wh_is_compl()
            self.dobj_pos = self._get_dobj_pos()
            self.is_do_neg = self.is_do_neg()

    def _preprocess(self, question):
        for i in range(len(question)):
            question[i]['id'] = i
            question[i]['head'] -= 1
            # if question[i]['form'] == '-LRB-':
            #    question[i]['form'] = '('
            # elif question[i]['form'] == '-RRB-':
            #    question[i]['form'] = ')'
        return question

    def _get_node(self, rel):
        for tok in self.question:
            if tok['deprel'].startswith(rel):
                return tok
        return None

    def _get_children(self, node, rels, loc='right'):
        assert (loc in ['left', 'right', 'anywhere'])
        head_id = node['id']
        children = []
        for tok in self.question:
            if 'head' in tok and tok['head'] == head_id \
                    and (len(rels) == 0 or tok['deprel'] in rels):
                if loc == 'left' and tok['id'] < head_id:
                    children.append(tok)
                elif loc == 'right' and tok['id'] > head_id:
                    children.append(tok)
                elif loc == 'anywhere':
                    children.append(tok)
        return children

    def _get_nth_child(self, node, loc='right', n=0):
        assert (loc in ['left', 'right'])
        children = self._get_children(node, [], loc)
        if len(children) == 0:
            return node
        else:
            return self._get_nth_child(children[n], loc, 0)

    def _get_wh(self):
        whs = []
        question = self.question
        for tok in question:
            if tok['xpostag'].startswith('W') and tok['form'] != 'that':
                whs.append(tok)
        if len(whs) == 0:
            return None
        elif len(whs) == 1:
            return whs[0]
        else:
            for wh in whs:
                if len(question) > wh['id'] + 1 \
                        and is_verb(question[wh['id'] + 1]) and 'cl' in question[wh['id'] + 1]['deprel']:
                    continue
                elif 'cl' in question[wh['head']]['deprel']:
                    continue
                else:
                    return wh

    def _get_wh_pos(self):
        wh = self.wh
        wh_idx = wh['id']
        wh_lower = self.wh['form'].lower()
        question = self.question

        wh_tok_ids = [wh_idx]
        wh_tok_heads = [wh['head']]
        root_idx = self.root['id']
        cop = self.cop
        for i, tok in enumerate(reversed(question[:wh_idx])):
            if tok['xpostag'] in PREPS \
                    or (wh_lower == 'what' and i == 0 and tok['form'] == 'do' and question[wh_idx - 2]['form'] == 'to'):
                wh_tok_ids.append(tok['id'])
                wh_tok_heads.append(tok['head'])
            else:
                break

        if cop is not None:
            root_idx = cop['id']
        for tok in question[wh_idx + 1:]:
            if not is_verb(tok) and (wh_idx <= root_idx or tok['id'] in wh_tok_heads):
                wh_tok_ids.append(tok['id'])
                wh_tok_heads.append(tok['head'])
            elif tok['form'] == 'of':
                wh_tok_ids.append(tok['id'])
                wh_tok_heads.append(tok['head'])
            elif self.wh_is_happened and tok['form'] == 'happened':
                wh_tok_ids.append(tok['id'])
                if len(question) > tok['id'] + 1 and question[tok['id'] + 1]['form'] == 'to':
                    wh_tok_ids.append(tok['id'] + 1)
                break
            else:
                break
        return min(wh_tok_ids), max(wh_tok_ids)

    def _is_valid(self):
        question = self.question
        has_root = False
        has_verb = False
        has_wh = (self.wh is not None)
        for tok in self.question:
            if tok['deprel'] == 'root':
                has_root = True
            if is_verb(tok):
                has_verb = True
        return (has_root and has_verb and has_wh)

    def _lastword_idx(self):
        question = self.question
        for i, tok in enumerate(question[::-1]):
            if tok['xpostag'][0] in alpha and tok['xpostag'] != 'SYM':
                return len(question) - i - 1
        return 0

    def _dangling_prep(self):
        prep = self._get_children(self.root, ['compound:prt', 'obl', 'case'], 'right')
        question = self.question
        for p in prep:
            if p['deprel'] == 'case' and any([tok['head'] == p['id'] for tok in question[:self.root['id']]]):
                return p
            elif p['deprel'] == 'case':
                continue
            elif p['xpostag'] in PREPS and len(question) > p['id'] + 1 and question[p['id'] + 1]['head'] > p['id']:
                return p
            elif p['xpostag'] in PREPS and len(question) <= p['id'] + 1:
                return p
        return None

    def _is_descendant(self, child, head):
        if child == head:
            return True
        question = self.question
        count = 0
        while 'head' in child and child['head'] != -1:
            if question[child['head']] == head:
                return True
            child = question[child['head']]
            count += 1
            if count > 5:
                break
        return False

    def _get_dobj_pos(self):
        question = self.question
        lastword_idx = self.lastword_idx
        root = self.root
        root_idx = root['id']
        dobj_pos = root_idx + 1

        # If root verb is the last word in the sentence
        if dobj_pos == lastword_idx:
            return dobj_pos

        # Get complements
        comps = self._get_children(root, ['xcomp', 'compound:prt'], 'right')
        for c in comps:
            if c['deprel'] == 'xcomp' and not is_verb(c):
                continue
            elif c['id'] + 1 > dobj_pos:
                dobj_pos = c['id'] + 1

        if len(question) > dobj_pos:
            postword = question[dobj_pos]
            if postword['xpostag'] in PREPS and postword['head'] < dobj_pos:
                dobj_pos = postword['id'] + 1

        return min(lastword_idx + 1, dobj_pos)

    def _wh_is_time(self):
        wh = self.wh
        wh_lower = wh['form'].lower()
        wh_idx = wh['id']
        question = self.question
        return (wh_lower in ['what', 'which'] and len(question) > wh_idx + 1 \
                and question[wh_idx + 1]['form'] in TIME_WORDS)

    def _wh_is_quantity(self):
        question = self.question
        q_length = len(question)
        wh_lower = self.wh['form'].lower()
        wh_idx = self.wh['id']
        return (q_length > wh_idx + 1 and wh_lower == 'how' and question[wh_idx + 1]['form'] in ['many', 'much'])

    def _wh_is_happened(self):
        question = self.question
        wh_lower = self.wh['form'].lower()
        if wh_lower != 'what':
            return False
        wh_idx = self.wh['id']
        if len(question) > wh_idx + 1 and question[wh_idx + 1]['form'] == 'happened':
            return True
        return False

    def _aux_precedes_verb(self):
        cop = self.cop
        aux = self.aux
        root = self.root
        root_idx = root['id']
        adverbs = 0
        for tok in reversed(self.question[:root_idx]):
            if tok['xpostag'].startswith('RB'):
                adverbs += 1
            else:
                break

        if cop is not None and is_verb(root) and cop['id'] == root['id'] - 1 - adverbs:
            return True
        elif aux is not None and aux['id'] == root_idx - adverbs - len(self.aux_toks):
            return True
        return False

    def _wh_is_compl(self):
        question = self.question
        q_length = len(question)
        wh_lower = self.wh['form'].lower()
        wh_idx = self.wh['id']
        cop = self.cop
        aux = self.aux
        root = self.root
        lastword_idx = self.lastword_idx
        quantity = self.wh_is_quantity

        if ((wh_idx > 0 and question[wh_idx - 1]['xpostag'] in PREPS) \
                    and not (quantity and question[wh_idx - 1]['form'].lower() == 'about')) \
                or question[lastword_idx]['xpostag'] in PREPS \
                or (wh_lower not in SUBJ_WH and not quantity) \
                or (wh_lower in SUBJ_WH and self.dangling_prep is not None \
                            and not self.aux_precedes_verb) \
                or (self.wh_is_time and (aux is not None or cop is not None) and not self.aux_precedes_verb):
            return True
        return False

    def get_answer_pos(self, a):
        # Answer position is the index of the previous word + 1
        if self._answer_pos is not None:
            return self._answer_pos
        question = self.question
        wh = self.wh
        wh_lower = wh['form'].lower()
        wh_idx = wh['id']
        root = self.root
        root_idx = root['id']
        aux = self.aux
        cop = self.cop
        subj = self.subj
        lastword_idx = self.lastword_idx
        dobj_pos = self.dobj_pos
        comps = self._get_children(root, ['xcomp'], 'right')
        startidx, endidx = self.wh_pos
        dangling_prep = self.dangling_prep

        if self.wh_is_happened and question[endidx]['form'] == 'to':
            head = question[question[endidx]['head']]
            self._answer_pos = head['id'] + 1
            if not a.type.startswith('V'):
                a.add_affix([{'form': 'experienced', 'xpostag': 'VBN'}], 'left')
            self.type = 'WHAT_HAPPENED_TO'
        elif self.wh_is_happened:
            self._answer_pos = lastword_idx + 1
            self.type = 'WHAT_HAPPENED'
        elif wh_idx > root_idx or (cop is not None and wh_idx > cop['id']):
            self._answer_pos = startidx
            self.type = 'NO_WH_MOV'
        elif self.wh_is_compl and dangling_prep is None:
            self._answer_pos = lastword_idx + 1
            self.type = 'COMPL'
        elif self.wh_is_compl:
            self._answer_pos = dangling_prep['id'] + 1
            self.type = 'COMPL'
        elif (cop is not None and wh_idx == root_idx) or aux is None \
                or (self._is_descendant(wh, subj) and not (
                        aux is not None and aux['id'] < root_idx - len(self.aux_toks))) \
                or self.aux_precedes_verb:
            self._answer_pos = startidx
            self.type = 'SUBJ'
        elif (a.type.startswith('V') or a.cop is not None) \
                and (root['form'] in VERB_DO or (len(comps) > 0 and comps[0]['form'] in VERB_DO)):
            if len(comps) > 0 and comps[0]['form'] in VERB_DO:
                self._answer_pos = comps[0]['id']
            else:
                self._answer_pos = root_idx
            self.type = 'VERB'
        else:
            self._answer_pos = dobj_pos
            self.type = 'DOBJ'
        return self._answer_pos

    def set_answer_pos(self, pos):
        question_length = len(self.question)
        assert (abs(pos) < question_length + 1)
        self._answer_pos = pos
        return

    def remove_tok(self, tok):
        if tok in self.question:
            self.question.remove(tok)
        return

    def set_aux_pos(self, pos):
        self._new_aux_pos = pos
        return

    def _get_new_aux_pos(self):
        aux = self.aux
        old_pos = aux['id']
        root = self.root
        root_idx = root['id']
        if old_pos > root_idx:
            return old_pos

        question = self.question
        lastword_idx = self.lastword_idx
        aux_length = len(self.aux_toks)
        if old_pos + aux_length - 1 == lastword_idx:
            return old_pos
        last_prev_verb = root_idx
        for tok in reversed(question[:root_idx]):
            if is_verb(tok):
                last_prev_verb = tok['id']
            else:
                break
        last_prev_adv = last_prev_verb
        for tok in reversed(question[:last_prev_verb]):
            if tok['xpostag'].startswith('RB') or (
                    tok['deprel'] == 'advmod' and tok['head'] in [root_idx, last_prev_verb]):
                last_prev_adv = tok['id']
            else:
                break

        return last_prev_adv

    def _get_new_cop_pos(self):
        cop = self.cop
        startidx, endidx = self.wh_pos
        old_pos = cop['id']
        question = self.question
        root = self.root
        root_idx = root['id']
        subj = self.subj
        lastword_idx = self.lastword_idx
        a_pos = self._answer_pos
        if old_pos == lastword_idx:
            return old_pos
        root_mod = self._get_children(root, ['case', 'det', 'amod', 'advmod'], 'left')
        if len(root_mod) > 0 and root_mod[-1]['id'] == root_idx - 1:
            root_idx = root_mod[0]['id']

        if root_idx > endidx + 2 and root_idx > old_pos and self.type == 'COMPL':
            return root_idx
        else:
            return lastword_idx + 1

    def swap_aux(self):
        new_pos = self._new_aux_pos
        if self.aux is not None:
            word = self.aux
            aux_length = len(self.aux_toks)
            if new_pos is None:
                new_pos = self._get_new_aux_pos()
        elif self.cop is not None:
            word = self.cop
            aux_length = 1
            if new_pos is None:
                new_pos = self._get_new_cop_pos()
        else:
            return

        old_pos = word['id']
        if old_pos == new_pos:
            return
        question = self.question

        neworder = [i for i in range(old_pos)] + [i + aux_length for i in range(old_pos, new_pos - aux_length)] \
                   + [i for i in range(old_pos, old_pos + aux_length)] + [i for i in range(new_pos, len(question))]
        self.question = [question[i] for i in neworder]
        return

    def change_tense(self, past=False, pres_3sg=False):
        root = self.root
        if not is_verb(root):
            return
        conj = []
        for tok in self.question:
            if 'head' in tok and tok['head'] == root['id'] and tok['deprel'] == 'conj' and is_verb(tok):
                conj.append(tok)
        if past:
            for tok in [root] + conj:
                if tok['form'] == 'leave':
                    new_form = 'left'
                else:
                    new_form = pattern.en.conjugate(tok['form'], tense='past')
                tok['form'] = new_form
                tok['xpostag'] = 'VBD'
        elif pres_3sg:
            for tok in [root] + conj:
                tok['form'] = pattern.en.conjugate(tok['form'], tense='present', person=3, number='singular')
                tok['xpostag'] = 'VBZ'
        return

    def format_declr(self):
        words = [t['form'] for t in self.question]
        for i, t in enumerate(words[::-1]):
            if t == '?':
                words = words[:-i - 1] + ['.'] + words[len(words) - i:]
                break
        words[0] = words[0][0].upper() + words[0][1:]
        return words

    def insert_answer(self, a):
        a_pos = self._answer_pos
        if a_pos is None:
            return None

        answer = a.answer
        question = self.question
        aux = self.aux
        startidx, endidx = self.wh_pos

        if self.type == 'VERB':
            self.remove_tok(self.question[a_pos])

        if startidx == a_pos:
            self.question = question[:startidx] + answer + question[endidx + 1:]
        elif startidx < a_pos:
            self.question = question[:startidx] + question[endidx + 1:a_pos] + answer + question[a_pos:]
        else:
            self.question = answer + question[:startidx] + question[endidx + 1:]

        if aux is not None and aux['form'] in AUX_DO and not self.is_do_neg:
            self.remove_tok(aux)

        return

    def is_do_neg(self):
        if self.aux is not None and self.aux['form'] in AUX_DO and \
                (self.question[self.aux['id'] + 1]['form'] == 'not' \
                         or (self.root['id'] > 0 and self.question[self.root['id'] - 1]['form'] == 'not')):
            return True
        else:
            return False

    def insert_answer_default(self, a):
        a_pos = self._answer_pos
        if a_pos is None:
            a_pos = self.get_answer_pos(a)
        question = self.question
        lastword_idx = self.lastword_idx
        aux = self.aux
        cop = self.cop
        startidx, endidx = self.wh_pos
        wh_lower = self.wh['form'].lower()

        if self.type in ['COMPL', 'DOBJ', 'VERB']:
            self.swap_aux()
        elif self.type == 'SUBJ' and wh_lower != 'who' and cop is not None and not self.aux_precedes_verb \
                and not (len(question) > cop['id'] + 1 and question[cop['id'] + 1]['xpostag'] in PREPS):
            self.set_aux_pos(lastword_idx + 1)
            self.swap_aux()
            self.set_answer_pos(lastword_idx + 1)

        if aux is not None and aux['form'] in AUX_DO and not self.is_do_neg:
            self.change_tense(past=(aux['form'] == 'did'), pres_3sg=(aux['form'] == 'does'))

        if wh_lower == 'whose':
            a = add_affix([a], ["'s"], 'poss', 'right')[0]

        if self.type == 'VERB' and aux is not None and a_pos == self.root['id']:
            a.change_tense(past=(aux['form'] == 'did'), pres_3sg=(aux['form'] == 'does'))

        if question[startidx]['xpostag'] in PREPS and a.answer[0]['xpostag'] not in PREPS:
            a = add_affix([a], [question[startidx]['form'].lower()], question[startidx]['xpostag'], 'left')[0]

        elif self.type == 'COMPL' and \
                (a.answer[0]['xpostag'] not in PREPS and question[lastword_idx]['xpostag'] not in PREPS) \
                and self.dangling_prep is None:
            if wh_lower in PREP_DICT and not (wh_lower == 'how' and startidx != endidx):
                prep = PREP_DICT[wh_lower]
                if wh_lower == 'why' and a.type.startswith('N'):
                    prep += ' of'
                a = add_affix([a], [prep], 'IN', 'left')[0]
            elif self.wh_is_time:
                a = add_affix([a], [PREP_DICT['when']], 'IN', 'left')[0]

        self.insert_answer(a)
        return


class AnswerSpan:
    def __init__(self, answer):
        self.answer = self._preprocess(answer)
        self.isvalid = self._isvalid()
        self.root = self._get_rel('root')
        self.cop = self._get_rel('cop')
        self.type = self._type()

    def _isvalid(self):
        return len(self.answer) > 0

    def _type(self):
        if self.root is None:
            return None
        else:
            return self.root['xpostag']

    def _get_rel(self, rel):
        answer = self.answer
        for tok in answer:
            if tok['deprel'] == rel:
                return tok
        return None

    def _preprocess(self, answer):
        for i in range(len(answer)):
            answer[i]['id'] = i
            answer[i]['head'] -= 1
            # if answer[i]['form'] == '-LRB-':
            #    answer[i]['form'] = '('
            # elif answer[i]['form'] == '-RRB-':
            #    answer[i]['form'] = ')'
        if answer[-1]['upostag'] == 'PUNCT':
            answer = answer[:-1]
        if len(answer) > 0 and not answer[0]['xpostag'].startswith('NNP'):
            answer[0]['form'] = answer[0]['form'][0].lower() + answer[0]['form'][1:]
        return answer

    def add_affix(self, afx_node, pos='left'):
        if pos == 'left':
            self.answer = afx_node + self.answer
        elif pos == 'right':
            self.answer = self.answer + afx_node
        return

    def change_tense(self, past=False, pres_3sg=False):
        root = self.root
        if root is None or not is_verb(root):
            return
        conj = []
        for tok in self.answer:
            if 'head' in tok and tok['head'] == root['id'] and tok['deprel'] == 'conj' and is_verb(tok):
                conj.append(tok)
        if past:
            for tok in [root] + conj:
                if tok['form'] == 'leave':
                    new_form = 'left'
                else:
                    new_form = pattern.en.conjugate(tok['form'], tense='past')
                tok['form'] = new_form
                tok['xpostag'] = 'VBD'
        elif pres_3sg:
            for tok in [root] + conj:
                tok['form'] = pattern.en.conjugate(tok['form'], tense='present', person=3, number='singular')
                tok['xpostag'] = 'VBZ'
        return


