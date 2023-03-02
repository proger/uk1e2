import argparse
from pathlib import Path

from loguru import logger

from .tokenize_text import Verbalizer

parser = argparse.ArgumentParser(__file__, description='gather whisper results into kaldi format',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('whisper_folder', help='folder where whisper txts are', type=Path)
args = parser.parse_args()

logger.info('{}', args)


verbalizer = Verbalizer()

def verbalize(utt_file: Path):
    whisper_text = utt_file.read_text().replace('\n', ' ')
    words = verbalizer.forward(whisper_text, utterance_id=utt_file.stem)
    return ' '.join(words)

for utt in args.whisper_folder.glob('*.wav.txt'):
    print(utt.stem.replace('.wav', ''), verbalize(utt))
