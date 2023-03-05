import torchaudio

from datasets import load_dataset

# file with our dataset
csv_test_file = 'segments_filtered.csv'

# where to save the cached dataset
cache_folder = 'segment.data'

# number of processes to use
processes = 5

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
ds = load_dataset('csv', data_files=csv_test_file)['train']

# process the dataset
ds = ds.map(map_to_array, keep_in_memory=False, num_proc=processes)

# save the cached dataset to the disk
ds.save_to_disk(cache_folder)

print('Finished.')
