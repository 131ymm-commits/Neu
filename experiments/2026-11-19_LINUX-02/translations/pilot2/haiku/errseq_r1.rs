use core::ffi::c_int;
use core::sync::atomic::{AtomicU32, Ordering};

#[allow(non_camel_case_types)]
pub type errseq_t = u32;

const MAX_ERRNO: u32 = 4095;
const ERRSEQ_SHIFT: u32 = MAX_ERRNO.ilog2() + 1;
const ERRSEQ_SEEN: u32 = 1 << ERRSEQ_SHIFT;
const ERRNO_MASK: u32 = ERRSEQ_SEEN - 1;
const ERRSEQ_CTR_INC: u32 = 1 << (ERRSEQ_SHIFT + 1);

/// Атомарное представление `errseq_t` по адресу `p`.
///
/// # Safety
/// `p` должен быть выровненным и действительным указателем на `errseq_t`,
/// к которому возможен конкурентный доступ только через атомарные операции.
#[inline(always)]
unsafe fn atomic<'a>(p: *mut errseq_t) -> &'a AtomicU32 {
    unsafe { AtomicU32::from_ptr(p) }
}

/// Установить ошибку `err` в `eseq` для последующего сообщения.
#[no_mangle]
pub extern "C" fn errseq_set(eseq: *mut errseq_t, err: c_int) -> errseq_t {
    let a = unsafe { atomic(eseq) };
    let mut old = a.load(Ordering::Relaxed);

    // Проверка допустимости кода ошибки (WARN: только условие, без вывода).
    let neg = err.wrapping_neg() as u32;
    if err == 0 || neg > MAX_ERRNO {
        return old;
    }

    loop {
        // Очистить биты ошибки и флаг SEEN, записать новую ошибку.
        let mut new = (old & !(ERRNO_MASK | ERRSEQ_SEEN)) | neg;

        // Увеличивать счётчик только если значение кто-то уже прочитал.
        if old & ERRSEQ_SEEN != 0 {
            new = new.wrapping_add(ERRSEQ_CTR_INC);
        }

        // Изменений нет — завершаем.
        if new == old {
            return new;
        }

        let cur = match a.compare_exchange(old, new, Ordering::SeqCst, Ordering::SeqCst) {
            Ok(v) | Err(v) => v,
        };

        // Успех, либо другой поток записал то же самое значение.
        if cur == old || cur == new {
            return cur;
        }

        // Гонка с другим обновлением — повторяем.
        old = cur;
    }
}

/// Получить текущее значение `errseq_t` для инициализации выборки.
#[no_mangle]
pub extern "C" fn errseq_sample(eseq: *mut errseq_t) -> errseq_t {
    let a = unsafe { atomic(eseq) };
    let mut old = a.load(Ordering::Relaxed);

    // Если ошибка ещё не была замечена, новый вызывающий начинает с нуля.
    if old & ERRSEQ_SEEN == 0 {
        old = 0;
    }
    old
}

/// Была ли ошибка с момента выборки `since`?
#[no_mangle]
pub extern "C" fn errseq_check(eseq: *mut errseq_t, since: errseq_t) -> c_int {
    let a = unsafe { atomic(eseq) };
    let cur = a.load(Ordering::Relaxed);

    if cur == since {
        return 0;
    }
    ((cur & ERRNO_MASK) as c_int).wrapping_neg()
}

/// Проверить `eseq` относительно `*since` и продвинуть `*since` к текущему значению.
#[no_mangle]
pub extern "C" fn errseq_check_and_advance(eseq: *mut errseq_t, since: *mut errseq_t) -> c_int {
    let a = unsafe { atomic(eseq) };
    let mut err: c_int = 0;
    let mut old = a.load(Ordering::Relaxed);

    while old != unsafe { *since } {
        // Выставляем флаг SEEN и пытаемся записать его на место.
        let new = old | ERRSEQ_SEEN;
        if new != old {
            let cur = match a.compare_exchange(old, new, Ordering::SeqCst, Ordering::SeqCst) {
                Ok(v) | Err(v) => v,
            };
            if cur != old {
                // Значение изменилось — повторяем с новым.
                old = cur;
                continue;
            }
        }
        unsafe {
            *since = new;
        }
        err = ((new & ERRNO_MASK) as c_int).wrapping_neg();
        break;
    }
    err
}
