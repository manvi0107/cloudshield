"""AI forecast refiner: gradient boosting that corrects the geometric forecast's dip depth (ETA refinement was tested and gave no gain).
Train:  python -m ai.refiner   (generates data from the digital twin, saves models/refiner.joblib)"""
import os
import numpy as np

PATH = os.path.join(os.path.dirname(__file__), '..', 'models', 'refiner.joblib')
feat = lambda f: [f['eta'], f['depth'], f['speed'], f['conf'], f['n']]


class Refiner:
    def __init__(s, md, me):
        s.md, s.me = md, me

    @classmethod
    def load(cls, path=PATH):
        try:
            import joblib
            d = joblib.load(path)
            return cls(d['depth'], d['eta'])
        except Exception:
            return None

    def refine(s, f):
        x = [feat(f)]
        return {**f, 'depth': float(np.clip(s.md.predict(x)[0], 0, 1))}  # ETA stays geometric: the ETA model gave no gain


def dataset(n=300):
    from twin.sim import Twin, PLANT
    X, yd, ye, base = [], [], [], []
    for seed in range(1000, 1000 + n):
        tw, f, k = Twin(20, seed), None, 0
        while f is None and k < 250:
            tw.step(); f = tw.forecast(tw.t - 1); k += 1
        if f is None:
            continue
        t = tw.t - 1
        true = next((u - t for u in range(t, t + 400) if 1 - tw.cloud.cover(PLANT, u) < .7), None)
        if true is None:
            continue
        X.append(feat(f)); yd.append(tw.cloud.depth); ye.append(true - f['eta'])
    return np.array(X), np.array(yd), np.array(ye)


def train(n=300):
    import joblib
    from sklearn.ensemble import GradientBoostingRegressor as G
    from sklearn.model_selection import train_test_split
    X, yd, ye = dataset(n)
    Xa, Xb, da, db, ea, eb = train_test_split(X, yd, ye, test_size=.2, random_state=0)
    md, me = G(n_estimators=60, max_depth=3).fit(Xa, da), G(n_estimators=60, max_depth=3).fit(Xa, ea)
    print(f"samples={len(X)}  depth MAE: geometric={np.abs(Xb[:, 1] - db).mean():.3f} refined={np.abs(md.predict(Xb) - db).mean():.3f}")
    print(f"ETA MAE (s): geometric={np.abs(eb).mean():.2f} refined={np.abs(me.predict(Xb) - eb).mean():.2f}")
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    joblib.dump(dict(depth=md, eta=me, mae_geo=float(np.abs(Xb[:, 1] - db).mean()), mae_ai=float(np.abs(md.predict(Xb) - db).mean()), samples=len(X)), PATH)


if __name__ == '__main__':
    train()
