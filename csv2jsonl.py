import sys
import pandas as pd

pd.read_csv(sys.argv[1], sep=';').to_json(sys.stdout, orient='records', lines=True, force_ascii=False)