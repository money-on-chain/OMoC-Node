#!/usr/bin/env python3
from glob import glob

table = []
for file in glob("*.log"):
    with open(file, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            
            line = line.strip()
            row = {}

            if 'need' in line or ' AS ' in line:
                timestamp = line.split()[0]
                pair = line.split()[2]
                data = ' '.join(line.split()[4:])
                node = file.replace('-', ' ').replace('_', ' ').replace('.', ' ').split()[6]
                node = {'charly': 'charlie'}.get(node, node) #FIXME later, special case for charl(y/ie)

                row = {
                    'timestamp': timestamp,
                    'node': node,
                    'pair': pair
                }

            if 'need' in line:

                state = ''
                hint = "---["
                if hint in data:
                    state = data.split(hint)[1].split("|")[0]

                row['state'] = state

            if ' AS ' in line:
                
                type_ = 'unknown'
                hint = " AS FALLBACK"
                if hint in data:
                    data = data.replace(hint, "")
                    type_ = 'fallback'
                hint = " AS CHOSEN"
                if hint in data:
                    data = data.replace(hint, "")
                    type_ = 'chosen'

                tx = 'unknown'
                hint = "ERROR PUBLISHING"
                if hint in data:
                    data = data.replace(hint, "")
                    tx = 'error'
                hint = "PRICE PUBLISHED"
                if hint in data:
                    data = data.replace(hint, "")
                    tx = 'ok'
                hint = "SENDING TRANSACTION"
                if hint in data:
                    data = data.replace(hint, "")
                    tx = 'send'

                message = ''
                hint = "'message': '"
                if hint in data:
                    message = data.split(hint)[1].split("'")[0]

                code = ''
                hint = "'code': "
                if hint in data:
                    code = data.split(hint)[1].split(",")[0]

                hash_ = ''
                hint = "'0x"
                if hint in data:
                    code = '0x' + data.split(hint)[1].split("'")[0]
                
                row['type'] = type_
                row['tx'] = tx
                row['tx'] = tx
                row['message'] = message
                row['code'] = code
                row['hash'] = hash_

            if row:
                table.append(row)

table = sorted(table, key=lambda x: x["timestamp"], reverse=False)

states = {}
for d in table:
    if 'state' in d:
        states[d['pair'], d['node']] = d['state']
    else:
        print(
            f"{d['timestamp']}\t"
            f"{d['node']}\t"
            f"{d['pair']}\t"
            f"{states.get((d['pair'], d['node']), '')}\t"
            f"{d['type']}\t"
            f"{d['tx']}\t"
            f"{d['message']}\t"
            f"{d['code']}\t"
            f"{d['hash']}"
        )

            