import re
import os

import whisper
import numpy as np
import scipy.io.wavfile as wavfile

from tempfile import NamedTemporaryFile
from datasets import load_metric, load_from_disk

cached_dataset = 'segment.data'

# the name of a Whisper model
model_name = 'large-v2'

# a filename where to save results
save_to = 'whisper_large_v2.txt'

# how many files to inference in a batch
batch_size = 16

# load the model
model = whisper.load_model(model_name)

# load scripts to count metrics
wer = load_metric("wer.py")
cer = load_metric("cer.py")


def only_uk_sentence(v):
    char_set_lower = 'а, б, в, г, ґ, д, е, є, ж, з, и, і, ї, й, к, л, м, н, о, п, р, с, т, у, ф, х, ц, ч, ш, щ, ь, ю, я'.replace(',','').replace(' ', '')
    char_set_upper = char_set_lower.upper()
    char_set = char_set_lower + char_set_upper
    char_set = char_set + '—,!?' + "'" + ' '

    return all((True if x in char_set else False for x in v))


def map_to_pred(batch):
    tmp_files = []

    # Whisper takes files as input so we need to save batches into files
    # and then to use them during inference
    for speech in batch["speech"]:
        with NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            wavfile.write(tmp.name, 16000, np.array(speech))
            tmp_files.append(tmp.name)

    # do inference
    results = []
    for idx, f in enumerate(tmp_files):
        result = model.transcribe(f, language='uk')

        results.append(result["text"])

    # some corrections
    batch["predicted"] = [it.replace('’', "'").strip().lower().replace(',','').replace('.','').replace('?','').replace('!','') for it in results]
    batch["target"] = [it.strip() for it in batch["text"]]

    # filter out incorrect samples
    checked_preds = []
    checked_gt = []
    for idx, pred in enumerate(batch["predicted"]):
        has_num = bool(re.search(r'\d', pred))
        only_uk = only_uk_sentence(pred)

        if not has_num and only_uk:
            checked_preds.append(pred)
            checked_gt.append(batch["target"][idx])

    batch["predicted"] = checked_preds
    batch["target"] = checked_gt

    # append the results
    with open(save_to, 'a') as wr:
        for idx, row in enumerate(batch['predicted']):
            target = batch['target'][idx]
            path = batch['path'][idx].split('/')[-1].replace('.wav', '')

            wer_value = round(wer.compute(predictions=[row], references=[target]), 4)
            cer_value = round(cer.compute(predictions=[row], references=[target]), 4)

            wr.write(f'{path}|{target}|{row}|{wer_value}|{cer_value}\n')

    # remove temporary files
    for f in tmp_files:
        os.unlink(f)

    return batch


# do inference
ds = load_from_disk(cached_dataset)
ds.map(map_to_pred, batched=True, batch_size=batch_size, remove_columns=list(ds.features.keys()))
