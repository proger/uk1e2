import torch

from transformers import Wav2Vec2Processor, Wav2Vec2ForCTC
from datasets import load_metric, load_from_disk

cached_dataset = 'segment.data'

# the name of wav2vec2 model
model_name = 'Yehor/wav2vec2-xls-r-300m-uk-with-3gram-news-lm'

# a filename where to save results
save_to = 'wav2vec2_300m.txt'

# how many files to inference in a batch
batch_size = 16

# set the device to do inference on
device = torch.device('cuda:0')

# load the model
model = Wav2Vec2ForCTC.from_pretrained(model_name).to(device)
processor = Wav2Vec2Processor.from_pretrained(model_name)

# load scripts to count metrics
wer = load_metric("wer.py")
cer = load_metric("cer.py")

def map_to_pred(batch):
    # do inference
    features = processor(batch['speech'], sampling_rate=16_000, padding=True, return_tensors='pt')
    input_values = features.input_values.to(device)
    attention_mask = features.attention_mask.to(device)

    with torch.no_grad():
        logits = model(input_values, attention_mask=attention_mask).logits

    predicted_ids = torch.argmax(logits, dim=-1)
    results = processor.batch_decode(predicted_ids)

    # fix apostrophe in predictions
    batch["predicted"] = results
    batch["target"] = [it.strip() for it in batch["text"]]

    # append the results
    with open(save_to, 'a') as wr:
        for idx, row in enumerate(batch['predicted']):
            target = batch['target'][idx]
            path = batch['path'][idx].split('/')[-1].replace('.wav', '')

            wer_value = round(wer.compute(predictions=[row], references=[target]), 4)
            cer_value = round(cer.compute(predictions=[row], references=[target]), 4)

            wr.write(f'{path}|{target}|{row}|{wer_value}|{cer_value}\n')

    return batch


# do inference
ds = load_from_disk(cached_dataset)
ds.map(map_to_pred, batched=True, batch_size=batch_size, remove_columns=list(ds.features.keys()))
