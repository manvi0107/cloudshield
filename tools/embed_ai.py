"""Export the trained depth model to JSON and embed it in dashboard/index.html (between AI_START and AI_END).
Run after `python -m ai.refiner`:  python -m tools.embed_ai"""
import json, re
import joblib
from ai.refiner import PATH

d = joblib.load(PATH)
m = d['depth']
trees = []
for e in m.estimators_[:, 0]:
    t = e.tree_
    trees.append([t.feature.tolist(), [round(float(x), 4) for x in t.threshold], t.children_left.tolist(),
                  t.children_right.tolist(), [round(float(x[0][0]), 5) for x in t.value]])
meta = f"Gradient boosting, {len(trees)} trees, depth error {d.get('mae_geo', 0):.3f} to {d.get('mae_ai', 0):.3f} on held-out twin data ({d.get('samples', 0)} samples)"
blob = json.dumps(dict(init=float(m.init_.constant_[0][0]), lr=float(m.learning_rate), trees=trees, meta=meta), separators=(',', ':'))
p = 'dashboard/index.html'
s = open(p, encoding='utf-8').read()
s = re.sub(r'/\*AI_START\*/.*?/\*AI_END\*/', lambda _: '/*AI_START*/' + blob + '/*AI_END*/', s, flags=re.S)
open(p, 'w', encoding='utf-8').write(s)
print('embedded', len(blob), 'bytes;', meta)
