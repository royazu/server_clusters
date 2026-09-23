RADIUS = 5.0


def point(rec):
    return [float(rec["longitude"]), float(rec["latitude"])]


def euclid(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def median(vals):
    s = sorted(vals)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2


class GeoClusters:
    groups = []

    @classmethod
    def add(cls, iid, rec, radius=RADIUS):
        p = point(rec)
        nearest, best = None, None
        for g in cls.groups:
            d = euclid(p, g["centroid"])
            if best is None or d < best:
                nearest, best = g, d
        if nearest is not None and best <= radius:
            nearest["ids"].append(iid)
            n = len(nearest["ids"])
            c = nearest["centroid"]
            nearest["centroid"] = [(c[0] * (n - 1) + p[0]) / n, (c[1] * (n - 1) + p[1]) / n]
        else:
            cls.groups.append({"centroid": p[:], "ids": [iid]})

    @classmethod
    def remove(cls, iid, data):
        for g in list(cls.groups):
            if iid not in g["ids"]:
                continue
            g["ids"].remove(iid)
            if not g["ids"]:
                cls.groups.remove(g)
                return
            pts = [point(data[i]) for i in g["ids"]]
            g["centroid"] = [
                sum(p[0] for p in pts) / len(pts),
                sum(p[1] for p in pts) / len(pts),
            ]
            return

    @classmethod
    def as_json(cls, data):
        out = {}
        for i, g in enumerate(cls.groups, 1):
            pts = [point(data[j]) for j in g["ids"] if j in data]
            if not pts:
                continue
            lons, lats = [p[0] for p in pts], [p[1] for p in pts]
            block = {
                "median_coordinates": [median(lons), median(lats)],
                "mean_coordinates": [sum(lons) / len(lons), sum(lats) / len(lats)],
            }
            for j in g["ids"]:
                if j in data:
                    block[j] = data[j]
            out[f"cluster_{i}"] = block
        return out
