from collections import defaultdict
from pathlib import Path
from subprocess import check_output

from loguru import logger


def g2p_batch(words) -> dict[str, dict[str, bool]]:
    model = Path('data/local/dict/g2p.fst')
    lexicon = Path('data/local/dict/uk_pron.v3.vcb')
    if not model.exists() or not lexicon.exists():
        logger.error('g2p models not found: {} {}', model, lexicon)
        return {}
    output = check_output(['phonetisaurus', 'predict',
                           '--nbest', '2',
                           '--model', model,
                           '--lexicon', lexicon], input='\n'.join(words).encode('utf-8'))
    oov = defaultdict(dict)
    for line in output.decode('utf-8').splitlines():
        word, *pron = line.split()
        pron = ' '.join(pron)
        #logger.debug('{} {}', word, pron)
        oov[word][pron] = True
    return oov

if __name__ == '__main__':
    lexicon = {"йоулупуккі": {}}
    oov = g2p_batch(lexicon)
    print(oov)
    for word in oov:
        for pron in oov[word]:
            lexicon[word][pron] = True
    print(lexicon)
