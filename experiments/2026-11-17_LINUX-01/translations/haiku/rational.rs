// SPDX-License-Identifier: GPL-2.0
//
// Rational fractions: перевод lib/math/rational.c на Rust.
//
// Конфигурация: x86_64, BITS_PER_LONG = 64, unsigned long = c_ulong = u64.
// Макросы EXPORT_SYMBOL, MODULE_DESCRIPTION и MODULE_LICENSE не порождают
// кода и здесь опущены; экспорт обеспечивают #[no_mangle] и pub extern "C".
//
// Вычисляет наилучшее рациональное приближение n/d при ограничениях
// max_numerator и max_denominator (подходящие подходящие дроби цепной дроби
// и полуподходящая дробь). Арифметика C на беззнаковых числах заворачивается
// по модулю 2^64, поэтому все операции, которые могут переполниться, записаны
// через wrapping_*.

use core::ffi::c_ulong;

/// ULONG_MAX для unsigned long (64 бита).
const ULONG_MAX: c_ulong = c_ulong::MAX;

#[no_mangle]
pub extern "C" fn rational_best_approximation(
    given_numerator: c_ulong,
    given_denominator: c_ulong,
    max_numerator: c_ulong,
    max_denominator: c_ulong,
    best_numerator: *mut c_ulong,
    best_denominator: *mut c_ulong,
) {
    // n/d — исходная дробь, которая на каждой итерации уменьшается
    // алгоритмом Евклида.
    //
    // n2/d2, n1/d1, n0/d0 — последовательно более точные приближения:
    // текущее, предыдущее и два предыдущих соответственно.
    let mut n: c_ulong = given_numerator;
    let mut d: c_ulong = given_denominator;
    let mut n0: c_ulong = 0;
    let mut d1: c_ulong = 0;
    let mut n1: c_ulong = 1;
    let mut d0: c_ulong = 1;

    loop {
        if d == 0 {
            break;
        }

        // Следующий член цепной дроби 'a' через алгоритм Евклида.
        let dp: c_ulong = d;
        let a: c_ulong = n / d;
        d = n % d;
        n = dp;

        // Текущая подходящая дробь n2/d2 по найденному члену и двум предыдущим.
        let n2: c_ulong = n0.wrapping_add(a.wrapping_mul(n1));
        let d2: c_ulong = d0.wrapping_add(a.wrapping_mul(d1));

        // Если текущая дробь превышает ограничения, возвращаем предыдущую
        // подходящую дробь или наибольшую полуподходящую дробь (её последний
        // член — t).
        if n2 > max_numerator || d2 > max_denominator {
            let mut t: c_ulong = ULONG_MAX;

            if d1 != 0 {
                t = max_denominator.wrapping_sub(d0) / d1;
            }
            if n1 != 0 {
                t = core::cmp::min(t, max_numerator.wrapping_sub(n0) / n1);
            }

            // Проверка, ближе ли полуподходящая дробь, чем предыдущая
            // подходящая. Если d1 == 0, это первая итерация, и полуподходящая
            // дробь выбирается всегда.
            let two_t: c_ulong = (2 as c_ulong).wrapping_mul(t);
            if d1 == 0
                || two_t > a
                || (two_t == a && d0.wrapping_mul(dp) > d1.wrapping_mul(d))
            {
                n1 = n0.wrapping_add(t.wrapping_mul(n1));
                d1 = d0.wrapping_add(t.wrapping_mul(d1));
            }
            break;
        }

        n0 = n1;
        n1 = n2;
        d0 = d1;
        d1 = d2;
    }

    // Запись результата по указателям.
    unsafe {
        *best_numerator = n1;
        *best_denominator = d1;
    }
}
