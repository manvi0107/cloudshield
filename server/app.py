"""FastAPI backend: runs the twin in real time, bridges MQTT hardware nodes, serves the dashboard."""
import asyncio, json, os, time
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from twin.sim import Twin
from twin.run import run, metrics
from ai.refiner import Refiner

VERSION, BOOT = "1.1.0", time.time()
ai = Refiner.load()
S = dict(tw=None, last=None, hist=[], epoch=0, comms=True, ai_on=True, speed=2, paused=False, hw={}, mq=None, replay=None)
app = FastAPI(title="CloudShield Grid")


def new_twin():
    S["tw"], S["hist"], S["epoch"] = Twin(100, int(time.time()) % 100000, ai if S["ai_on"] else None), [], S["epoch"] + 1


def start_mqtt():
    host = os.getenv("MQTT_HOST")
    if not host:
        return None
    import paho.mqtt.client as mqtt
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    def on_msg(cl, ud, m):
        try:
            _, nid, kind = m.topic.split("/")
            h = S["hw"].setdefault(nid, {})
            h.update(json.loads(m.payload))
            h["ts"] = time.time()
            if kind == "reading":
                h["rts"] = time.time()
        except Exception:
            pass
    c.on_connect = lambda cl, u, fl, rc, pr=None: cl.subscribe([("node/+/reading", 0), ("node/+/status", 0)])
    c.on_message = on_msg
    c.connect_async(host, int(os.getenv("MQTT_PORT", 1883)))
    c.loop_start()
    return c


async def ticker():
    while True:
        if S["paused"]:
            await asyncio.sleep(.3)
            continue
        tw = S["tw"]
        if tw.t >= 360:                      # scenario finished: hold the result, then start a new one
            await asyncio.sleep(10)
            new_twin()
            continue
        now = time.time()
        ov = {i: S["hw"][f"mesh-{i}"]["v"] for i in range(5) if now - S["hw"].get(f"mesh-{i}", {}).get("rts", 0) < 5}
        st = tw.step(ov, S["comms"])
        S["last"] = st
        S["hist"].append(st)
        if S["mq"]:
            try:
                S["mq"].publish("shortfall/level", str(st["level"]), retain=True)
                S["mq"].publish("forecast/dip", json.dumps(st["forecast"]), retain=True)
            except Exception:
                pass
        await asyncio.sleep(1 / S["speed"])


@app.on_event("startup")
async def up():
    new_twin()
    S["mq"] = start_mqtt()
    asyncio.create_task(ticker())


@app.get("/api/meta")
def meta():
    return dict(epoch=S["epoch"], ai=ai is not None and S["ai_on"], **S["tw"].meta())


@app.get("/api/history")
def history(since: int = -1):
    return dict(epoch=S["epoch"], steps=[x for x in S["hist"] if x["t"] > since])


@app.get("/api/state")
def state():
    return S["last"] or {}


@app.get("/api/status")
def status():
    now, h = time.time(), S["hist"]
    nodes = []
    for i in range(5):
        d = S["hw"].get(f"mesh-{i}", {})
        hw = now - d.get("rts", 0) < 5
        nodes.append(dict(id=f"mesh-{i}", type="mesh", source="hardware" if hw else "simulated", online=True, fw=d.get("fw", "sim") if hw else "sim"))
    return dict(version=VERSION, uptime_s=int(now - BOOT), mode="live", comms=S["comms"], ai=ai is not None, ai_on=S["ai_on"],
                mqtt=S["mq"] is not None, speed=S["speed"], paused=S["paused"], epoch=S["epoch"], nodes=nodes,
                metrics=metrics(h, S["tw"]) if h else None)


@app.get("/api/hw")
def hw():
    now = time.time()
    return {k: dict(v=d["v"], age=round(now - d["rts"], 1), fw=d.get("fw", "1.0")) for k, d in S["hw"].items() if now - d.get("rts", 0) < 5 and "v" in d}


@app.get("/api/replay")
def replay():
    S["replay"] = S["replay"] or run(ai=ai)
    return S["replay"]


@app.post("/api/comms/{st}")
def comms(st: str):
    S["comms"] = st != "down"
    return {"comms": S["comms"]}


@app.post("/api/ai/{st}")
def ai_toggle(st: str):
    S["ai_on"] = st == "on"
    S["tw"].ai = ai if S["ai_on"] else None
    return {"ai_on": S["ai_on"]}


@app.post("/api/speed/{x}")
def speed(x: int):
    S["speed"] = max(1, min(20, x))
    return {"speed": S["speed"]}


@app.post("/api/pause/{st}")
def pause(st: str):
    S["paused"] = st == "on"
    return {"paused": S["paused"]}


@app.post("/api/reset")
def reset():
    new_twin()
    return {"epoch": S["epoch"]}


app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "..", "dashboard"), html=True), name="ui")
