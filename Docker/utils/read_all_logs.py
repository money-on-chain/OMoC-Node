#!/usr/bin/env python3
import click, sys
from glob import glob
from tabulate import tabulate



def main(selected_pair=None):
    """
    This script reads all the log files in the current directory,
    extracts relevant information, and prints it in a tabular format.
    """

    table = []
    for file in glob("*.log"):
        with open(file, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                
                line = line.strip()
                row = {}

                init={
                    'sign_ask': 'GATHERING SIGNATURES:',
                    'sign_err': 'Publish: Not enough signatures',
                    'sign_ok': 'Publish: enough signatures',
                    'state': 'need',
                    'tx': ' AS ',
                    'blocks_ago': 'Price changed ',
                }

                if any([i in line for i in init.values()]):
                    timestamp = line.split()[0]
                    pair = line.split()[2]
                    data = ' '.join(line.split()[4:])
                    node = file.replace('-', ' ').replace('_', ' '
                        ).replace('.', ' ').split()[6]
                    
                    #FIXME later, special case for charl(y/ie)
                    node = {'charly': 'charlie'}.get(node, node)
                    
                    row = {
                        'timestamp': timestamp,
                        'node': node,
                        'pair': pair
                    }

                if init['blocks_ago'] in line:
                    blocks_ago = [i for i in data.split() if i.isdigit()][0]
                    row['blocks_ago'] = blocks_ago

                if init['sign_ask'] in line:
                    row['step'] = 'signs ask'

                if init['sign_err'] in line:
                    row['step'] = 'signs error'

                if init['sign_ok'] in line:
                    row['step'] = 'signs ok'

                if init['sign_ask'] in line or init['sign_err'] in line or init['sign_ok'] in line:
                    if "(chosen)" in data:
                        row['type'] = 'chosen'
                    if "(fallback" in data:
                        row['type'] = 'fallback #' + data.split('fallback ')[1].split(')')[0]

                if init['state']  in line:

                    state = ''
                    hint = "---["
                    if hint in data:
                        state = data.split(hint)[1].split("|")[0]

                    row['state'] = state

                if init['tx']  in line:
                    
                    type_ = 'unknown'
                    hint = " AS FALLBACK"
                    if hint in data:
                        data = data.replace(hint, "")
                        index_ = data.split('#')[1].split(',')[0]
                        type_ = f"fallback #{index_}" if index_ else 'fallback'
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
                        tx = 'received'
                        if "state='failed'" in data:
                            tx='failed'
                        if "state='success'" in data:
                            tx='success'
                    hint = "SENDING TRANSACTION"
                    if hint in data:
                        data = data.replace(hint, "")
                        tx = 'send'

                    message = ''
                    hint = "'message': '"
                    if hint in data:
                        message = data.split(hint)[1].split("'")[0]

                    hash_ = ''
                    hint = "'0x"
                    if hint in data:
                        hash_ = '0x' + data.split(hint)[1].split("'")[0]

                    lpb = ''
                    hint = ", last pub block"
                    if hint in data:
                        lpb = data.split(hint)[1].split(",")[0].strip()

                    row['type'] = type_
                    row['tx'] = tx
                    row['lpb'] = lpb                
                    row['message'] = message
                    row['hash'] = hash_

                if row:
                    table.append(row)

    table = sorted(table, key=lambda x: x["timestamp"], reverse=False)

    states = {}
    blocks_ago = {}
    final_table = []
    for d in table:
        if 'tx' in d:
            if selected_pair and d['pair'].lower() != selected_pair.lower():
                continue
            row = []
            row.append(f"{d['timestamp'].split('.')[0].replace('T', ' ')}")
            row.append(f"{d['node']}")
            if selected_pair is None:
                row.append(f"{d['pair']}")
            row.append(f"tx {d['tx']}") # step
            row.append(f"{d['type']}") # as
            row.append(f"{d['lpb']}") # lpb
            row.append(f"{d['message']}")
            row.append(f"{d['hash']}")
            final_table.append(row)
        elif 'step' in d:
            if selected_pair and d['pair'].lower() != selected_pair.lower():
                continue
            row = []
            row.append(f"{d['timestamp'].split('.')[0].replace('T', ' ')}")
            row.append(f"{d['node']}")
            if selected_pair is None:
                row.append(f"{d['pair']}")
            row.append(f"{d['step']}") # step
            row.append(f"{d.get('type', '')}") # as
            row.append(f"") # lpb
            row.append(f"")
            row.append(f"")
            final_table.append(row)
        elif 'state' in d:
            if states.get((d['pair'], d['node']), '') != d['state']:
                if selected_pair and d['pair'].lower() != selected_pair.lower():
                    continue
                row = []
                row.append(f"{d['timestamp'].split('.')[0].replace('T', ' ')}")
                row.append(f"{d['node']}")
                if selected_pair is None:
                    row.append(f"{d['pair']}")
                row.append(f"state {d['state']}") # step
                row.append("") # as
                row.append("") # lpb
                row.append("") # message
                row.append("") # hash
                final_table.append(row)
            states[d['pair'], d['node']] = d['state']
        elif 'blocks_ago' in d:
            if blocks_ago.get((d['pair'], d['node']), '') != d['blocks_ago']:
                if selected_pair and d['pair'].lower() != selected_pair.lower():
                    continue
                row = []
                row.append(f"{d['timestamp'].split('.')[0].replace('T', ' ')}")
                row.append(f"{d['node']}")
                if selected_pair is None:
                    row.append(f"{d['pair']}")
                row.append(f"blk {d['blocks_ago']}") # step
                row.append("") # as
                row.append("") # lpb
                row.append("") # message
                row.append("") # hash
                final_table.append(row)
            blocks_ago[d['pair'], d['node']] = d['blocks_ago']


    headers=[]
    headers.append("Timestamp")
    headers.append("Node")
    if selected_pair is None:
        headers.append("Pair")
    headers.append("Step")
    headers.append("As")
    headers.append("LPB")
    headers.append("Message")
    headers.append("Hash")
    
    if selected_pair is not None:
        print(f"Pair = {selected_pair}")
    print(tabulate(final_table, tablefmt="plain", headers=headers))


def get_pairs():
    out = set()
    for file in glob("*.log"):
        with open(file, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                line = line.strip()
                if 'need' in line or ' AS ' in line:
                    pair = line.split()[2]
                    out.add(pair)
    if not out:
        sys.exit("No *.log files found or no pairs in the logs.")
    return sorted(out)



@click.command()
@click.argument('pair', required=False,
                type=click.Choice(get_pairs(), case_sensitive=False))
def cli(pair):
    main(selected_pair=pair)



if __name__ == '__main__':
    cli()
