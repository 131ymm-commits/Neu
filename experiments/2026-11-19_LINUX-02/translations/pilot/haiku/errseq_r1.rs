use core::ffi::c_int;
use core::ptr;
use core::sync::atomic::{AtomicU32, Ordering};

type ErrseqT = u32;

const MAX_ERRNO: u32 = 4095;

const fn ilog2(n: u32) -> u32 {
    31 - n.leading_zeros()
}

/// Младшие биты: код ошибки (0..=MAX_ERRNO).
const ERRSEQ_SHIFT: u32 = ilog2(MAX_ERRNO) + 1;
/// Флаг: значение уже было просмотрено.
const ERRSEQ_SEEN: u32 = 1 << ERRSEQ_SHIFT;
/// Маска кода ошибки.
const ERRNO_MASK: u32 = ERRSEQ_SEEN - 1;
/// Младший бит счётчика.
const ERRSEQ_CTR_INC: u32 = 1 << (ERRSEQ_SHIFT + 1);

/// Атомарное чтение (READ_ONCE над errseq_t).
#[inline]
unsafe fn read_once(p: *mut ErrseqT) -> ErrseqT {
    unsafe { AtomicU32::from_ptr(p).load(Ordering::Relaxed) }
}

/// cmpxchg: если *p == old, записать new; вернуть значение *p до операции.
#[inline]
unsafe fn cmpxchg(p: *mut ErrseqT, old: ErrseqT, new: ErrseqT) -> ErrseqT {
    let a = unsafe { AtomicU32::from_ptr(p) };
    match a.compare_exchange(old, new, Ordering::SeqCst, Ordering::SeqCst) {
        Ok(v) | Err(v) => v,
    }
}

#[no_mangle]
pub extern "C" fn errseq_set(eseq: *mut ErrseqT, err: c_int) -> ErrseqT {
    let mut old = unsafe { read_once(eseq) };

    // WARN(): журнала нет (ввод-вывод запрещён), сохраняется только условие.
    let warn_cond = err == 0 || (err.wrapping_neg() as u32) > MAX_ERRNO;
    if warn_cond {
        return old;
    }

    loop {
        // Сброс кода ошибки и флага SEEN, установка новой ошибки.
        let mut new = (old & !(ERRNO_MASK | ERRSEQ_SEEN)) | (err.wrapping_neg() as u32);

        // Увеличиваем счётчик только если значение кто-то просмотрел.
        if (old & ERRSEQ_SEEN) != 0 {
            new = new.wrapping_add(ERRSEQ_CTR_INC);
        }

        // Изменений нет — готово.
        if new == old {
            break new;
        }

        let cur = unsafe { cmpxchg(eseq, old, new) };

        // Успех, либо кто-то уже записал то же значение.
        if cur == old || cur == new {
            break cur;
        }

        // Гонка с другим обновлением — повторяем.
        old = cur;
    }
}

#[no_mangle]
pub extern "C" fn errseq_sample(eseq: *mut ErrseqT) -> ErrseqT {
    let old = unsafe { read_once(eseq) };

    // Если никто не видел эту ошибку, мы можем быть первыми.
    if (old & ERRSEQ_SEEN) == 0 {
        0
    } else {
        old
    }
}

#[no_mangle]
pub extern "C" fn errseq_check(eseq: *mut ErrseqT, since: ErrseqT) -> c_int {
    let cur = unsafe { read_once(eseq) };

    if cur == since {
        return 0;
    }
    -((cur & ERRNO_MASK) as c_int)
}

#[no_mangle]
pub extern "C" fn errseq_check_and_advance(eseq: *mut ErrseqT, since: *mut ErrseqT) -> c_int {
    let mut err: c_int = 0;
    let mut old = unsafe { read_once(eseq) };

    while old != unsafe { ptr::read(since) } {
        // Выставляем SEEN и пытаемся записать значение обратно.
        let new = old | ERRSEQ_SEEN;
        if new != old {
            let cur = unsafe { cmpxchg(eseq, old, new) };
            if cur != old {
                // Значение изменилось параллельно — повторяем с новым.
                old = cur;
                continue;
            }
        }
        unsafe { ptr::write(since, new) };
        err = -((new & ERRNO_MASK) as c_int);
        break;
    }
    err
}
