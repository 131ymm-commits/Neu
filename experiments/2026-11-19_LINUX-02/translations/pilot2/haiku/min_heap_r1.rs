#![allow(non_camel_case_types)]

// Перевод lib/min_heap.c и встроенных функций include/linux/min_heap.h.
// Только core; ввода-вывода нет.

use core::ffi::{c_uint, c_ulong, c_void};

type size_t = usize;
type ssize_t = isize;

/// void (*)(void *lhs, void *rhs, void *args)
type SwapFn = unsafe extern "C" fn(lhs: *mut c_void, rhs: *mut c_void, args: *mut c_void);

#[repr(C)]
pub struct min_heap_char {
    pub nr: size_t,
    pub size: size_t,
    pub data: *mut u8,
    pub preallocated: [u8; 0],
}

#[repr(C)]
pub struct min_heap_callbacks {
    pub less: unsafe extern "C" fn(lhs: *const c_void, rhs: *const c_void, args: *mut c_void) -> bool,
    pub swp: Option<SwapFn>,
}

/// Значения "функции обмена" как в C: маленькие целые, приведённые к указателю.
/// SWAP_WORDS_64 совпадает с NULL.
const SWAP_WORDS_64: usize = 0;
const SWAP_WORDS_32: usize = 1;
const SWAP_BYTES: usize = 2;

/// WARN_ONCE(cond, msg): вывод в журнал опущен (нет ввода-вывода), возвращается cond.
#[inline(always)]
fn warn_once(cond: bool) -> bool {
    cond
}

/// CONFIG_HAVE_EFFICIENT_UNALIGNED_ACCESS задан (x86_64), поэтому адрес base
/// в проверку выравнивания не входит: учитывается только size.
#[inline(always)]
fn is_aligned(_base: *const c_void, size: size_t, align: u8) -> bool {
    let lsbits: u8 = size as u8;
    (lsbits & align.wrapping_sub(1)) == 0
}

/// Обмен поэлементно по 32-битным словам. n кратно 4.
unsafe fn swap_words_32(a: *mut u8, b: *mut u8, mut n: size_t) {
    loop {
        n = n.wrapping_sub(4);
        let t = core::ptr::read_unaligned(a.wrapping_add(n) as *const u32);
        let bv = core::ptr::read_unaligned(b.wrapping_add(n) as *const u32);
        core::ptr::write_unaligned(a.wrapping_add(n) as *mut u32, bv);
        core::ptr::write_unaligned(b.wrapping_add(n) as *mut u32, t);
        if n == 0 {
            break;
        }
    }
}

/// Обмен поэлементно по 64-битным словам (ветка CONFIG_64BIT). n кратно 8.
unsafe fn swap_words_64(a: *mut u8, b: *mut u8, mut n: size_t) {
    loop {
        n = n.wrapping_sub(8);
        let t = core::ptr::read_unaligned(a.wrapping_add(n) as *const u64);
        let bv = core::ptr::read_unaligned(b.wrapping_add(n) as *const u64);
        core::ptr::write_unaligned(a.wrapping_add(n) as *mut u64, bv);
        core::ptr::write_unaligned(b.wrapping_add(n) as *mut u64, t);
        if n == 0 {
            break;
        }
    }
}

/// Обмен побайтно (запасной вариант).
unsafe fn swap_bytes(a: *mut u8, b: *mut u8, mut n: size_t) {
    loop {
        n = n.wrapping_sub(1);
        let t = *a.wrapping_add(n);
        *a.wrapping_add(n) = *b.wrapping_add(n);
        *b.wrapping_add(n) = t;
        if n == 0 {
            break;
        }
    }
}

fn select_swap_func(base: *const c_void, size: size_t) -> usize {
    if is_aligned(base, size, 8) {
        SWAP_WORDS_64
    } else if is_aligned(base, size, 4) {
        SWAP_WORDS_32
    } else {
        SWAP_BYTES
    }
}

unsafe fn do_swap(a: *mut u8, b: *mut u8, size: size_t, swap_func: usize, priv_: *mut c_void) {
    if swap_func == SWAP_WORDS_64 {
        swap_words_64(a, b, size);
    } else if swap_func == SWAP_WORDS_32 {
        swap_words_32(a, b, size);
    } else if swap_func == SWAP_BYTES {
        swap_bytes(a, b, size);
    } else {
        let f = core::mem::transmute::<usize, SwapFn>(swap_func);
        f(a as *mut c_void, b as *mut c_void, priv_);
    }
}

/// Смещение родителя. lsbit передаётся в параметр unsigned int, поэтому
/// усекается до 32 бит (как неявное преобразование в C).
#[inline(always)]
fn parent(mut i: size_t, lsbit: c_ulong, size: size_t) -> size_t {
    let lsbit = lsbit as c_uint as size_t;
    i = i.wrapping_sub(size);
    i = i.wrapping_sub(size & (i & lsbit).wrapping_neg());
    i / 2
}

/// Вызов func->less(lhs, rhs, args).
#[inline(always)]
unsafe fn call_less(
    func: *const min_heap_callbacks,
    lhs: *mut u8,
    rhs: *mut u8,
    args: *mut c_void,
) -> bool {
    ((*func).less)(lhs as *const c_void, rhs as *const c_void, args)
}

unsafe fn __min_heap_init_inline(heap: *mut min_heap_char, data: *mut c_void, size: size_t) {
    (*heap).nr = 0;
    (*heap).size = size;
    if !data.is_null() {
        (*heap).data = data as *mut u8;
    } else {
        (*heap).data = core::ptr::addr_of_mut!((*heap).preallocated) as *mut u8;
    }
}

unsafe fn __min_heap_peek_inline(heap: *mut min_heap_char) -> *mut c_void {
    if (*heap).nr != 0 {
        (*heap).data as *mut c_void
    } else {
        core::ptr::null_mut()
    }
}

unsafe fn __min_heap_full_inline(heap: *mut min_heap_char) -> bool {
    (*heap).nr == (*heap).size
}

unsafe fn __min_heap_sift_down_inline(
    heap: *mut min_heap_char,
    pos: size_t,
    elem_size: size_t,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) {
    let lsbit: c_ulong = (elem_size & elem_size.wrapping_neg()) as c_ulong;
    let data: *mut u8 = (*heap).data;
    let mut swp: usize = (*func).swp.map_or(0usize, |f| f as usize);
    // Счётчики предварительно масштабированы по размеру элемента.
    let mut a: size_t = pos.wrapping_mul(elem_size);
    let mut b: size_t;
    let mut c: size_t;
    let mut d: size_t;
    let n: size_t = (*heap).nr.wrapping_mul(elem_size);

    if swp == 0 {
        swp = select_swap_func(data as *const c_void, elem_size);
    }

    // Путь вниз до листьев.
    b = a;
    loop {
        c = b.wrapping_mul(2).wrapping_add(elem_size);
        d = c.wrapping_add(elem_size);
        if d >= n {
            break;
        }
        b = if call_less(
            func,
            data.wrapping_add(c),
            data.wrapping_add(d),
            args,
        ) {
            c
        } else {
            d
        };
    }

    // Особый случай: последний лист без пары.
    if d == n {
        b = c;
    }

    // Возврат к правильной позиции.
    while b != a && call_less(func, data.wrapping_add(a), data.wrapping_add(b), args) {
        b = parent(b, lsbit, elem_size);
    }

    // Сдвиг элемента на место.
    c = b;
    while b != a {
        b = parent(b, lsbit, elem_size);
        do_swap(
            data.wrapping_add(b),
            data.wrapping_add(c),
            elem_size,
            swp,
            args,
        );
    }
}

unsafe fn __min_heap_sift_up_inline(
    heap: *mut min_heap_char,
    elem_size: size_t,
    idx: size_t,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) {
    let lsbit: c_ulong = (elem_size & elem_size.wrapping_neg()) as c_ulong;
    let data: *mut u8 = (*heap).data;
    let mut swp: usize = (*func).swp.map_or(0usize, |f| f as usize);
    let mut a: size_t = idx.wrapping_mul(elem_size);
    let mut b: size_t;

    if swp == 0 {
        swp = select_swap_func(data as *const c_void, elem_size);
    }

    while a != 0 {
        b = parent(a, lsbit, elem_size);
        if call_less(func, data.wrapping_add(b), data.wrapping_add(a), args) {
            break;
        }
        do_swap(
            data.wrapping_add(a),
            data.wrapping_add(b),
            elem_size,
            swp,
            args,
        );
        a = b;
    }
}

/// Floyd: heapify за O(nr).
unsafe fn __min_heapify_all_inline(
    heap: *mut min_heap_char,
    elem_size: size_t,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) {
    let mut i: ssize_t = ((*heap).nr / 2).wrapping_sub(1) as ssize_t;
    while i >= 0 {
        __min_heap_sift_down_inline(heap, i as size_t, elem_size, func, args);
        i -= 1;
    }
}

unsafe fn __min_heap_pop_inline(
    heap: *mut min_heap_char,
    elem_size: size_t,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) -> bool {
    let data: *mut u8 = (*heap).data;

    if warn_once((*heap).nr == 0) {
        return false;
    }

    // Последний элемент ставится в корень (позиция 0), затем просеивание вниз.
    (*heap).nr = (*heap).nr.wrapping_sub(1);
    core::ptr::copy(
        data.wrapping_add((*heap).nr.wrapping_mul(elem_size)),
        data,
        elem_size,
    );
    __min_heap_sift_down_inline(heap, 0, elem_size, func, args);

    true
}

/// Удаление минимума и вставка нового элемента за один просеивание.
unsafe fn __min_heap_pop_push_inline(
    heap: *mut min_heap_char,
    element: *const c_void,
    elem_size: size_t,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) {
    core::ptr::copy(element as *const u8, (*heap).data, elem_size);
    __min_heap_sift_down_inline(heap, 0, elem_size, func, args);
}

unsafe fn __min_heap_push_inline(
    heap: *mut min_heap_char,
    element: *const c_void,
    elem_size: size_t,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) -> bool {
    let data: *mut u8 = (*heap).data;

    if warn_once((*heap).nr >= (*heap).size) {
        return false;
    }

    // Элемент помещается в конец массива.
    let pos: size_t = (*heap).nr;
    core::ptr::copy(
        element as *const u8,
        data.wrapping_add(pos.wrapping_mul(elem_size)),
        elem_size,
    );
    (*heap).nr = (*heap).nr.wrapping_add(1);

    // Просеивание вверх.
    __min_heap_sift_up_inline(heap, elem_size, pos, func, args);

    true
}

unsafe fn __min_heap_del_inline(
    heap: *mut min_heap_char,
    elem_size: size_t,
    idx: size_t,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) -> bool {
    let data: *mut u8 = (*heap).data;
    let mut swp: usize = (*func).swp.map_or(0usize, |f| f as usize);

    if warn_once((*heap).nr == 0) {
        return false;
    }

    if swp == 0 {
        swp = select_swap_func(data as *const c_void, elem_size);
    }

    // Последний элемент ставится на место удаляемого, затем просеивание.
    (*heap).nr = (*heap).nr.wrapping_sub(1);
    if idx == (*heap).nr {
        return true;
    }
    do_swap(
        data.wrapping_add(idx.wrapping_mul(elem_size)),
        data.wrapping_add((*heap).nr.wrapping_mul(elem_size)),
        elem_size,
        swp,
        args,
    );
    __min_heap_sift_up_inline(heap, elem_size, idx, func, args);
    __min_heap_sift_down_inline(heap, idx, elem_size, func, args);

    true
}

// ---- экспортируемые функции ----

#[no_mangle]
pub unsafe extern "C" fn __min_heap_init(heap: *mut min_heap_char, data: *mut c_void, size: size_t) {
    __min_heap_init_inline(heap, data, size)
}

#[no_mangle]
pub unsafe extern "C" fn __min_heap_peek(heap: *mut min_heap_char) -> *mut c_void {
    __min_heap_peek_inline(heap)
}

#[no_mangle]
pub unsafe extern "C" fn __min_heap_full(heap: *mut min_heap_char) -> bool {
    __min_heap_full_inline(heap)
}

#[no_mangle]
pub unsafe extern "C" fn __min_heap_sift_down(
    heap: *mut min_heap_char,
    pos: size_t,
    elem_size: size_t,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) {
    __min_heap_sift_down_inline(heap, pos, elem_size, func, args)
}

#[no_mangle]
pub unsafe extern "C" fn __min_heap_sift_up(
    heap: *mut min_heap_char,
    elem_size: size_t,
    idx: size_t,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) {
    __min_heap_sift_up_inline(heap, elem_size, idx, func, args)
}

#[no_mangle]
pub unsafe extern "C" fn __min_heapify_all(
    heap: *mut min_heap_char,
    elem_size: size_t,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) {
    __min_heapify_all_inline(heap, elem_size, func, args)
}

#[no_mangle]
pub unsafe extern "C" fn __min_heap_pop(
    heap: *mut min_heap_char,
    elem_size: size_t,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) -> bool {
    __min_heap_pop_inline(heap, elem_size, func, args)
}

#[no_mangle]
pub unsafe extern "C" fn __min_heap_pop_push(
    heap: *mut min_heap_char,
    element: *const c_void,
    elem_size: size_t,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) {
    __min_heap_pop_push_inline(heap, element, elem_size, func, args)
}

#[no_mangle]
pub unsafe extern "C" fn __min_heap_push(
    heap: *mut min_heap_char,
    element: *const c_void,
    elem_size: size_t,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) -> bool {
    __min_heap_push_inline(heap, element, elem_size, func, args)
}

#[no_mangle]
pub unsafe extern "C" fn __min_heap_del(
    heap: *mut min_heap_char,
    elem_size: size_t,
    idx: size_t,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) -> bool {
    __min_heap_del_inline(heap, elem_size, idx, func, args)
}
