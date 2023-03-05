import os
import torch

import numpy as np
import nemo.collections.asr as nemo_asr
import scipy.io.wavfile as wavfile

from tempfile import NamedTemporaryFile
from datasets import load_metric, load_from_disk

cached_dataset = 'segment.data'

# possible models:
# - theodotus/stt_uk_squeezeformer_ctc_ml
# - nvidia/stt_uk_citrinet_1024_gamma_0_25
# - theodotus/stt_uk_contextnet_512
model_name = 'nvidia/stt_uk_citrinet_1024_gamma_0_25'

# a filename where to save results
save_to = 'stt_uk_citrinet_1024_gamma_0_25.txt'

# how many files to inference in a batch
batch_size = 16

# set the device to do inference on
device = torch.device('cuda:0')

# load the model
asr_model = nemo_asr.models.EncDecCTCModel.from_pretrained(model_name, map_location=device)

# load scripts to count metrics
wer = load_metric("wer.py")
cer = load_metric("cer.py")

def map_to_pred(batch):
    tmp_files = []

    # NeMo takes files as input so we need to save batches into files
    # and then to use them during inference
    for speech in batch["speech"]:
        with NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            wavfile.write(tmp.name, 16_000, np.array(speech))
            tmp_files.append(tmp.name)

    # do inference
    results = asr_model.transcribe(tmp_files)

    # fix apostrophe in predictions
    batch["predicted"] = [it.replace('’', "'") for it in results]
    batch["target"] = [it.strip() for it in batch["text"]]

    # append the results
    with open(save_to, 'a') as wr:
        for idx, row in enumerate(batch['predicted']):
            target = batch['target'][idx]
            path = batch['path'][idx].split('/')[-1].replace('.wav', '')

            wer_value = round(wer.compute(predictions=[row], references=[target]), 4)
            cer_value = round(cer.compute(predictions=[row], references=[target]), 4)

            wr.write(f'{path}|{target}|{row}|{wer_value}|{cer_value}\n')

    # remove temporary files
    for tf in tmp_files:
        os.unlink(tf)

    return batch


# do inference
ds = load_from_disk(cached_dataset)
ds.map(map_to_pred, batched=True, batch_size=batch_size, remove_columns=list(ds.features.keys()))
