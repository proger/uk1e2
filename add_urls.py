import json
import sys
from datetime import datetime


for line in sys.stdin:
    obj = json.loads(line)

    try:
        h,m,s = obj['start_time'].split(':')
        obj['url'] = 'https://youtu.be/' + obj['source'] + '?t=' + str(int(s) + int(m)*60 + int(h)*60*60)
    except:
        print(obj, file=sys.stderr)

    print(json.dumps(obj, ensure_ascii=False))
