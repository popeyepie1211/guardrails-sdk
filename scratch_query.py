import psycopg
import json

conn = psycopg.connect('dbname=postgres user=postgres password=password host=127.0.0.1 port=5432')
cur = conn.cursor()
cur.execute("SELECT baseline FROM model_baselines WHERE model_id = 'credit_fraud_model_v1'")
row = cur.fetchone()
if row is None:
    print("NO ROW FOUND")
else:
    data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
    print('Top keys:', list(data.keys()))
    bs = data.get('baseline_summary', {})
    print('baseline_summary keys:', list(bs.keys()))
    print('ood_score baseline:', bs.get('ood_score'))
    
    dist = data.get('distributions', {})
    print('distributions keys:', list(dist.keys()))
    num = dist.get('numerical', {})
    if num:
        for k in list(num.keys())[:3]:
            vals = num[k]
            print(f'  {k}: {len(vals)} values, first 3: {vals[:3]}')
    else:
        print('  numerical distributions: EMPTY')

conn.close()
