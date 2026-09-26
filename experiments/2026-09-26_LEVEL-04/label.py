# LEVEL-04: механическая разметка исходов цепочки (поправка совета, п. 2). Вслепую к генотипу: на вход — звенья цепочки и правда.
# Звено — «отказ», если выписано меньше m значений или последнее значение не разбирается как число.
# Цепочка: «верно» — полная и итог = правда; «ошибка» — полная, но итог неверен;
# «отказ с догадкой» — есть звено-отказ, но итог-число выдан; «отказ» — итог не число.
import re
P = 1000000007
def is_num(v): return bool(re.fullmatch(r'\d+', str(v).strip()))
def label_chain(links, final, truth):
    """links: список {'m': шагов, 'n': выписано, 'values': [...]} по порядку исполнения (включая пересчёты). Возвращает (исход, выполнено_шагов)."""
    refused = any((l.get('n') or 0) < l['m'] or not (l.get('values') and is_num(l['values'][-1])) for l in links)
    done = sum(min(l.get('n') or 0, l['m']) for l in links)
    if not is_num(final): return 'отказ', done
    if refused: return ('верно' if str(final) == str(truth) else 'отказ с догадкой'), done
    return ('верно' if str(final) == str(truth) else 'ошибка'), done
