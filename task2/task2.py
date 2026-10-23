import hashlib
import glob
import math

email = "idolzhas@gmail.com"
hashes = []

for filepath in glob.glob('files/*.data'):
    with open(filepath, 'rb') as f:
        hashes.append(hashlib.sha3_256(f.read()).hexdigest())

assert len(hashes) == 256, len(hashes)

hashes.sort(key=lambda h: math.prod(int(c, 16) + 1 for c in h))

final_string = "".join(hashes) + email.lower().strip()
result = hashlib.sha3_256(final_string.encode('utf-8')).hexdigest()

print(f"!task2 {email.lower().strip()} {result}")