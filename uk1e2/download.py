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

from .tokenize_text import Verbalizer


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
        self.id = f'{self.speaker_id}-{self.recording_id}-{self.utterance_id}-{int(s*100):07d}-{int(e*100):07d}'


@dataclass
class Record:
    recording_url: str
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

    @staticmethod
    def make_recording_id(x, domain):
        x = x.replace('.', '0')
        x = x.replace('-', '0') # dashes confuse kaldi when segments or speakers are used
        x = x.rjust(11, '0') # pad all names to match length of youtube ids
        domain_code = {
            'Interview': 'I',
            'courses': 'C',
            'podcast': 'P',
            'youtube': 'Y',
            'news': 'N',
        }.get(domain, "")
        return f'{domain_code}{x}'

    def download_(self, root, source, domain):
        if self.name == "":  # a new record
            self.name = self.make_recording_id(source, domain)
            if "youtu" in self.recording_url:
                self.path = root / (source + '.m4a')
                if not self.path.exists():
                    yt_dl(self.recording_url, root)
                wav = self.path.with_suffix('.wav')
                if not wav.exists():
                    to_wav(self.path, wav)
                self.path = wav
            else:
                self.path = root / (self.name + '.wav')
                download_file(self.recording_url, self.path)

        """{
  "transcript": "\nКатерина КЕЛЬБУС: == Україна хоче провести мирний саміт до кінця лютого, і зробити це планують в ООН"
  "words": [
    {
      "case": "not-found-in-audio",
      "endOffset": 9,
      "startOffset": 1,
      "word": "Катерина"
    },
    {
      "alignedWord": "україна",
      "case": "success",
      "end": 1.95,
      "endOffset": 46,
      "phones": [],
      "start": 1.41,
      "startOffset": 39,
      "word": "Україна"
    }, 
    ]
    }
"""
    def from_alignment(self, ja: Dict, recording_id: AnyStr, domain="", start_utterance_id=1) -> List["Utterance"]:
        min_cut_duration = 20.  # cut whatever is reach first: duration with minimal gap or speaker turn
        utts: List["Utterance"] = []
        cur_speaker_id = cur_speaker_name = ""
        cur_speaker_name_offset = -1  # speaker name offset in transcription text
        speaker_name2id = {}
        cur_time = distance_to_prev = 0.
        utt_duration = 0.
        utt_words = []
        utt = None
        utt_start_index = -1
        cur_utterance_id = start_utterance_id
        text = ja.get("transcript", "")
        words = utts.get("words", [])
        # for i, w in enumerate(words):
        for i in range(len(words) + 1):
            w = words[i] if i < len(words) else None
            is_first_in_utt = False if i < len(words) else True
            is_last_in_utt = True if i + 1 >= len(words) else False
            if not is_last_in_utt and w["case"] == "not-found-in-audio":
                # TODO: update potential speaker name
                if cur_speaker_name_offset < 0:
                    if i == 0 or self._is_start_of_line(text, w["startOffset"]):  # check we are in line beginning
                        cur_speaker_name_offset = w["startOffset"]
                continue
            if cur_speaker_name_offset >= 0 and i > 0:  # speaker label end is detected
                cur_speaker_name = text[cur_speaker_name_offset : words[i-1][endOffset]]
                speaker_name2id[cur_speaker_name] = speaker_name2id.get(cur_speaker_name, len(speaker_name2id)+1)
                cur_speaker_name_offset = -1
                is_first_in_utt = True

            cur_time = w["end"] if w is not None else cur_time
            if utt_start_index >= 0:
                utt_duration += (w["end"] - words[utt_start_index]["start"]) if w is not None else 0
            distance_to_prev = (w["start"] - words[i-1]["end"]) if 0 < i < len(words) else 0.
            if min_cut_duration <= utt_duration and 0.1 < distance_to_prev:
                is_first_in_utt = True

            if is_first_in_utt and utt_start_index >= 0:  
                # create utt with previous words starting with utt_start_index, if utt_start_index >= 0
                start_word = words[utt_start_index]
                utt_text = self._subtext_by_json_words(text, words, utt_start_index, i)
                utt_word_sequence_text = self._subtext_by_json_words(text, words, utt_start_index, i, keep_decoration=False)
                local_speaker_id = speaker_name2id.get(cur_speaker_name, "")
                if not local_speaker_id:
                    local_speaker_id = speaker_name2id[len(speaker_name2id)+1] = len(speaker_name2id) + 1
                utt = Utterance(recording_id=self.name, text=utt_text, normalized_text=utt_word_sequence_text, 
                                start=start_word["start"], end=cur_time,
                            speaker_id=self.get_global_speaker_id(self.name, str(local_speaker_id)),
                            utterance_id=f'U{int(cur_utterance_id):07d}', domain=domain, source=recording_id,
                            utterance_url=self.recording_url, recording_path=self.path)
                self.add_utterance(utt)
                cur_utterance_id += 1
                utt_start_index = i
            
    @staticmethod
    def _subtext_by_json_words(text: str, words: List[Dict], start: int, stop: int, *, retain_skipped=False, keep_decoration=True):
        result = ""
        for i in range(start, stop):
            w = words[i]
            next_word = words[i+1] if i+1 < len(words) else None
            if w["case"] == "not-found-in-audio":
                if not retain_skipped:
                    continue
            t = text[w["startOffset"] : next_word["startOffset"] if next_word is not None else len(text)] if keep_decoration else (w["alignedWord"] + " ")
            result += t
        return result
            
    
    @staticmethod
    def _is_start_of_line(text: str, i: int):
        i -= 1
        while i >= 0:
            c = text[i]
            if not c.isspace():
                return False
            if c == "\n":
                return True
            i -= 1
        return False if i >= 0 else True


class Corpus:
    def __init__(self, root: Path):
        self.root = root
        self.url2record: Dict[str, Record] = {}
        self.speakers = {}
        
    def get_global_speaker_id(self, recording_id, speaker_id):
        key = (recording_id, speaker_id)
        if not key in self.speakers:
            self.speakers[key] = len(self.speakers)
        return f'S{self.speakers[key]:05d}' 
    
    def globalize_speaker_ids(self):
        for recording_id, record in self.url2record.items():
            for utt in record.utterances:
                global_speaker_id = self.get_global_speaker_id(recording_id, utt.speaker_id)
                utt.speaker_id = global_speaker_id
    
    def record_by_utterance_url(self, utterance_url: str):
        recording_url, _ = utterance_url.split("?", 1)
        if not recording_url in self.url2record:
            self.url2record[recording_url] = Record(recording_url=recording_url)
        return self.url2record[recording_url]
        
    def from_dir(self, dir_path: AnyStr, domain="news"):
        # {"recording_id": "Ro0dlb0_0VeI", "id": "S00250-Ro0dlb0_0VeI-U0107190-0121300-0121300", "text": "Угу", "normalized_text": "Угу", "start": 1213.0, "end": 1213.0, "speaker_id": "S00250", "utterance_id": "U0107190", "domain": "youtube", "source": "o0dlb0_-VeI", "utterance_url": "https://www.youtube.com/embed/o0dlb0_-VeI?start=1213&end=1213", "recording_path": "data/corpus/o0dlb0_-VeI.wav"}
        # read urls from dir_path/urls
        with open(os.path.join(dir_path, "urls")) as urls:
            utt_count = 0
            for url in urls:
                url = url.strip()
                name = os.path.basename(url)
                stem, ext = os.path.splitext(name)
                # record_id = record_id_prefix + stem
                align_path = os.path.join(dir_path, "align", stem + "json")
                with open(align_path) as f:
                    aj = json.loads(f.read())  # alignment json
                    r = Record(recording_url=url, name=Record.make_recording_id(stem, domain))
                    r.from_alignment(aj, start_utterance_id=utt_count)
                    utt_count += len(r.utterances)
            self.globalize_speaker_ids()  # update speaker ids

        
    def from_csv(self, lines: Iterable[List[AnyStr]]):
        for i, line in enumerate(lines):
            if i == 0: # ignore header
                continue

            rowid, domain, source, utterance_id, start_time, \
                local_speaker_id, text, normalized_text, start, end, utterance_url = line

            r = self.record_by_utterance_url(utterance_url)
            r.download_(self.root, source, domain)

            if end == "":
                end = r.compute_duration() # end is missing for some final utterances: guess from file duration
                
            # TODO: guess reasonable enough utterance margins so that kaldi finds everything
            if start == end:
                start, end = float(start) - 0.3, float(end) + 0.3
            else:
                start, end = float(start), float(end)

            s = Utterance(recording_id=r.name, text=text, normalized_text=normalized_text, start=start, end=end,
                          speaker_id=self.get_global_speaker_id(r.name, local_speaker_id),
                          utterance_id=f'U{int(utterance_id):07d}', domain=domain, source=source,
                          utterance_url=utterance_url, recording_path=str(r.path))

            r.add_utterance(s)
            
        assert len(self.speakers) < 1e5
        assert i < 1e7

def download_file(url: str, target_audio_path: Path):
    target_audio_path.parent.mkdir(exist_ok=True)

    if target_audio_path.exists():
        return

    filename = url.split('/')[-1].replace(" ", "_")  # be careful with file names
    file_path = target_audio_path.parent / filename
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

    to_wav(file_path, target_audio_path)
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


def to_wav(v: Path, a: Path):
    cl = ["ffmpeg", "-i", str(v), "-vn", "-ac", "1", "-acodec", "pcm_s16le", "-ar", "16000", str(a)]
    print(f"Converting audio by command: {' '.join(cl)}", file=sys.stderr)
    subprocess.check_call(cl)


def main():
    csv_path = Path(sys.argv[1] if len(sys.argv) > 1 else "utterances.csv")
    corpus_dir = Path(sys.argv[2] if len(sys.argv) > 2 else "data/corpus")
    corpus_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Reading {csv_path} and storing downloaded audio in {corpus_dir}", file=sys.stderr)
    corpus = Corpus(corpus_dir)
    if os.path.isfile(csv_path):
        with open(csv_path) as csv_file:
            corpus.from_csv(csv.reader(csv_file, delimiter=','))
    elif os.path.isdir(csv_path):
        corpus.from_dir()
 
    for _, record in corpus.url2record.items():
        for segment in record.utterances:
            print(json.dumps(asdict(segment), ensure_ascii=False))


if __name__ == '__main__':
    main()
