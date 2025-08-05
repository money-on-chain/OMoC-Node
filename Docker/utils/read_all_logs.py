#!/usr/bin/env python3
import click, sys
from glob import glob
from tabulate import tabulate



def main(selected_pair=None, show_hash=False, overview=False):
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

                if init['sign_err'] in line or init['sign_ok'] in line:
                    row['step'] = row['step'] + data.split('signatures')[1].split(' (')[0]    

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

    if overview:

        def get_by_kv(table, key, *values):
            return [x for x in table if key in x and x[key] in values]

        def get_by_keys(table, *keys):
            return [x for x in table if all([(key in x) for key in keys])]

        def get_by_key(table, key):
            return [x[key] for x in table if key in x]

        def get_count(table):
            out = {}
            for key in table:
                out[key] = out.get(key , 0) + 1
            return out
        
        if selected_pair:
            table = get_by_kv(table, 'pair', selected_pair)
        
        tx_error_message_count = get_count(
            get_by_key(get_by_kv(table, 'tx', 'error'), 'message'))
        
        tx_total = get_by_kv(table, 'tx', 'success', 'failed')
        tx_success = get_by_kv(tx_total, 'tx', 'success')
        tx_failed = get_by_kv(tx_total, 'tx', 'failed')

        errors_count = sum(tx_error_message_count.values())
        len_total = len(tx_total) + errors_count
        errors = '\n'.join([f"    {str(k).capitalize()}: {v}" for (k, v) in tx_error_message_count.items()])

        len_tx_success = len(tx_success)
        len_tx_failed = len(tx_failed)

        len_tx_success_chosen = len(get_by_kv(tx_success, 'type', 'chosen'))
        len_tx_success_fallback = len_tx_success - len_tx_success_chosen

        len_tx_failed_chosen = len(get_by_kv(tx_failed, 'type', 'chosen'))
        len_tx_failed_fallback = len_tx_failed - len_tx_failed_chosen

        title = "Overview of logs"
        if selected_pair:
            title += f" only for pair {selected_pair}"
        title = ' '.join(title.split())
        title += '\n' + ' '.join([len(x)*'=' for x in title.split()])

        print(f"""
{title}
                            
Total transactions: {len_total}

Failed: {len_tx_failed}
    As chosen: {len_tx_failed_chosen/len_tx_failed*100:.2f}%
    As fallback: {len_tx_failed_fallback/len_tx_failed*100:.2f}%

Success: {len_tx_success}
    As chosen: {len_tx_success_chosen/len_tx_success*100:.2f}%
    As fallback: {len_tx_success_fallback/len_tx_success*100:.2f}%

Errors: {errors_count}
{errors}


""")
        return


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
            if show_hash:
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
            if show_hash:
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
                if show_hash:
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
                if show_hash:
                    row.append("") # hash
                final_table.append(row)
            blocks_ago[d['pair'], d['node']] = d['blocks_ago']
        
    same_date = final_table[0][0].split()[0]==final_table[-1][0].split()[0]
    if selected_pair is not None:
        print(f"Pair = {selected_pair}")
    if same_date:
        print(f"Date = {final_table[0][0].split()[0]}")

    for i in range(len(final_table)-1, -1, -1):
        if final_table[i][0] == final_table[i-1][0]:
            final_table[i][0] = ''
        else:
            if same_date:
                final_table[i][0] = final_table[i][0].split()[1]    
    headers=[]
    headers.append("Time" if same_date else "Date/time")
    headers.append("Node")
    if selected_pair is None:
        headers.append("Pair")
    headers.append("Step")
    headers.append("As")
    headers.append("LPB")
    headers.append("Message")
    if show_hash:
        headers.append("Hash")
    
    print()
    print(tabulate(final_table, tablefmt="simple", headers=headers))
    print()


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



@click.command(cls=click.Command,
               context_settings=dict(help_option_names=['-h', '--help']))
@click.argument('pair', required=False,
                type=click.Choice(get_pairs(), case_sensitive=False))
@click.option('-s', '--show-hash', 'show_hash', is_flag=True, default=False,
              help='Shows TX hash in the output')

@click.option('-o', '--overview', 'overview', is_flag=True, default=False,
              help='Shows overview')
def cli(pair, show_hash=False, overview=False):
    main(selected_pair=pair, show_hash=show_hash, overview=overview)



if __name__ == '__main__':
    cli()
