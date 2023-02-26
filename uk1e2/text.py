import stanza


class Verbalizer:
    def __init__(self):
        self.nlp = stanza.Pipeline('uk', processors='tokenize,pos')
        
    def forward(self, text):
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

# БПЛА -> бе пе ел а