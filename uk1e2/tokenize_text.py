import stanza

import re
import unicodedata
import ftfy

from loguru import logger


alphabet_filter = {
    'latin': re.compile(r'[^A-Za-z\' -]'),
    'cyr': re.compile(r'[^ыёэъЫЁЭЪйцукенгшщзхїфивапролджєґячсміiтьбюЙЦУКЕНГШЩЗХЇФИВАПРОЛДЖЄҐЯЧСМІТЬБЮ\' -]'),
    'uk': re.compile(         r'[^йцукенгшщзхїфивапролджєґячсміiтьбюЙЦУКЕНГШЩЗХЇФИВАПРОЛДЖЄҐЯЧСМІТЬБЮ\' -]')
}
re_punct = re.compile(r'[\.,!?"«»“”…:;–—―-]+')
re_whitespace = re.compile(r'[\s-]+')
re_leading = re.compile(r'^[\'-]+')
re_trailing = re.compile(r'[\'-]+$')


def strip_accents(s):
    t =  ''.join(c for c in unicodedata.normalize('NFD', s)
                 if unicodedata.category(c) != 'Mn' or unicodedata.name(c) == 'COMBINING BREVE')
    t = t.replace("й", "й")
    return t


def keep_useful_characters(sentence, utterance_id='sentence'):
    s = sentence.lower()
    s = s.replace('’', "'")
    s = s.replace('`', "'")
    s = s.replace('՚', "'")
    s = re_punct.sub(' ', s)
    s1 = s
    s1 = strip_accents(s1)
    s = alphabet_filter['cyr'].sub('', s1)
    if s1 != s:
        logger.warning('skipping {} with latin text: |{}|{}|', utterance_id, (sentence, s1), s)
        return None
    s = re_whitespace.sub(' ', s)
    s = re_leading.sub('', s)
    s = re_trailing.sub('', s)
    s = s.strip()
    return s


class Verbalizer:
    def __init__(self):
        self.nlp = stanza.Pipeline('uk', processors='tokenize,pos')
        
    def forward(self, text, *, utterance_id='sentence'):
        text = ftfy.fix_text(text) # unicode
        text = keep_useful_characters(text, utterance_id=utterance_id)

        if text is None:
            return None
        else:
            words = [keep_useful_characters(t, utterance_id=utterance_id)
                        for t in text.split()]
            
            return words

        if False: # this path is way too slow
            doc = self.nlp(text)

            words = []
            for sentence in doc.sentences:
                for word in sentence.words:
                    if word.upos == "PUNCT":
                        continue
                    # XXX: гнат юра юрА Юра
                    if len(word.text) > 1 and word.text.upper() == word.text:
                        words.append(word.text)
                    else:
                        words.append(word.text.lower())

            return ' '.join(words)

# TODO: БПЛА -> бе пе ел а



if __name__ == '__main__':
    import sys

    for line in sys.stdin:
        utt_id, text = line.strip().split(maxsplit=1)
        print(utt_id, keep_useful_characters(text))

