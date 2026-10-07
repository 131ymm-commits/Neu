"""Русские строки команд для тренера."""
import unittest

from voicecoach import parse
from voicecoach.describe import describe, item_ru
from tests.test_parser import ctx

NAMES = {1: "Миракл", 2: "Топсон", 3: "Коллапс", 4: "Мира", 5: "Вася"}


def d(text):
    return [describe(c, NAMES) for c in parse(text, ctx()).commands]


class Describe(unittest.TestCase):
    def test_examples(self):
        self.assertEqual(d("Миракл, фарми лес, остальные на Рошана"),
                         ["Миракл: фармить — свой лес", "Топсон, Коллапс, Мира, Вася: Рошан"])
        self.assertEqual(d("бейте пуджа"), ["все: фокус цели — Пудж"])
        self.assertEqual(d("смок и ганг мид"), ["все: смок — мид, потом ганг"])
        self.assertEqual(d("не начинайте"), ["все: не начать драку"])
        self.assertEqual(d("Миракл, купи бкб"), ["Миракл: купить — БКБ"])
        self.assertEqual(d("купи бкб"), ["?: купить — БКБ — кому?"])
        self.assertEqual(d("т2 на топе сносим"), ["все: пушить линию — топ, т2"])
        self.assertEqual(d("спасите керри"), ["Топсон, Коллапс, Мира, Вася: спасти союзника — Миракл"])

    def test_item_names(self):
        self.assertEqual(item_ru("item_black_king_bar"), "БКБ")
        self.assertEqual(item_ru("item_blink"), "блинк")


if __name__ == "__main__":
    unittest.main()
