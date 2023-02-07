import json
import sys

# def file_duration(x):
#     import subprocess
#     cmd = "ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1".split()
#     return subprocess.check_output(cmd + [x])

def read_timestamp(x):
    hh,mm,ss = map(int, x.split(':'))
    return ss + mm*60 + hh*60

def flush(obj, end_time):
    t = read_timestamp(obj['start_time'])
    obj['start'] = t

    if obj['domain'] == 'youtube':
        if end_time:
            end_time = read_timestamp(end_time)
            obj['url'] = 'https://www.youtube.com/embed/' + obj['source'] + f'?start={t}&end={end_time}'
        else:
            obj['url'] = 'https://www.youtube.com/embed/' + obj['source'] + f'?start={t}'
    else:
        if end_time:
            end_time = read_timestamp(end_time)
            obj['end'] = end_time
            obj['url'] = f"https://a.wilab.org.ua/uk1e2/mp4/{obj['source']}.mp4?start={t}&end={end_time}"
        else:
            obj['url'] = f"https://a.wilab.org.ua/uk1e2/mp4/{obj['source']}.mp4?start={t}"

    print(json.dumps(obj, ensure_ascii=False), flush=True)


def catch(f, *args):
    try:
        f(*args)
    except Exception as e:
        raise ValueError(*args) from e


prev = None
for line in sys.stdin:
    obj = json.loads(line)

    if prev:
        if obj['source'] != prev['source']:
            catch(flush, prev, None)
        else:
            catch(flush, prev, obj['start_time'])

    prev = obj
    
flush(obj, end_time=None)