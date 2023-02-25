import sys
import pandas as pd

unnormalized = pd.read_csv(sys.argv[1], sep=';')
normalized   = pd.read_csv(sys.argv[2], sep=';')

df = pd.concat([unnormalized, normalized], axis=1)

df = df[['domain', 'source', 'utterance_id', 'start_time', 'speaker_id', 'text', 'normalized_text']]
df.to_json(sys.stdout, orient='records', lines=True, force_ascii=False)
