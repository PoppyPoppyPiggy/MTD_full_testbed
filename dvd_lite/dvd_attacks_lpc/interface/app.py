import os, subprocess, time, json, pathlib
from flask import Flask, render_template, request, redirect, url_for, flash, send_file

LPC_ROOT = os.environ.get("LPC_ROOT", os.path.expanduser("~/MTD/MTD_full_testbed/dvd_lite/dvd_attacks_lpc"))
BUS_LOG = os.path.join(LPC_ROOT, "attack_output", "bus.log")
EVAL_DIR = os.path.join(LPC_ROOT, "attack_output")
YAML_DIR = os.path.join(LPC_ROOT, "scenarios")

app = Flask(__name__)
app.secret_key = "lpc-ui"

def list_yaml():
    p = pathlib.Path(YAML_DIR)
    return sorted([str(x) for x in p.glob("*.yaml")])

@app.route("/")
def index():
    yamls = list_yaml()
    files = {
        "bus_log": os.path.exists(BUS_LOG),
        "timeline": os.path.exists(os.path.join(EVAL_DIR,"effect_timeline.csv")),
        "metrics": os.path.exists(os.path.join(EVAL_DIR,"ns3_metrics.csv")),
    }
    return render_template("index.html", yamls=yamls, files=files)

@app.route("/run_yaml", methods=["POST"])
def run_yaml():
    yaml = request.form.get("yaml","").strip()
    if not yaml:
        flash("YAML not specified")
        return redirect(url_for("index"))
    cmd = f'cd "{LPC_ROOT}" && chmod +x attackctl modules/*.sh sh_core/*.sh && ./attackctl "{yaml}"'
    subprocess.Popen(["bash","-lc", cmd])
    flash(f"Scenario started: {yaml}")
    return redirect(url_for("index"))

@app.route("/ns3_eval", methods=["POST"])
def ns3_eval():
    cmd = f'cd "{LPC_ROOT}" && chmod +x eval/run_eval.sh && ./eval/run_eval.sh'
    r = subprocess.run(["bash","-lc", cmd], capture_output=True, text=True)
    flash(r.stdout.strip() or "ns-3 eval done")
    return redirect(url_for("index"))

@app.route("/download/<name>")
def download(name):
    m = {
        "bus.log": BUS_LOG,
        "effect_timeline.csv": os.path.join(EVAL_DIR,"effect_timeline.csv"),
        "ns3_metrics.csv": os.path.join(EVAL_DIR,"ns3_metrics.csv"),
        "packets.csv": os.path.join(EVAL_DIR,"packets.csv"),
        "window_features.csv": os.path.join(EVAL_DIR,"window_features.csv"),
    }
    path = m.get(name)
    if not path or not os.path.exists(path):
        return ("Not found", 404)
    return send_file(path, as_attachment=True)
    
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5173, debug=False)
