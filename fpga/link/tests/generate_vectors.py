"""Regenerate checked-in offline protocol fixtures; never accesses hardware."""
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from reference.link_protocol import vectors

items = vectors()
out = ROOT / 'link/tests'
(out/'link_vectors.json').write_text(json.dumps(items, indent=2)+'\n', encoding='utf-8')
(out/'link_vectors.mem').write_text('\n'.join(v['request']+v['response'] for v in items)+'\n', encoding='ascii')
print(f'Generated {len(items)} golden vectors')
