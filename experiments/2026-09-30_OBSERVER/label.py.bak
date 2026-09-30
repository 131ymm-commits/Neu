# «Наблюдатель»: разметка вердикта автора по коду (правила записаны до опыта; без суждения головы).
# ACCEPT — согласие/продолжение без возражения; REJECT — отказ или поворот («нет…», «не туда», «не так», «неправильно»); OTHER — новое задание, вопрос, прочее.
import re
REJ = re.compile(r'^\s*(нет\b|не\s+(туда|так|в\s+ту\s+сторону|правильно)|неправильно)|\b(не\s+туда|не\s+в\s+ту\s+сторону|не\s+правильно|неправильно)\b', re.I)
ACC = re.compile(r'^\s*(да|ок|ok|окей|хорошо|давай|делай|запускай|прогоняй|продолжи|продолжай|продолжим|согласен|верно|отлично)\b', re.I)
def label(text):
    t = text.strip()
    if REJ.search(t): return 'REJECT'
    if ACC.search(t): return 'ACCEPT'
    return 'OTHER'
if __name__ == '__main__':
    import json, sys, collections
    P = json.load(open(sys.argv[1])); c = collections.Counter(label(p['human']) for p in P); print(dict(c))
