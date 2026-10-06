# Разбор видео на кадры для просмотра головами Claude (слова автора 06.10: «Ищи варианты с видео сам. Потом разделяешь на кадры и работаешь с ними»).
#   /tmp/claude-0/vidvenv/bin/python tools/video_frames.py <url|файл> <папка> [кадр каждые N с, по умолчанию 3] [кадров на лист, по умолчанию 6]
# Скачивание — yt-dlp (с субтитрами, если есть), нарезка — ffmpeg из imageio-ffmpeg; на выходе листы 3×2 (contact sheets) с метками времени.
# Окружение: python3 -m venv /tmp/claude-0/vidvenv && /tmp/claude-0/vidvenv/bin/pip install yt-dlp imageio-ffmpeg
# Сеть: YouTube (youtube.com, googlevideo.com) закрыт политикой среды на 06.10.2026 — открыть в настройках среды или прислать файл.
import os, subprocess, sys, glob
import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe()
src, out = sys.argv[1], sys.argv[2]; every = float(sys.argv[3]) if len(sys.argv) > 3 else 3.0; per = int(sys.argv[4]) if len(sys.argv) > 4 else 6
os.makedirs(out, exist_ok=True)
if src.startswith('http'):
    subprocess.run([sys.executable, '-m', 'yt_dlp', '-f', 'mp4[height<=720]/best[height<=720]/best', '--write-auto-subs', '--write-subs', '--sub-langs', 'en,ru',
                    '--convert-subs', 'srt', '-o', os.path.join(out, 'video.%(ext)s'), src], check=True)
    src = sorted(glob.glob(os.path.join(out, 'video.*')), key=lambda p: -os.path.getsize(p))[0]
cols, rows = 3, max(1, per // 3)
# метка времени на каждом кадре, затем листы cols×rows
vf = (f"fps=1/{every},scale=480:-1,drawtext=text='%{{pts\\:hms}}':x=8:y=8:fontsize=22:fontcolor=yellow:box=1:boxcolor=black@0.6,"
      f"tile={cols}x{rows}")
r = subprocess.run([FF, '-hide_banner', '-loglevel', 'error', '-y', '-i', src, '-vf', vf, os.path.join(out, 'sheet_%03d.png')])
if r.returncode != 0:   # drawtext требует шрифт; без него — без меток
    subprocess.run([FF, '-hide_banner', '-loglevel', 'error', '-y', '-i', src, '-vf', f"fps=1/{every},scale=480:-1,tile={cols}x{rows}", os.path.join(out, 'sheet_%03d.png')], check=True)
sheets = sorted(glob.glob(os.path.join(out, 'sheet_*.png')))
print(f'{len(sheets)} листов по {cols * rows} кадров (кадр каждые {every} с; лист k начинается с {cols * rows * every:g}·(k−1) с) → {out}')
