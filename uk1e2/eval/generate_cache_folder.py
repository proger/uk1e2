import os
import torchaudio

from datasets import load_dataset

# where to save the cached dataset
cache_folder = 'segment.data'

# number of processes to use
processes = os.cpu_count() or 1

def add_paths(example):
    path = f"data/segments/wav/{example['id']}.wav"
    example["path"] = path
    return example

def path_exists(example):
    return os.path.exists(example["path"])

def map_to_array(batch):
    path = batch["path"]
    speech, sampling_rate = torchaudio.load(path)
    if sampling_rate != 16_000:
        resampler = torchaudio.transforms.Resample(orig_freq=sampling_rate, new_freq=16_000)
        batch["speech"] = resampler.forward(speech.squeeze(0)).numpy()
    else:
        batch["speech"] = speech.squeeze(0).numpy()
    batch["lengths"] = len(batch["speech"])
    return batch

# load the dataset
ds = load_dataset('json', data_files={'test': 'local_utterances.jsonl'})['test']

# process the dataset
ds = ds.map(add_paths).filter(path_exists).map(map_to_array, keep_in_memory=False, num_proc=processes)

# save the cached dataset to the disk
ds.save_to_disk(cache_folder)

print('Finished.')
