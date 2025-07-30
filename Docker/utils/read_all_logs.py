#!/usr/bin/env python3
from glob import glob

out = []
for file in glob("*.log"):
    with open(file, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if ' AS ' in line:
                data = ' '.join(line.split()[4:])
                
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

                message=''
                if "'message': '" in data:
                    message = data.split("'message': '")[1].split("'")[0]

                code=''
                if "'code': " in data:
                    code = data.split("'code': ")[1].split(",")[0]


                timestamp = line.split()[0]
                
                pair = line.split()[2]
                
                node = file.replace('-', ' ').replace('_', ' ').replace('.', ' ').split()[6]
                node = {'charly': 'charlie'}.get(node, node) #FIXME later, special case for charl(y/ie)
                
                out.append(f"{timestamp}\t{node}\t{pair}\t{type_}\t{tx}\t{message}\t{code}")

out.sort()
print('\n'.join(out))

            