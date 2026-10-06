# Видео → звук (текст) + 1 кадр в секунду (чаще на быстрых сменах сцены). Метод Gemini API (1 кадр/с + звук) и OpenAI Cookbook (кадры + расшифровка).
# Слова автора 06.10.2026: «Нужно аудио и 1 фото каждой секунды видео. Ну или чаще, если эпизод с быстрыми изменениями».
#   /tmp/claude-0/vidvenv/bin/python tools/video_frames.py <url|файл> <папка> [кадров в секунду, 1] [порог смены сцены, 0.3]
# Выход: frames/f_<секунды>.png (1/с + дополнительные на сменах сцены), sheet_NNN.png (листы 3×2 для просмотра), index.txt (кадр → время),
#        transcript.txt (субтитры, если есть; иначе распознавание речи pocketsphinx, английский, качество низкое).
# Окружение: python3 -m venv /tmp/claude-0/vidvenv && /tmp/claude-0/vidvenv/bin/pip install yt-dlp imageio-ffmpeg pocketsphinx
# Сеть: YouTube (youtube.com, googlevideo.com) закрыт политикой среды на 06.10.2026 — открыть в настройках среды или прислать файл.
import glob, os, re, subprocess, sys, wave
import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe()
src, out = sys.argv[1], sys.argv[2]
fps = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
scene = float(sys.argv[4]) if len(sys.argv) > 4 else 0.3
os.makedirs(os.path.join(out, 'frames'), exist_ok=True)

subs = []
if src.startswith('http'):
    subprocess.run([sys.executable, '-m', 'yt_dlp', '-f', 'mp4[height<=720]/best[height<=720]/best', '--write-auto-subs', '--write-subs',
                    '--sub-langs', 'en.*,ru.*', '--convert-subs', 'srt', '-o', os.path.join(out, 'video.%(ext)s'), src], check=True)
    subs = glob.glob(os.path.join(out, 'video*.srt'))
    src = max((p for p in glob.glob(os.path.join(out, 'video.*')) if not p.endswith('.srt')), key=os.path.getsize)

# 1) кадры: каждые 1/fps секунд плюс кадр на каждой смене сцены сильнее порога
sel = f"select='isnan(prev_selected_t)+gte(t-prev_selected_t\\,{1 / fps:g})+gt(scene\\,{scene:g})',showinfo,scale=640:-1"
r = subprocess.run([FF, '-hide_banner', '-i', src, '-vf', sel, '-vsync', 'vfr', os.path.join(out, 'frames', 'tmp_%05d.png')], capture_output=True, text=True)
times = [float(m) for m in re.findall(r'pts_time:([0-9.]+)', r.stderr)]
tmp = sorted(glob.glob(os.path.join(out, 'frames', 'tmp_*.png')))
idx = []
for p, t in zip(tmp, times):
    q = os.path.join(out, 'frames', f'f_{t:08.2f}.png'); os.replace(p, q); idx.append((t, q))
open(os.path.join(out, 'index.txt'), 'w').write(''.join(f'{t:8.2f} с  {os.path.basename(q)}\n' for t, q in idx))

# 2) листы 3×2 для просмотра (в index.txt — время каждого кадра; лист k = кадры 6(k−1)+1 … 6k)
fr = [q for _, q in idx]
for k in range(0, len(fr), 6):
    grp = fr[k:k + 6]; args = sum([['-i', g] for g in grp], [])
    pads = ''.join(f'[{j}:v]scale=640:360:force_original_aspect_ratio=decrease,pad=640:360:(ow-iw)/2:(oh-ih)/2[v{j}];' for j in range(len(grp)))
    lay = '|'.join(f'{(j % 3) * 640}_{(j // 3) * 360}' for j in range(len(grp)))
    subprocess.run([FF, '-hide_banner', '-loglevel', 'error', '-y', *args, '-filter_complex',
                    pads + ''.join(f'[v{j}]' for j in range(len(grp))) + f'xstack=inputs={len(grp)}:layout={lay}:fill=black' if len(grp) > 1 else f'[0:v]null',
                    os.path.join(out, f'sheet_{k // 6 + 1:03d}.png')])

# 3) звук → текст: субтитры, если есть; иначе pocketsphinx (английский)
tr = os.path.join(out, 'transcript.txt')
if subs:
    open(tr, 'w').write(open(subs[0]).read())
else:
    wav = os.path.join(out, 'audio16k.wav')
    if subprocess.run([FF, '-hide_banner', '-loglevel', 'error', '-y', '-i', src, '-vn', '-ac', '1', '-ar', '16000', '-sample_fmt', 's16', wav]).returncode == 0 and os.path.getsize(wav) > 1000:
        from pocketsphinx import Decoder
        dec = Decoder(samprate=16000); lines = []
        with wave.open(wav) as w:
            step = 16000 * 10                                      # кусками по 10 с, с меткой времени
            for i in range(0, w.getnframes(), step):
                w.setpos(i); buf = w.readframes(step)
                dec.start_utt(); dec.process_raw(buf, full_utt=True); dec.end_utt()
                h = dec.hyp(); lines.append(f'[{i / 16000:7.1f} с] {h.hypstr if h else ""}')
        open(tr, 'w').write('\n'.join(lines) + '\n')
    else:
        open(tr, 'w').write('(звуковой дорожки нет)\n')
print(f'{len(idx)} кадров ({fps:g}/с + смены сцены > {scene:g}), {len(glob.glob(os.path.join(out, "sheet_*.png")))} листов, текст: {tr}')
