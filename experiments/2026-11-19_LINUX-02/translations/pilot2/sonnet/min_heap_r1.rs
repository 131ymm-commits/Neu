use core::ffi::{c_uint, c_ulong, c_void};
use core::ptr;

#[repr(C)]
pub struct min_heap_char {
    pub nr: usize,
    pub size: usize,
    pub data: *mut u8,
    pub preallocated: [u8; 0],
}

#[repr(C)]
pub struct min_heap_callbacks {
    pub less: Option<unsafe extern "C" fn(*const c_void, *const c_void, *mut c_void) -> bool>,
    pub swp: Option<unsafe extern "C" fn(*mut c_void, *mut c_void, *mut c_void)>,
}

type SwapFn = unsafe extern "C" fn(*mut c_void, *mut c_void, *mut c_void);

const SWAP_WORDS_64: usize = 0;
const SWAP_WORDS_32: usize = 1;
const SWAP_BYTES: usize = 2;

#[inline(always)]
fn off(p: *mut u8, n: usize) -> *mut u8 {
    p.wrapping_add(n)
}

#[inline(always)]
fn is_aligned(_base: *const c_void, size: usize, align: u8) -> bool {
    let lsbits = size as u8;
    (lsbits & (align - 1)) == 0
}

#[inline(always)]
unsafe fn swap_words_32(a: *mut u8, b: *mut u8, mut n: usize) {
    loop {
        n = n.wrapping_sub(4);
        let t = ptr::read_unaligned(off(a, n) as *const u32);
        ptr::write_unaligned(off(a, n) as *mut u32, ptr::read_unaligned(off(b, n) as *const u32));
        ptr::write_unaligned(off(b, n) as *mut u32, t);
        if n == 0 {
            break;
        }
    }
}

#[inline(always)]
unsafe fn swap_words_64(a: *mut u8, b: *mut u8, mut n: usize) {
    loop {
        n = n.wrapping_sub(8);
        let t = ptr::read_unaligned(off(a, n) as *const u64);
        ptr::write_unaligned(off(a, n) as *mut u64, ptr::read_unaligned(off(b, n) as *const u64));
        ptr::write_unaligned(off(b, n) as *mut u64, t);
        if n == 0 {
            break;
        }
    }
}

#[inline(always)]
unsafe fn swap_bytes(a: *mut u8, b: *mut u8, mut n: usize) {
    loop {
        n = n.wrapping_sub(1);
        let t = *off(a, n);
        *off(a, n) = *off(b, n);
        *off(b, n) = t;
        if n == 0 {
            break;
        }
    }
}

#[inline(always)]
fn select_swap_func(base: *const c_void, size: usize) -> usize {
    if is_aligned(base, size, 8) {
        SWAP_WORDS_64
    } else if is_aligned(base, size, 4) {
        SWAP_WORDS_32
    } else {
        SWAP_BYTES
    }
}

#[inline(always)]
unsafe fn do_swap(a: *mut u8, b: *mut u8, size: usize, swap_func: usize, privp: *mut c_void) {
    if swap_func == SWAP_WORDS_64 {
        swap_words_64(a, b, size);
    } else if swap_func == SWAP_WORDS_32 {
        swap_words_32(a, b, size);
    } else if swap_func == SWAP_BYTES {
        swap_bytes(a, b, size);
    } else {
        let f: SwapFn = core::mem::transmute::<usize, SwapFn>(swap_func);
        f(a as *mut c_void, b as *mut c_void, privp);
    }
}

#[inline(always)]
fn parent(mut i: usize, lsbit: c_uint, size: usize) -> usize {
    i = i.wrapping_sub(size);
    let m = (i & (lsbit as usize)).wrapping_neg();
    i = i.wrapping_sub(size & m);
    i / 2
}

#[inline(always)]
unsafe fn get_swp(func: *const min_heap_callbacks) -> usize {
    core::mem::transmute::<Option<SwapFn>, usize>((*func).swp)
}

#[inline(always)]
unsafe fn call_less(func: *const min_heap_callbacks, a: *mut u8, b: *mut u8, args: *mut c_void) -> bool {
    ((*func).less.unwrap())(a as *const c_void, b as *const c_void, args)
}

unsafe fn sift_down_inline(
    heap: *mut min_heap_char,
    pos: usize,
    elem_size: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) {
    let lsbit: c_ulong = elem_size.wrapping_neg() & elem_size;
    let lsbit = lsbit as c_uint;
    let data = (*heap).data;
    let mut swp = get_swp(func);
    let a = pos.wrapping_mul(elem_size);
    let mut b: usize;
    let mut c: usize;
    let mut d: usize;
    let n = (*heap).nr.wrapping_mul(elem_size);

    if swp == 0 {
        swp = select_swap_func(data as *const c_void, elem_size);
    }

    b = a;
    loop {
        c = b.wrapping_mul(2).wrapping_add(elem_size);
        d = c.wrapping_add(elem_size);
        if !(d < n) {
            break;
        }
        b = if call_less(func, off(data, c), off(data, d), args) { c } else { d };
    }

    if d == n {
        b = c;
    }

    while b != a && call_less(func, off(data, a), off(data, b), args) {
        b = parent(b, lsbit, elem_size);
    }

    c = b;
    while b != a {
        b = parent(b, lsbit, elem_size);
        do_swap(off(data, b), off(data, c), elem_size, swp, args);
    }
}

unsafe fn sift_up_inline(
    heap: *mut min_heap_char,
    elem_size: usize,
    idx: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) {
    let lsbit: c_ulong = elem_size.wrapping_neg() & elem_size;
    let lsbit = lsbit as c_uint;
    let data = (*heap).data;
    let mut swp = get_swp(func);
    let mut a = idx.wrapping_mul(elem_size);
    let mut b: usize;

    if swp == 0 {
        swp = select_swap_func(data as *const c_void, elem_size);
    }

    while a != 0 {
        b = parent(a, lsbit, elem_size);
        if call_less(func, off(data, b), off(data, a), args) {
            break;
        }
        do_swap(off(data, a), off(data, b), elem_size, swp, args);
        a = b;
    }
}

#[no_mangle]
pub unsafe extern "C" fn __min_heap_init(heap: *mut min_heap_char, data: *mut c_void, size: usize) {
    (*heap).nr = 0;
    (*heap).size = size;
    if !data.is_null() {
        (*heap).data = data as *mut u8;
    } else {
        (*heap).data = ptr::addr_of_mut!((*heap).preallocated) as *mut u8;
    }
}

#[no_mangle]
pub unsafe extern "C" fn __min_heap_peek(heap: *mut min_heap_char) -> *mut c_void {
    if (*heap).nr != 0 {
        (*heap).data as *mut c_void
    } else {
        ptr::null_mut()
    }
}

#[no_mangle]
pub unsafe extern "C" fn __min_heap_full(heap: *mut min_heap_char) -> bool {
    (*heap).nr == (*heap).size
}

#[no_mangle]
pub unsafe extern "C" fn __min_heap_sift_down(
    heap: *mut min_heap_char,
    pos: usize,
    elem_size: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) {
    sift_down_inline(heap, pos, elem_size, func, args);
}

#[no_mangle]
pub unsafe extern "C" fn __min_heap_sift_up(
    heap: *mut min_heap_char,
    elem_size: usize,
    idx: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) {
    sift_up_inline(heap, elem_size, idx, func, args);
}

#[no_mangle]
pub unsafe extern "C" fn __min_heapify_all(
    heap: *mut min_heap_char,
    elem_size: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) {
    let mut i: isize = ((*heap).nr / 2).wrapping_sub(1) as isize;
    while i >= 0 {
        sift_down_inline(heap, i as usize, elem_size, func, args);
        i -= 1;
    }
}

#[no_mangle]
pub unsafe extern "C" fn __min_heap_pop(
    heap: *mut min_heap_char,
    elem_size: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) -> bool {
    let data = (*heap).data;

    if (*heap).nr == 0 {
        return false;
    }

    (*heap).nr -= 1;
    ptr::copy(off(data, (*heap).nr.wrapping_mul(elem_size)) as *const u8, data, elem_size);
    sift_down_inline(heap, 0, elem_size, func, args);

    true
}

#[no_mangle]
pub unsafe extern "C" fn __min_heap_pop_push(
    heap: *mut min_heap_char,
    element: *const c_void,
    elem_size: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) {
    ptr::copy(element as *const u8, (*heap).data, elem_size);
    sift_down_inline(heap, 0, elem_size, func, args);
}

#[no_mangle]
pub unsafe extern "C" fn __min_heap_push(
    heap: *mut min_heap_char,
    element: *const c_void,
    elem_size: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) -> bool {
    let data = (*heap).data;

    if (*heap).nr >= (*heap).size {
        return false;
    }

    let pos = (*heap).nr;
    ptr::copy(element as *const u8, off(data, pos.wrapping_mul(elem_size)), elem_size);
    (*heap).nr += 1;

    sift_up_inline(heap, elem_size, pos, func, args);

    true
}

#[no_mangle]
pub unsafe extern "C" fn __min_heap_del(
    heap: *mut min_heap_char,
    elem_size: usize,
    idx: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) -> bool {
    let data = (*heap).data;
    let mut swp = get_swp(func);

    if (*heap).nr == 0 {
        return false;
    }

    if swp == 0 {
        swp = select_swap_func(data as *const c_void, elem_size);
    }

    (*heap).nr -= 1;
    if idx == (*heap).nr {
        return true;
    }
    do_swap(
        off(data, idx.wrapping_mul(elem_size)),
        off(data, (*heap).nr.wrapping_mul(elem_size)),
        elem_size,
        swp,
        args,
    );
    sift_up_inline(heap, elem_size, idx, func, args);
    sift_down_inline(heap, idx, elem_size, func, args);

    true
}
