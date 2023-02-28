"""
Prepare Hugging Face-compatible audio dataset for training using Kaldi
"""

from collections import defaultdict, Counter
from pathlib import Path
from typing import Dict, Set, Tuple

import datasets
from loguru import logger
from sqlite_utils import Database
from tqdm import tqdm


from .phonetisaurus import g2p_batch
#from uk.g2p import g2p_batch
from .tokenize_text import Verbalizer


def write_segments(segments: Dict[str, Tuple[str, float, float]], filename: Path):
    with open(filename, 'w') as f:
        for utterance_id in sorted(segments):
            recording_id, start, end = segments[utterance_id]
            print(utterance_id, recording_id, start, end, file=f)


def write_scp(scp: Dict[str, str], filename: Path):
    with open(filename, 'w') as f:
        for key in sorted(scp):
            print(key, scp[key], file=f)


def write_spk2utt(spk2utt: Dict[str, Set[str]], datadir: Path):
    with open(datadir / 'spk2utt', 'w') as f:
        for speaker_id in sorted(spk2utt):
            print(speaker_id, end='', file=f)
            for utterance_id in sorted(spk2utt[speaker_id]):
                print('', utterance_id, end='', file=f)
            print(file=f)


verbalizer = Verbalizer()

def verbalize(sample):
    utterance_id = sample['id']
    normalized_text = sample['normalized_text']
    sample['words'] = verbalizer.forward(normalized_text, utterance_id=utterance_id)
    return sample


def prepare(dataset, datadir):
    datadir.mkdir(exist_ok=True, parents=True)
    (datadir / 'wav').mkdir(exist_ok=True)

    db = Database(datadir / 'db.sqlite', recreate=True)

    text = {}
    utt2spk = {}
    spk2utt = defaultdict(set)
    wavscp = {}
    segments = {}
    lexicon = defaultdict(dict)

    samples = []

    for sample in tqdm(dataset):
        utterance_id = sample['id']
        words = sample['words']
        
        if words is None:
            continue

        sample['kaldi_text'] = text[utterance_id] = ' '.join(words)
        utt2spk[utterance_id] = sample['speaker_id']
        spk2utt[sample['speaker_id']].add(sample['id'])

        start, end = sample['start'], sample['end']

        recording_id = sample['id'].split('-')[1] # speaker-recoding-utt-start-end
        wavscp[recording_id] = sample['recording_path']
        segments[utterance_id] = (recording_id, start, end)

        #logger.debug('utt {}', sample)
        samples.append(sample)

        for word in words:
            if not word in lexicon:
                lexicon[word] = {}

    db['utterances'].insert_all(samples, pk='id')

    logger.debug("estimating lexicon")
    oov = g2p_batch(lexicon)
    for word in oov:
        for pron in oov[word]:
            lexicon[word][pron] = True
    logger.info('learned {} new words', len(lexicon))

    db['utterances'].enable_fts(['text', 'normalized_text', 'kaldi_text'])

    write_scp(text, datadir / 'text')
    write_scp(utt2spk, datadir / 'utt2spk')
    write_spk2utt(spk2utt, datadir)
    write_scp(wavscp, datadir / 'wav.scp')
    if segments:
        write_segments(segments, datadir / 'segments')
    write_scp(Counter(verbalizer.vocabulary.unk), datadir / 'unk.txt')
    write_scp(Counter([word for word in lexicon if not lexicon[word]]), datadir / 'g2p.errors')

    with open(datadir / 'lexicon.txt', 'w') as lexicon_txt:
        for word in lexicon:
            for pron in lexicon[word]:
                print(word, pron, file=lexicon_txt)
    
    with open(datadir / 'words.txt', 'w') as words_txt:
        for word in sorted(lexicon):
            print(word, file=words_txt)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(__file__, description='prepare kaldi data directory with a speech dataset from Hugging Face',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--root', type=Path, default=Path('data'),
                        help='where to put {lang}/test and {lang}/train datadirs')
    parser.add_argument('local_utterances', help='make local_utterances.json')
    args = parser.parse_args()

    logger.info('{}', args)

    dataset = datasets.load_dataset('json', data_files=args.local_utterances, split='train')

    datadir = args.root / 'local'
    logger.info('writing to {}', datadir)

    dataset = dataset.map(verbalize, load_from_cache_file=False)
    prepare(dataset, datadir)
