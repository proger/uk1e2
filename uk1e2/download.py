from dataclasses import dataclass, field, asdict
import csv
import json
import os
from pathlib import Path
import requests
import subprocess
import sys

import yt_dlp

from typing import List, Dict, AnyStr, Iterable

from .text import Verbalizer


@dataclass
class Utterance:
    recording_id: str
    id: str = field(init=False)
    text: str
    normalized_text: str
    start: float
    end: float
    speaker_id: str
    utterance_id: str
    domain: str
    source: str
    utterance_url: str
    recording_path: str

    def __post_init__(self):
        s, e = self.start, self.end
        self.id = f'{self.recording_id}-{int(s*100):07d}-{int(e*100):07d}'



def make_recording_id(x):
    x = x.replace('.', '0')
    x = x.replace('-', '0') # dashes confuse kaldi when segments or speakers are used
    x = x.rjust(11, '0') # pad all names to match length of youtube ids
    return x


@dataclass
class Record:
    name: str = ''
    path: str = ''
    utterances: List[Utterance] = field(default_factory=list)
        
    def add_utterance(self, s: Utterance):
        self.utterances.append(s)
    
    def to_text(self, allow_multiline=True):
        t = ""
        sep = "\n" if allow_multiline else " "
        for s in self.utterances:
            t += (sep if t else "") + s.text
        if not allow_multiline:
            t = t.replace("\n", " ")
        return t
    
    def compute_duration(self):
        cmd = "ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1".split()
        return subprocess.check_output(cmd + [self.path])



class Corpus:
    def __init__(self, root: Path):
        self.root = root
        self.records: List[Record] = []
        self.url2record: Dict[str, Record] = {}
        self.id_to_record: Dict[str, Record] = {}
        
    def add_record(self, r: Record):
        self.records.append(r)
    
    def record_by_url(self, url: str, allow_create_new=True):
        r = self.url2record.get(url, Record() if allow_create_new else None)
        if r is not None and allow_create_new:
            self.url2record[url] = r
        return r
    
    @staticmethod
    def _parse_utterance_url(segment_url: str):
        url, params = segment_url.split("?", 1)
        return url, params
        
    def from_csv(self, lines: Iterable[List[AnyStr]]):
        audio_ext = ".m4a"
        for i, line in enumerate(lines):
            if i == 0: # ignore header
                continue

            rowid, domain, source, utterance_id, start_time, \
                speaker_id, text, normalized_text, start, end, utterance_url = line

            record_url, params = self._parse_utterance_url(utterance_url)

            r = self.record_by_url(record_url, allow_create_new=True)

            if r.name == "":  # a new record
                r.name = make_recording_id(source)
                if "youtu" in record_url:
                    r.path = self.root / (source + audio_ext)
                    if not r.path.exists():
                        yt_dl(record_url, self.root)
                else:
                    download(record_url, self.root, r.name, audio_ext)
                    r.path = self.root / (r.name + audio_ext)

                self.id_to_record[r.name] = r
                print(f"new record {len(self.id_to_record)} url={record_url} name={r.name}", file=sys.stderr)

            if end == "":
                end = r.compute_duration() # end is missing for some final utterances: guess from file duration

            # TODO: properly align start/end of utterances
            s = Utterance(recording_id=r.name, text=text, normalized_text=normalized_text, start=float(start), end=float(end),
                          speaker_id=speaker_id, utterance_id=utterance_id, domain=domain, source=source,
                          utterance_url=utterance_url, recording_path=str(r.path))

            r.add_utterance(s)


def download(url: str, dest_folder: Path, stem: str, audio_ext=".m4a"):
    dest_folder.mkdir(exist_ok=True)

    target_audio_path = dest_folder / (stem + audio_ext)
    if target_audio_path.exists():
        return

    filename = url.split('/')[-1].replace(" ", "_")  # be careful with file names
    file_path = dest_folder / filename
    if not file_path.exists():
        r = requests.get(url, stream=True)
        if r.ok:
            print("saving to", file_path.absolute(), file=sys.stderr)
            with open(file_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024 * 2):  # 1024 * 8
                    if chunk:
                        f.write(chunk)
                        f.flush()
                        os.fsync(f.fileno())
        else:
            raise ConnectionError("Download failed: status code {}\n{}".format(r.status_code, r.text))

    to_audio(file_path, target_audio_path, clean_video_on=True)
    if not target_audio_path.exists():
        raise FileNotFoundError("extracting audio did not word")


def yt_dl(url, dir: Path):
    ydl_opts = {
        'format': 'm4a/bestaudio/best',
        'outtmpl': os.path.join(dir, "%(id)s.%(ext)s"),  # 'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
        # ℹ️ See help(yt_dlp.postprocessor) for a list of available Postprocessors and their arguments
        'postprocessors': [{  # Extract audio using ffmpeg
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'm4a',
        }]
    }
    urls = url if isinstance(url, list) else [url]

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        error_code = ydl.download(urls)
        print(f"Downloaded with code: {error_code}", file=sys.stderr)
        return error_code


def to_audio(v: Path, a: Path, clean_video_on=False):
    cl = ["ffmpeg", "-i", str(v), "-vn", "-acodec", "copy", str(a)]
    print(f"Converting to audio by command: {' '.join(cl)}", file=sys.stderr)
    try:
        output = subprocess.run(cl, capture_output=True)
        text_output = output.stderr.decode("utf-8")  #.split("\n")
        if clean_video_on:
            v.unlink()
    except:
        print(f"ERROR converting to audio: {v} --> {a}.\n  Lines:\n    {text_output}", file=sys.stderr)


def main():
    csv_path = Path(sys.argv[1] if len(sys.argv) > 1 else "utterances.csv")
    corpus_dir = Path(sys.argv[2] if len(sys.argv) > 2 else "data/corpus")
    corpus_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Reading {csv_path} and storing downloaded audio in {corpus_dir}", file=sys.stderr)
    corpus = Corpus(corpus_dir)
    with open(csv_path) as csv_file:
        corpus.from_csv(csv.reader(csv_file, delimiter=','))
 
    for recording_id, record in corpus.id_to_record.items():
        for segment in record.utterances:
            print(json.dumps(asdict(segment), ensure_ascii=False))


if __name__ == '__main__':
    main()
