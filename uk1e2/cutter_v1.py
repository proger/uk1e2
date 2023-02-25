"""
Dependencies:
pip install pydub==0.25.1
"""

"""
Ідея така: вирівнюємо аудіо та текст, вирізаємо аудіо по першому таймстемпу слова на початку і останньому в кінці
Опціонально перевіряємо щоб було хоч два слова підряд
Приклад аутпуту для одного файлу можна отримати на align.wilab.org.ua
"""




import json
from pprint import pprint
from pydub import AudioSegment
from pathlib import Path
import os
def trim_tails(full_transcript, start_text_offset, end_text_offset, words):

    is_len_more_0 = True
    audio_part_trimmed = {}

    # find new start_text_offset

    # вважаю,щоб перевірити, що початок синтагми збігається з початком речення,
    # потрібно перевірити другий символ, повертаючись назад, оскільки першим буде пробіл
    if full_transcript[start_text_offset - 2] not in ('.', '!', '?', '='):
        start_idx = 0
        text_len = end_text_offset - start_text_offset
        for i in range(end_text_offset):
            start_idx += 1
            text_len -= 1
            if text_len <= 0:
                is_len_more_0 = False
                break
            if full_transcript[i+start_text_offset] in ('.', '!', '?'):
                break
        # вважаю, що після крапки стоїть пробіл. Слово наступного речення починається після пробілу
        if is_len_more_0:
            start_text_offset += start_idx + 1

    # find new end_text_offset

    # перевіряю чи наступний символ крапка, чи збігається синтагма з кінцем речення
    # треба ще розглянути абзац
    if full_transcript[end_text_offset] not in ('.', '!', '?') and is_len_more_0:
        for i in range(end_text_offset, 0, -1):
            text_len = end_text_offset - start_text_offset
            if text_len <= 0:
                is_len_more_0 = False
                break
            if full_transcript[i] in ('.', '!', '?'):
                break
            end_text_offset -= 1

    if is_len_more_0:
        # trimming process
        start_audio_part = 0
        end_audio_part = 0
        gained_words = []
        start = False
        if is_len_more_0:
            for i, x in enumerate(words):
                if x['startOffset'] == start_text_offset:
                    start_audio_part = x['start']
                    start = True
                if start:
                    gained_words.append(x['word'])
                if x['endOffset'] == end_text_offset:
                    end_audio_part = x['end']
                    break

        dur = end_audio_part - start_audio_part
        print(f'DURATION: {dur}')

        # add modified dates to audio_part_trimmed dict
        audio_part_trimmed = {
            'start': start_audio_part,
            'start_ms': start_audio_part * 1000,
            'end': end_audio_part,
            'end_ms': end_audio_part * 1000,
            'start_text': start_text_offset,
            'end_text': end_text_offset,
            'transcript': ' '.join(gained_words),
            'transcript_original': full_transcript[start_text_offset: end_text_offset],
        }
    return audio_part_trimmed


def extract_segments(output_data_dir: Path, source_webm_file: Path, source_json_file: Path):
    # Get file name
    basename = os.path.basename(source_webm_file)
    filename, _ = os.path.splitext(basename)

    # Load the file
    audio_file = AudioSegment.from_file(source_webm_file)
    print(audio_file)

    # Load the JSON metadata
    with open(source_json_file) as x:
        metadata = json.loads(x.read())
        words = metadata['words']

    # Our container for audio parts
    audio_parts = []

    # Analyze metadat from Gentle
    # pprint(words)
    start_audio_part = 0
    end_audio_part = 0
    start_text_offset = 0
    end_text_offset = 0
    # gained_words = []
    not_found_words_min = 2
    not_found_words_counter = 0
    is_finish_word = False
    dur = 0
    is_more_30 = False

    for idx, word in enumerate(words):
        # Set is_finish_word to True if we reached the end
        if idx == len(words) - 1:
            is_finish_word = True
        # set the beginning of a segement
        if word['case'] == 'success' and word['alignedWord'] != '<unk>':
            if start_audio_part == 0:
                start_audio_part = word['start']
                start_text_offset = word['startOffset']
            end_audio_part = word['end']
            end_text_offset = word['endOffset']
            # gained_words.append(word['word'])
            dur = end_audio_part - start_audio_part
            if dur > 30:
                is_more_30 = True

        # catch the end of a segment
        if start_audio_part != 0 and end_audio_part != 0 and word['case'] == 'not-found-in-audio':
            # set the end when counter reached the limit "not_found_words_min"
            if not_found_words_counter >= not_found_words_min:
                full_transcript = metadata['transcript']
                audio_part_trimmed = trim_tails(
                    full_transcript, start_text_offset, end_text_offset, words)
                if len(audio_part_trimmed) != 0:
                    audio_parts.append(audio_part_trimmed)
                # Reset start/end audio parts variables
                dur = 0
                start_audio_part = 0
                end_audio_part = 0
                start_text_offset = 0
                end_text_offset = 0
                # gained_words = []
                not_found_words_counter = 0
                is_more_30 = False
            else:
                # Increment counter
                not_found_words_counter += 1

        if start_audio_part != 0 and end_audio_part != 0 and is_more_30:
            # At the end we add it ot our audio parts
            full_transcript = metadata['transcript']
            audio_part_trimmed = trim_tails(
                full_transcript, start_text_offset, end_text_offset, words)
            if len(audio_part_trimmed) != 0:
                audio_parts.append(audio_part_trimmed)
            # Reset start/end audio parts variables
            dur = 0
            start_audio_part = 0
            end_audio_part = 0
            start_text_offset = 0
            end_text_offset = 0
            # gained_words = []
            not_found_words_counter = 0
            is_more_30 = False

        if start_audio_part != 0 and end_audio_part != 0 and is_finish_word:
            # At the end we add it ot our audio parts
            full_transcript = metadata['transcript']
            audio_part_trimmed = trim_tails(
                full_transcript, start_text_offset, end_text_offset, words)
            if len(audio_part_trimmed) != 0:
                audio_parts.append(audio_part_trimmed)

    # We extract audio parts and save them into inpedendent files
    for idx, audio_part in enumerate(audio_parts):
        # Do not save empty transcripts
        if not audio_part['transcript_original']:
            continue

        # TODO: add skipping long segments (> 30s)

        # get audio part from the original file
        audio_segment = audio_file[audio_part['start_ms']
            : audio_part['end_ms']]

        # set filenames
        audio_part['save_as_audio'] = f"{output_data_dir}/{filename}_{idx}.wav"
        audio_part['save_as_txt'] = f"{output_data_dir}/{filename}_{idx}.txt"

        # save audio
        audio_segment.export(audio_part['save_as_audio'], format="wav")

        # save text
        with open(audio_part['save_as_txt'], 'w') as x:
            fixed_transcript = audio_part['transcript_original'].replace(
                '\n', ' ')
            x.write(fixed_transcript)
        print()
        print()
        pprint(audio_part)
        dur = audio_part['end'] - audio_part['start']
        print(dur)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="""\
    Extract each segment as its own wav into the new data directory.
    python3 cutter.py -o segments -w ./data/130571196.webm -j ./data/130571196.json
    """, formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('-o', '--output-data-dir', type=Path)
    parser.add_argument('-w', '--source-webm-file', type=Path)
    parser.add_argument('-j', '--source-json-file', type=Path)

    args = parser.parse_args()

    extract_segments(args.output_data_dir,
                     args.source_webm_file, args.source_json_file)
