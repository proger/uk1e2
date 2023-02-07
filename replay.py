"""
read brushlyk snapshots, needs a patched yjs-websocket server that returns a json document on connection
"""
import json
import websocket
import argparse

parser = argparse.ArgumentParser('yjs snapshot client')
parser.add_argument('--url', type=str, default="ws://100.87.165.97:1235/y/playground/0/")
parser.add_argument('ids', nargs='+')
args = parser.parse_args()

messages = [
    r'"\u0000\u0000\u0001\u0000"',
    r'"\u0001[\u0001����\r\u0001S{\"anchorPos\":null,\"color\":\"0,200,55\",\"focusPos\":null,\"focusing\":false,\"name\":\"Dog\"}"',
    r'"\u0000\u0001\u0002\u0000\u0000"',
    r'"\u0001[\u0001����\r\u0002S{\"anchorPos\":null,\"color\":\"0,200,55\",\"focusPos\":null,\"focusing\":false,\"name\":\"Dog\"}"',
]

messages = [json.loads(line) for line in messages]

for id in args.ids:
    ws = websocket.WebSocket()
    ws.connect(args.url + id)

    # Replay the binary messages from the file
    for i, message in enumerate(messages):
        message = message.encode('utf-8')
        ws.send(message, opcode=websocket.ABNF.OPCODE_BINARY)
        if i >= 1:
            received = ws.recv()
            if i == 3:
                print(json.dumps({id: received.replace('[object Object]', '\n')}, ensure_ascii=False))

    ws.close()
