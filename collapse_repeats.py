import json
import sys

prev_source, prev_start_time, prev_speaker = None, None, None
prev_obj = None
for line in sys.stdin:
    obj = json.loads(line)
    source, start_time, speaker = obj['source'], obj['start_time'], obj['speaker_id']

    if source == prev_source and start_time == prev_start_time and prev_speaker == speaker:
        prev_obj['text'] += "\n" + obj['text']
        print('collapsing', prev_obj['utterance_id'], obj['utterance_id'], file=sys.stderr)
    else:
        if prev_obj:
            print(json.dumps(prev_obj, ensure_ascii=False))
        prev_obj = obj

    prev_source, prev_start_time, prev_speaker = source, start_time, speaker

print(json.dumps(obj, ensure_ascii=False))
