"""Join the screen recording, the narration clips and the cards into one mp4.
Usage: python tools/video/assemble.py        (reads video/marks.json, video/durations.json; writes video/ai-ledger-demo.mp4)"""
import json
import os
import subprocess

V = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "video")
INTRO_S, TAIL_S = 1.5, 1.0
m = json.load(open(os.path.join(V, "marks.json")))
durs = {s["id"]: s["dur"] for s in json.load(open(os.path.join(V, "durations.json")))}
trim, total = m["trim"] / 1000, m["total"] / 1000
D = round(total - trim, 3)
ids = [i for i in m["marks"]]


def run(*a):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *a], check=True)


p = lambda f: os.path.join(V, f)  # noqa: E731
run("-ss", str(trim), "-i", m["video"], "-an", "-t", str(D), "-vf", "fps=30,scale=1280:720:flags=lanczos,format=yuv420p",
    "-c:v", "libx264", "-preset", "medium", "-crf", "19", p("main_v.mp4"))
ins, parts = [], []
for n, i in enumerate(ids):
    ins += ["-i", p(f"{i}.wav")]
    parts.append(f"[{n}:a]adelay={int(round(m['marks'][i] - m['trim']))}:all=1[a{n}]")
mix = "".join(f"[a{n}]" for n in range(len(ids)))
run(*ins, "-filter_complex", ";".join(parts) + f";{mix}amix=inputs={len(ids)}:normalize=0,apad=whole_dur={D}[a]", "-map", "[a]", "-t", str(D),
    "-ar", "44100", "-ac", "1", p("main_a.wav"))
run("-i", p("main_v.mp4"), "-i", p("main_a.wav"), "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", p("main.mp4"))
run("-loop", "1", "-t", str(INTRO_S), "-i", p("intro.png"), "-f", "lavfi", "-t", str(INTRO_S), "-i", "anullsrc=r=44100:cl=mono",
    "-vf", "fps=30,scale=1280:720,format=yuv420p", "-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac", "-shortest", p("intro.mp4"))
end_s = durs["s9"] + TAIL_S
run("-loop", "1", "-t", str(end_s), "-i", p("outro.png"), "-i", p("s9.wav"), "-filter_complex", f"[1:a]apad=whole_dur={end_s}[a]",
    "-map", "0:v", "-map", "[a]", "-vf", "fps=30,scale=1280:720,format=yuv420p", "-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac", "-t", str(end_s), p("outro.mp4"))
run("-i", p("intro.mp4"), "-i", p("main.mp4"), "-i", p("outro.mp4"),
    "-filter_complex", "[0:v][0:a][1:v][1:a][2:v][2:a]concat=n=3:v=1:a=1[v][a]", "-map", "[v]", "-map", "[a]",
    "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", p("ai-ledger-demo.mp4"))
out = p("ai-ledger-demo.mp4")
info = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration,size:stream=codec_name,width,height,r_frame_rate", "-of", "json", out]).decode()
d = json.loads(info)
secs = float(d["format"]["duration"])
print(f"{out}\n  duration {int(secs // 60)}:{secs % 60:04.1f} ({secs:.1f}s)  size {int(d['format']['size']) / 1e6:.1f} MB  streams {[(s['codec_name'], s.get('width')) for s in d['streams']]}")
print("  UNDER 3:00" if secs < 180 else "  OVER 3:00: cut something")
