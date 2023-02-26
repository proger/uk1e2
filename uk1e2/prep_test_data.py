from dataclasses import dataclass, field
import csv
import os
from pathlib import Path
import requests
import subprocess
import sys

import yt_dlp
from tqdm import tqdm

from typing import List, Dict, AnyStr, Iterable

from .text import Verbalizer


@dataclass(frozen=True)
class Segment:
    text: str
    start: float
    end: float
    spk: str
        
    def make_segment_id(self, recording_id):
        s, e = self.start, self.end
        return f'{recording_id}-{int(s*100):07d}-{int(e*100):07d}'



def make_recording_id(x):
    x = x.replace('.', '0')
    x = x.replace('-', '0') # dashes confuse kaldi when segments or speakers are used
    x = x.rjust(11, '0') # pad all names to match length of youtube ids
    return x


@dataclass
class Record:
    name: str = ''
    path: str = ''
    segments: List[Segment] = field(default_factory=list)
        
    def add_segment(self, s: Segment):
        self.segments.append(s)
    
    def to_text(self, allow_multiline=True):
        t = ""
        sep = "\n" if allow_multiline else " "
        for s in self.segments:
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
    def _parse_segment_url(segment_url: str):
        url, params = segment_url.split("?", 1)
        return url, params
        
    def read_csv(self, lines: Iterable[List[AnyStr]], max_items=-1, ignore_errors=True):
        audio_ext = ".m4a"
        for i, line in enumerate(lines):
            if i == 0: # ignore header
                continue

            rowid, domain, source, utterance_id, start_time, \
                speaker_id, text, normalized_text, start, end, segment_url = line

            try:
                record_url, params = self._parse_segment_url(segment_url)
            except ValueError:
                print('suspicious segment', s)
                raise

            r = self.record_by_url(record_url, allow_create_new=True)

            result_code = 0
            if r.name == "":  # a new record
                print(f"Creating a new record by url: {record_url}", file=sys.stderr)
                r.name = make_recording_id(source)
                if "youtu" in record_url:
                    result_code = yt_dl(record_url, self.root)
                    r.path = self.root / (source + audio_ext)
                else:
                    result_code = download(record_url, self.root, r.name, audio_ext)
                    r.path = self.root / (r.name + audio_ext)
                if result_code == 0:
                    # TODO: check the label is unique
                    self.id_to_record[r.name] = r
                    print(f"Added a new, {len(self.id_to_record)}-th, record named: {r.name}", file=sys.stderr)

            if end == "":
                end = r.compute_duration() # end is missing for some final utterances: guess from file duration

            # TODO: properly align start/end of utterances
            s = Segment(normalized_text or text, float(start), float(end), speaker_id)

            if result_code == 0:
                r.add_segment(s)
            else:
                print(f"FATAL ERROR: while trying to append record: {record_url} with params: {params}. \nExiting.", file=sys.stderr)
                if not ignore_errors:
                    break
            if 0 < max_items < i:
                print(f"Reached maximum items for updating: {i}", file=sys.stderr)
                break

    def write_text(self, path: str):
        verbalizer = Verbalizer()
        with open(path, "wt") as f:
            for recording_id, record in tqdm(self.id_to_record.items()):
                for segment in record.segments:
                    print(segment.make_segment_id(recording_id), verbalizer.forward(segment.text), file=f)

    def write_segments(self, path: str):
        with open(path, "wt") as f:
            for recording_id, record in self.id_to_record.items():
                for segment in record.segments:
                    print(segment.make_segment_id(recording_id), recording_id, round(segment.start, 2), round(segment.end, 2), file=f)

    def write_scp(self, path: str):
        with open(path, "wt") as f:
            for recording_id, r in self.id_to_record.items():
                path = r.path
                command = f"{recording_id} ffmpeg -i {path} -f wav -ac 1 -acodec pcm_s16le -ar 16000 - |"
                print(command, file=f)


def download(url: str, dest_folder: Path, stem: str, audio_ext=".m4a"):
    dest_folder.mkdir(exist_ok=True)

    target_audio_path = dest_folder / (stem + audio_ext)
    if target_audio_path.exists():
        print(f"Audio - {target_audio_path} - is already prepared.", file=sys.stderr)
        return 0

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
        else:  # HTTP status code 4XX/5XX
            print("Download failed: status code {}\n{}".format(r.status_code, r.text), file=sys.stderr)
            return -1
    else:
        print(f"Video - {file_path} - is already downloaded.", file=sys.stderr)
    to_audio(file_path, target_audio_path, clean_video_on=True)
    return 0 if target_audio_path.exists() else -1


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
    if len(sys.argv) < 3:
        print(f"Read csv-file, download/covert audio and write necessary info", file=sys.stderr)
        print(f"", file=sys.stderr)
    csv_path = Path(sys.argv[1] if len(sys.argv) > 1 else "utterances.csv")
    corpus_dir = Path(sys.argv[2] if len(sys.argv) > 2 else "data/corpus")
    result_dir = Path(sys.argv[3] if len(sys.argv) > 3 else "data/local")
    corpus_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Read {csv_path}, download/covert audio to {corpus_dir} and write info to {result_dir}", file=sys.stderr)
    print(f"Downloading media files (and convert them to audio m4a format) to: {corpus_dir}", file=sys.stderr)
    corpus = Corpus(corpus_dir)
    with open(csv_path) as csv_file:
        corpus.read_csv(csv.reader(csv_file, delimiter=','), max_items=-1)
    
    print(f"Writing corpus local descriptions to: {result_dir}", file=sys.stderr)
    result_dir.mkdir(parents=True, exist_ok=True)
    corpus.write_scp(result_dir / "scp")
    corpus.write_segments(result_dir / "segments")
    corpus.write_text(result_dir / "text")


if __name__ == '__main__':
    main()
