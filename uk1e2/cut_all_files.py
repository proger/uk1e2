import subprocess
import json
import os
from os.path import exists

FILES_PATH = './files'

# load index
with open('./uk1e2/news/index.json') as f:
    index = json.loads(f.read())

# iterate over rows
for row in index['rows']:
    id, channel, title, date, duration, file_url, type_url = row

    json_metadata = f'./uk1e2/news/align/{id}.json'
    if not exists(json_metadata):
        continue

    audio_local_filename = f'{FILES_PATH}/{id}.webm'
    if not exists(audio_local_filename):
        continue

    # print(json_metadata)
    # print(audio_local_filename)
    # print('---')

    segments_folder = f'segments/{id}'

    if exists(segments_folder):
        print(f'Already processed: {segments_folder}')
        continue

    os.makedirs(segments_folder)

    bashCommand = ' '.join([
        '/opt/miniconda3/bin/python',
        '/Users/yehorsmoliakov/Work/irtc/cut-gentle-files/cutter_v3.py',
        '-o',
        segments_folder,
        '-w',
        audio_local_filename,
        '-j',
        json_metadata,
    ])
    process = subprocess.Popen(bashCommand.split(), stdout=subprocess.PIPE)
    output, error = process.communicate()

    if error:
        print('*****')
        print('ERRORR!!!!!1111')
        print(error)
        print('*****')
    else:
        print('FINISHED:')
        print()
        print(bashCommand)
        # print(output)
        print('---')