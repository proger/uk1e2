"""
Download all files locally
"""

import requests
import json
from os.path import exists

LOGIN = '****'
PASSWORD = '****'

FILES_PATH = './files'

def download_file(url, local_filename):
    with requests.get(url, auth=(LOGIN, PASSWORD), stream=True) as r:
        r.raise_for_status()
        with open(local_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192): 
                f.write(chunk)
    return local_filename

# load index
with open('./uk1e2/news/index.json') as f:
    index = json.loads(f.read())

# iterate over rows
for row in index['rows']:
    id, channel, title, date, duration, file_url, type_url = row
    json_metadata = f'./uk1e2/news/align/{id}.json'

    # Check the metadata file with alignment
    if not exists(json_metadata):
        print(f'File {json_metadata} does not exist')
        continue

    # Download the file to local filesystem
    download_url = file_url.replace('wavesurfer', 'file')
    local_filename = f'{FILES_PATH}/{id}.webm'

    if exists(local_filename):
        print(f'Local file {json_metadata} already exists')
        continue

    download_file(download_url, local_filename)