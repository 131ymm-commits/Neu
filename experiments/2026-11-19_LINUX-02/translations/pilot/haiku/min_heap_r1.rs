#![allow(non_camel_case_types)]

use core::ffi::{c_char, c_uint, c_ulong, c_void};
use core::ptr;

/// int (*less)(const void *lhs, const void *rhs, void *args)
pub type LessFn = unsafe extern "C" fn(*const c_void, *const c_void, *mut c_void) -> bool;
/// void (*swp)(void *lhs, void *rhs, void *args)
pub type SwapFn = unsafe extern "C" fn(*mut c_void, *mut c_void, *mut c_void);

/// struct min_heap_char из DEFINE_MIN_HEAP(char, min_heap_char)
#[repr(C)]
pub struct min_heap_char {
    pub nr: usize,
    pub size: usize,
    pub data: *mut c_char,
    pub preallocated: [c_char; 0],
}

/// struct min_heap_callbacks
#[repr(C)]
pub struct min_heap_callbacks {
    pub less: Option<LessFn>,
    pub swp: Option<SwapFn>,
}

/// Вместо sentinel-значений SWAP_WORDS_64 / SWAP_WORDS_32 / SWAP_BYTES из C
/// (ненулевые целые, приведённые к указателю функции, которые только сравниваются)
/// используется перечисление с тем же поведением.
#[derive(Clone, Copy)]
enum Swap {
    Words64,
    Words32,
    Bytes,
    Custom(SwapFn),
}

/// WARN_ONCE / WARN_ON_ONCE: вывод в журнал недоступен (только core, без ввода-вывода),
/// поэтому возвращается только условие.
#[inline(always)]
fn warn_once(cond: bool, _msg: &str) -> bool {
    cond
}

/// is_aligned: CONFIG_HAVE_EFFICIENT_UNALIGNED_ACCESS включён, адрес base не проверяется.
#[inline(always)]
fn is_aligned(_base: *const c_void, size: usize, align: u8) -> bool {
    let lsbits = size as u8;
    (lsbits & align.wrapping_sub(1)) == 0
}

#[inline(always)]
unsafe fn swap_words_32(a: *mut u8, b: *mut u8, mut n: usize) {
    loop {
        n = n.wrapping_sub(4);
        let pa = a.add(n) as *mut u32;
        let pb = b.add(n) as *mut u32;
        let t = pa.read_unaligned();
        pa.write_unaligned(pb.read_unaligned());
        pb.write_unaligned(t);
        if n == 0 {
            break;
        }
    }
}

#[inline(always)]
unsafe fn swap_words_64(a: *mut u8, b: *mut u8, mut n: usize) {
    loop {
        n = n.wrapping_sub(8);
        let pa = a.add(n) as *mut u64;
        let pb = b.add(n) as *mut u64;
        let t = pa.read_unaligned();
        pa.write_unaligned(pb.read_unaligned());
        pb.write_unaligned(t);
        if n == 0 {
            break;
        }
    }
}

#[inline(always)]
unsafe fn swap_bytes(a: *mut u8, b: *mut u8, mut n: usize) {
    loop {
        n = n.wrapping_sub(1);
        let t = *a.add(n);
        *a.add(n) = *b.add(n);
        *b.add(n) = t;
        if n == 0 {
            break;
        }
    }
}

#[inline(always)]
fn select_swap_func(base: *const c_void, size: usize) -> Swap {
    if is_aligned(base, size, 8) {
        Swap::Words64
    } else if is_aligned(base, size, 4) {
        Swap::Words32
    } else {
        Swap::Bytes
    }
}

#[inline(always)]
unsafe fn resolve_swap(func: *const min_heap_callbacks, data: *mut u8, elem_size: usize) -> Swap {
    match (*func).swp {
        Some(f) => Swap::Custom(f),
        None => select_swap_func(data as *const c_void, elem_size),
    }
}

#[inline(always)]
unsafe fn do_swap(a: *mut u8, b: *mut u8, size: usize, swap: Swap, args: *mut c_void) {
    match swap {
        Swap::Words64 => swap_words_64(a, b, size),
        Swap::Words32 => swap_words_32(a, b, size),
        Swap::Bytes => swap_bytes(a, b, size),
        Swap::Custom(f) => f(a as *mut c_void, b as *mut c_void, args),
    }
}

#[inline(always)]
unsafe fn call_less(
    func: *const min_heap_callbacks,
    lhs: *mut u8,
    rhs: *mut u8,
    args: *mut c_void,
) -> bool {
    let less = (*func).less.unwrap();
    less(lhs as *const c_void, rhs as *const c_void, args)
}

/// Родитель смещения i. lsbit — битовая маска size & -size, передаётся как unsigned int
/// (усечение до 32 бит, как при неявном преобразовании в C).
#[inline(always)]
fn parent(i: usize, lsbit: c_ulong, size: usize) -> usize {
    let lsbit = lsbit as c_uint as usize;
    let mut i = i.wrapping_sub(size);
    i = i.wrapping_sub(size & (i & lsbit).wrapping_neg());
    i / 2
}

#[inline(always)]
unsafe fn __min_heap_init_inline(heap: *mut min_heap_char, data: *mut c_void, size: usize) {
    (*heap).nr = 0;
    (*heap).size = size;
    if !data.is_null() {
        (*heap).data = data as *mut c_char;
    } else {
        (*heap).data = ptr::addr_of_mut!((*heap).preallocated) as *mut c_char;
    }
}

#[inline(always)]
unsafe fn __min_heap_peek_inline(heap: *mut min_heap_char) -> *mut c_void {
    if (*heap).nr != 0 {
        (*heap).data as *mut c_void
    } else {
        ptr::null_mut()
    }
}

#[inline(always)]
unsafe fn __min_heap_full_inline(heap: *mut min_heap_char) -> bool {
    (*heap).nr == (*heap).size
}

#[inline(always)]
unsafe fn __min_heap_sift_down_inline(
    heap: *mut min_heap_char,
    pos: usize,
    elem_size: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) {
    let lsbit = (elem_size & elem_size.wrapping_neg()) as c_ulong;
    let data = (*heap).data as *mut u8;
    let swap = resolve_swap(func, data, elem_size);

    // Масштабированные счётчики.
    let a = pos.wrapping_mul(elem_size);
    let mut b = a;
    let mut c: usize = 0;
    let mut d: usize = 0;
    let n = (*heap).nr.wrapping_mul(elem_size);

    // Путь вниз до листьев.
    loop {
        c = b.wrapping_mul(2).wrapping_add(elem_size);
        d = c.wrapping_add(elem_size);
        if d >= n {
            break;
        }
        b = if call_less(func, data.add(c), data.add(d), args) { c } else { d };
    }

    // Особый случай: последний лист без пары.
    if d == n {
        b = c;
    }

    // Возврат к правильной позиции.
    while b != a && call_less(func, data.add(a), data.add(b), args) {
        b = parent(b, lsbit, elem_size);
    }

    // Перемещение элемента на место.
    c = b;
    while b != a {
        b = parent(b, lsbit, elem_size);
        do_swap(data.add(b), data.add(c), elem_size, swap, args);
    }
}

#[inline(always)]
unsafe fn __min_heap_sift_up_inline(
    heap: *mut min_heap_char,
    elem_size: usize,
    idx: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) {
    let lsbit = (elem_size & elem_size.wrapping_neg()) as c_ulong;
    let data = (*heap).data as *mut u8;
    let swap = resolve_swap(func, data, elem_size);

    let mut a = idx.wrapping_mul(elem_size);
    while a != 0 {
        let b = parent(a, lsbit, elem_size);
        if call_less(func, data.add(b), data.add(a), args) {
            break;
        }
        do_swap(data.add(a), data.add(b), elem_size, swap, args);
        a = b;
    }
}

/// Floyd: heapify за O(nr).
#[inline(always)]
unsafe fn __min_heapify_all_inline(
    heap: *mut min_heap_char,
    elem_size: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) {
    let mut i: isize = ((*heap).nr / 2).wrapping_sub(1) as isize;
    while i >= 0 {
        __min_heap_sift_down_inline(heap, i as usize, elem_size, func, args);
        i -= 1;
    }
}

#[inline(always)]
unsafe fn __min_heap_pop_inline(
    heap: *mut min_heap_char,
    elem_size: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) -> bool {
    let data = (*heap).data as *mut u8;

    if warn_once((*heap).nr == 0, "Popping an empty heap") {
        return false;
    }

    // Последний элемент ставится в корень, затем sift down.
    let nr = (*heap).nr.wrapping_sub(1);
    (*heap).nr = nr;
    ptr::copy(data.add(nr.wrapping_mul(elem_size)), data, elem_size);
    __min_heap_sift_down_inline(heap, 0, elem_size, func, args);

    true
}

#[inline(always)]
unsafe fn __min_heap_pop_push_inline(
    heap: *mut min_heap_char,
    element: *const c_void,
    elem_size: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) {
    let data = (*heap).data as *mut u8;
    ptr::copy(element as *const u8, data, elem_size);
    __min_heap_sift_down_inline(heap, 0, elem_size, func, args);
}

#[inline(always)]
unsafe fn __min_heap_push_inline(
    heap: *mut min_heap_char,
    element: *const c_void,
    elem_size: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) -> bool {
    let data = (*heap).data as *mut u8;

    if warn_once((*heap).nr >= (*heap).size, "Pushing on a full heap") {
        return false;
    }

    // Элемент помещается в конец массива.
    let pos = (*heap).nr;
    ptr::copy(
        element as *const u8,
        data.add(pos.wrapping_mul(elem_size)),
        elem_size,
    );
    (*heap).nr = pos + 1;

    // Подъём элемента на позицию pos.
    __min_heap_sift_up_inline(heap, elem_size, pos, func, args);

    true
}

#[inline(always)]
unsafe fn __min_heap_del_inline(
    heap: *mut min_heap_char,
    elem_size: usize,
    idx: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) -> bool {
    let data = (*heap).data as *mut u8;

    if warn_once((*heap).nr == 0, "Popping an empty heap") {
        return false;
    }

    let swap = resolve_swap(func, data, elem_size);

    // Последний элемент ставится на место idx, затем восстанавливается куча.
    (*heap).nr = (*heap).nr.wrapping_sub(1);
    let nr = (*heap).nr;
    if idx == nr {
        return true;
    }
    do_swap(
        data.add(idx.wrapping_mul(elem_size)),
        data.add(nr.wrapping_mul(elem_size)),
        elem_size,
        swap,
        args,
    );
    __min_heap_sift_up_inline(heap, elem_size, idx, func, args);
    __min_heap_sift_down_inline(heap, idx, elem_size, func, args);

    true
}

// ---------------------------------------------------------------------------
// Экспортируемые функции (lib/min_heap.c)
// ---------------------------------------------------------------------------

#[no_mangle]
pub unsafe extern "C" fn __min_heap_init(heap: *mut min_heap_char, data: *mut c_void, size: usize) {
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
    pos: usize,
    elem_size: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) {
    __min_heap_sift_down_inline(heap, pos, elem_size, func, args)
}

#[no_mangle]
pub unsafe extern "C" fn __min_heap_sift_up(
    heap: *mut min_heap_char,
    elem_size: usize,
    idx: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) {
    __min_heap_sift_up_inline(heap, elem_size, idx, func, args)
}

#[no_mangle]
pub unsafe extern "C" fn __min_heapify_all(
    heap: *mut min_heap_char,
    elem_size: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) {
    __min_heapify_all_inline(heap, elem_size, func, args)
}

#[no_mangle]
pub unsafe extern "C" fn __min_heap_pop(
    heap: *mut min_heap_char,
    elem_size: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) -> bool {
    __min_heap_pop_inline(heap, elem_size, func, args)
}

#[no_mangle]
pub unsafe extern "C" fn __min_heap_pop_push(
    heap: *mut min_heap_char,
    element: *const c_void,
    elem_size: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) {
    __min_heap_pop_push_inline(heap, element, elem_size, func, args)
}

#[no_mangle]
pub unsafe extern "C" fn __min_heap_push(
    heap: *mut min_heap_char,
    element: *const c_void,
    elem_size: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) -> bool {
    __min_heap_push_inline(heap, element, elem_size, func, args)
}

#[no_mangle]
pub unsafe extern "C" fn __min_heap_del(
    heap: *mut min_heap_char,
    elem_size: usize,
    idx: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) -> bool {
    __min_heap_del_inline(heap, elem_size, idx, func, args)
}
