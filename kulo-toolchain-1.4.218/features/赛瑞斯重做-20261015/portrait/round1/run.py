# Copied from the 立绘重设计-20261008 runner (session 653d4f29 scratchpad art/run.py).
# Changes: newer codex.exe path, explicit -m gpt-6-astra, read-only sandbox
# (the agent only generates; this runner copies the PNG from the generated_images path in the log).
import subprocess, sys, os, re, shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
JOBS = __import__(os.environ.get("JOBS_MOD", "jobs_seris_r1")).JOBS
GEN = HERE / "gen"
CODEX = r"C:\Users\12101\AppData\Local\OpenAI\Codex\bin\9614f1d9b40d9c4f\codex.exe"
ids = sys.argv[1].split(",") if len(sys.argv) > 1 else None


def run(job):
    out = GEN / job["out"]
    if out.exists():
        return job["id"], "exists"
    task = (job["prompt"] + "\n\n---\nINSTRUCTIONS FOR YOU (the agent): Generate exactly ONE image with your built-in image generation tool, "
            "using the attached images as references as described. Draw it only with the image generation tool. After it is generated, "
            "reply with one line: 'Generated: <full path of the generated png>'.")
    cmd = [CODEX, "exec", "--skip-git-repo-check", "-m", "gpt-6-astra", "-s", "read-only",
           "-c", "model_reasoning_effort=\"medium\"", "-C", str(HERE)]
    for r in job["refs"]:
        cmd += ["-i", str(HERE / r)]
    cmd += ["-"]
    log = GEN / (job["id"] + ".log")
    with open(log, "w", encoding="utf-8") as lf:
        p = subprocess.run(cmd, input=task, text=True, encoding="utf-8", stdout=lf, stderr=subprocess.STDOUT, timeout=1500)
    txt = log.read_text(encoding="utf-8", errors="ignore")
    m = re.findall(r"([A-Za-z]:\\[^\s'\"<>]*generated_images[^\s'\"<>]+?\.png)", txt) or re.findall(r"(\S*generated_images\S+?\.png)", txt)
    for c in reversed(m):
        if Path(c).exists():
            shutil.copy(c, out)
            break
    return job["id"], ("ok" if out.exists() else f"missing rc={p.returncode}")


jobs = [j for j in JOBS if ids is None or j["id"] in ids]
with ThreadPoolExecutor(int(os.environ.get("PAR", "4"))) as ex:
    for r in ex.map(run, jobs):
        print(*r, flush=True)
