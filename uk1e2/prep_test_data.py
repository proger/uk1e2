from dataclasses import dataclass
import csv
import os
import requests
import subprocess
import sys

# Python code to convert video to audio
import moviepy.editor as mp
import yt_dlp
# from pytube import YouTube

from typing import List, Dict, AnyStr, IO, Union, Iterable

@dataclass(frozen=True)
class Segment:
    text: str
    start: float
    end: float
    spk: str
    location: str
        
    @staticmethod
    def from_csv_line_list(line: List[AnyStr]):
        rowid, domain, source, utterance_id, start_time, speaker_id, text, normalized_text, start, end, url = line
        s = Segment(normalized_text or text, start, end, speaker_id, url)
        return s


def make_name(x):
    x = x.replace('.', '0')
    x = x.replace('-', '0')
    x = x.rjust(11, '0') # pad all names to match length of youtube ids
    return x


class Record:
    def __init__(self, name="", path=""):
        self.name = name
        self.path = path
        self.segments: List[Segment] = []
        
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


class Corpus:
    def __init__(self, root=""):
        self.root = root
        self.records: List[Record] = []
        self.url2record: Dict[str, Record] = {}
        self.lab2record: Dict[str, Record] = {}
        
    def add_record(self, r: Record):
        self.records.append(r)
    
    def record_by_url(self, url:str, allow_create_new=True):
        r = self.url2record.get(url, Record() if allow_create_new else None)
        if r is not None and allow_create_new:
            self.url2record[url] = r
        return r
    
    @staticmethod
    def _parse_record_url(segment_url: str):
        url, params = segment_url.split("?", 1)
        return url, params
        
    # @staticmethod
    def update_by_csv_reader(self, lines: Iterable[List[AnyStr]], max_items=-1, ignore_errors=True):
        # rowid,domain,source,utterance_id,start_time,speaker_id,text,start,end,url
        head={}
        audio_ext = ".m4a"
        for i, line in enumerate(lines):
            if i==0:
                head = {s: j for j,s in enumerate(line)}  # TODO: use header information
                continue
            s = Segment.from_csv_line_list(line)
            try:
                record_url, params = self._parse_record_url(s.location)
            except ValueError:
                print('suspicious segment', s)
                raise
            r = self.record_by_url(record_url, allow_create_new=True)
            result_code = 0
            if r.name == "":  # a new record
                print(f"Creating a new record by url: {record_url}", file=sys.stderr)
                r.name = make_name(line[2])
                r.path = os.path.join(self.root, r.name + audio_ext)
                if "youtu" in record_url:
                    result_code = yt_dl(record_url, self.root)
                else:
                    result_code = download(record_url, self.root, r.name, audio_ext)
                if result_code == 0:
                    # TODO: check the label is unique
                    self.lab2record[r.name] = r
                    print(f"Added a new, {len(self.lab2record)}-th, record named: {r.name}", file=sys.stderr)
            if result_code == 0:
                    r.add_segment(s)
            else:
                print(f"FATAL ERROR: while trying to append record: {record_url} with params: {params}. \nExiting.", file=sys.stderr)
                if not ignore_errors:
                    break
            if 0 < max_items < i:
                print(f"Reached maximum items for updating: {i}", file=sys.stderr)
                break

    def write_labeled_text(self, path: str):
        with open(path, "wt") as f:
            for label, r in self.lab2record.items():
                t = r.to_text(allow_multiline=False)
                print(label + " " + t, file=f)


    def write_scp(self, path: str):
        # ffmpeg -i file.mkv -ss 20 -to 40 -f wav -
        with open(path, "wt") as f:
            for label, r in self.lab2record.items():
                path = r.path
                command = f"{label} ffmpeg -i \"{path}\" -f wav -ac 1 -acodec pcm_s16le -ar 16000 - |"
                print(command, file=f)


def download(url: str, dest_folder: str, stem: str, audio_ext=".m4a"):
    if not os.path.exists(dest_folder):
        os.makedirs(dest_folder)  # create folder if it does not exist

    target_audio_path = os.path.join(dest_folder, stem + audio_ext)
    if os.path.isfile(target_audio_path):
        print(f"Audio - {target_audio_path} - is already prepared.", file=sys.stderr)
        return 0

    filename = url.split('/')[-1].replace(" ", "_")  # be careful with file names
    file_path = os.path.join(dest_folder, filename)
    if not os.path.isfile(file_path):
        r = requests.get(url, stream=True)
        if r.ok:
            print("saving to", os.path.abspath(file_path), file=sys.stderr)
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
    return 0 if os.path.isfile(target_audio_path) else -1


def yt_dl(url, dir="data"):  # TODO: where!!!!!!!!!!!!!
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
    return -1


def to_audio(v: str, a: str, clean_video_on=False):
    cl = ["ffmpeg", "-i", v, "-vn", "-acodec", "copy", a]
    print(f"Converting to audio by command: {' '.join(cl)}", file=sys.stderr)
    try:
        output = subprocess.run(cl, capture_output=True)
        text_output = output.stderr.decode("utf-8")  #.split("\n")
        if clean_video_on:
            os.remove(v)
    except:
        print(f"ERROR converting to audio: {v} --> {a}.\n  Lines:\n    {text_output}", file=sys.stderr)


def to_audio2(v: str, a: str):
    # Insert Local Video File Path 
    clip = mp.VideoFileClip(v)
    
    # Insert Local Audio File Path
    clip.audio.write_audiofile(a)

def main():
    if len(sys.argv) < 3:
        print(f"Read csv-file, download/covert audio and write necessary info", file=sys.stderr)
        print(f"", file=sys.stderr)
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "utterances.csv"
    corpus_dir = sys.argv[2] if len(sys.argv) > 2 else "data/corpus"
    result_dir = sys.argv[3] if len(sys.argv) > 3 else "data/local"
    os.makedirs(corpus_dir, exist_ok=True)
    
    print(f"Read {csv_path}, download/covert audio to {corpus_dir} and write info to {result_dir}", file=sys.stderr)
    print(f"Downloading media files (and convert them to audio m4a format) to: {corpus_dir}", file=sys.stderr)
    corpus = Corpus(corpus_dir)
    with open(csv_path) as csv_file:
        csv_read=csv.reader(csv_file, delimiter=',')
        corpus.update_by_csv_reader(csv_read, max_items=-1)
    
    print(f"Writing corpus local descriptions to: {result_dir}", file=sys.stderr)
    os.makedirs(result_dir, exist_ok=True)
    corpus.write_scp(os.path.join(result_dir, "scp"))
    corpus.write_labeled_text(os.path.join(result_dir, "text"))
    return

if __name__ == '__main__':
    main()
